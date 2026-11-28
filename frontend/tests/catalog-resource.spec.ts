import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils';
import { defineComponent } from 'vue';
import api, { ApiError } from '@/api';
import { useCatalogResource } from '@/components/catalog/useCatalogResource';
import {
  finishNavigation,
  routeBusy,
  scrollRestorationBusy,
  startNavigation,
} from '@/composables/useLoadingState';

const mounted = new Set<VueWrapper>();

beforeEach(() => {
  vi.useFakeTimers();
  startNavigation();
  finishNavigation();
});

afterEach(async () => {
  for (const wrapper of mounted) wrapper.unmount();
  mounted.clear();
  await flushPromises();
  vi.clearAllTimers();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function harness<T>(initial: () => T) {
  let resource!: ReturnType<typeof useCatalogResource<T>>;
  const wrapper = mount(defineComponent({
    setup() {
      resource = useCatalogResource(initial);
      return () => null;
    },
  }));
  mounted.add(wrapper);
  return {
    resource,
    unmount() {
      wrapper.unmount();
      mounted.delete(wrapper);
    },
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

function transport() {
  const requests: {
    path: string;
    signal: AbortSignal;
    respond: (body: unknown, status?: number) => void;
    reject: (reason: unknown) => void;
  }[] = [];
  vi.stubGlobal('fetch', vi.fn((path: string, options: RequestInit) => {
    const pending = deferred<Response>();
    const signal = options.signal!;
    const abort = () => pending.reject(new DOMException('传输已中止', 'AbortError'));
    if (signal.aborted) abort();
    else signal.addEventListener('abort', abort, { once: true });
    requests.push({
      path,
      signal,
      respond(body, status = 200) {
        pending.resolve({
          status,
          ok: status >= 200 && status < 300,
          json: async () => body,
        } as Response);
      },
      reject: pending.reject,
    });
    return pending.promise.finally(() => signal.removeEventListener('abort', abort));
  }));
  return requests;
}

describe('目录资源生命周期', () => {
  test('替换挂起的获取函数时中止并结束原请求，但不结束当前加载状态', async () => {
    const { resource } = harness(() => '原有数据');
    const old = deferred<string>();
    const next = deferred<string>();
    let oldSignal!: AbortSignal;
    let nextSignal!: AbortSignal;
    const previous = resource.load((signal) => {
      oldSignal = signal;
      return old.promise;
    });
    const current = resource.load((signal) => {
      nextSignal = signal;
      return next.promise;
    });

    expect(oldSignal.aborted).toBe(true);
    expect(nextSignal.aborted).toBe(false);
    expect(vi.getTimerCount()).toBe(1);
    await previous;
    old.reject(new ApiError('延迟返回的禁止访问错误', 403));
    await flushPromises();
    expect(resource).toMatchObject({ data: '原有数据', loading: true, error: '', status: 0 });

    next.resolve('当前数据');
    await current;
    expect(resource).toMatchObject({ data: '当前数据', loading: false, error: '', status: 0 });
    expect(nextSignal.aborted).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });

  test.each(['resolve', 'reject'] as const)('即使获取函数忽略中止，也忽略过时的 %s 结果', async (outcome) => {
    const { resource } = harness(() => '初始数据');
    const old = deferred<string>();
    const previous = resource.load(() => old.promise);
    await resource.load(async () => '最新数据');
    await previous;
    if (outcome === 'resolve') old.resolve('过时数据');
    else old.reject(new ApiError('延迟返回的资源不存在错误', 404));
    await flushPromises();
    expect(resource).toMatchObject({ data: '最新数据', loading: false, error: '', status: 0 });
    expect(vi.getTimerCount()).toBe(0);
  });

  test('重置时立即中止请求、恢复身份对应的数据，并允许再次加载', async () => {
    let viewer = 'alice';
    const { resource } = harness(() => `${viewer}: 空数据`);
    resource.data = 'alice: 私有数据';
    const old = deferred<string>();
    let oldSignal!: AbortSignal;
    const pending = resource.load((signal) => {
      oldSignal = signal;
      return old.promise;
    });
    viewer = 'bob';
    resource.reset();
    expect(oldSignal.aborted).toBe(true);
    expect(resource).toMatchObject({ data: 'bob: 空数据', loading: false, error: '', status: 0 });
    expect(vi.getTimerCount()).toBe(0);
    await pending;
    old.resolve('alice: 延迟返回的私有数据');
    await flushPromises();
    expect(resource.data).toBe('bob: 空数据');
    await resource.load(async () => 'bob: 新数据');
    expect(resource.data).toBe('bob: 新数据');
  });

  test('卸载时中止并结束挂起的获取函数，且不接受其延迟结果', async () => {
    const { resource, unmount } = harness(() => '保留数据');
    const old = deferred<string>();
    let signal!: AbortSignal;
    const pending = resource.load((value) => {
      signal = value;
      return old.promise;
    });
    unmount();
    expect(signal.aborted).toBe(true);
    expect(resource.loading).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
    await pending;
    old.resolve('过迟的结果');
    await flushPromises();
    expect(resource).toMatchObject({ data: '保留数据', loading: false, error: '', status: 0 });
  });

  test('释放已完成的请求，而不在之后中止它们', async () => {
    const { resource, unmount } = harness(() => '初始数据');
    let signal!: AbortSignal;
    await resource.load(async (value) => {
      signal = value;
      return '已完成';
    });
    resource.reset();
    unmount();
    expect(signal.aborted).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });

  test('挂起的获取函数在 12 秒后超时，中止信号、保留数据并允许重试', async () => {
    const { resource } = harness(() => '保留数据');
    const old = deferred<string>();
    let signal!: AbortSignal;
    const pending = resource.load((value) => {
      signal = value;
      return old.promise;
    });
    await vi.advanceTimersByTimeAsync(11999);
    expect(signal.aborted).toBe(false);
    expect(resource.loading).toBe(true);
    await vi.advanceTimersByTimeAsync(1);
    await pending;
    expect(signal.aborted).toBe(true);
    expect(resource).toMatchObject({ data: '保留数据', loading: false, error: '请求超时，请重试。', status: 408 });
    expect(vi.getTimerCount()).toBe(0);

    const retry = deferred<string>();
    const retrying = resource.load((nextSignal) => {
      expect(nextSignal).not.toBe(signal);
      expect(nextSignal.aborted).toBe(false);
      return retry.promise;
    });
    expect(resource).toMatchObject({ data: '保留数据', loading: true, error: '', status: 0 });
    retry.resolve('重试数据');
    await retrying;
    old.resolve('超时后延迟返回的结果');
    await flushPromises();
    expect(resource).toMatchObject({ data: '重试数据', loading: false, error: '', status: 0 });
    expect(vi.getTimerCount()).toBe(0);
  });

  test.each([
    [new ApiError('未找到资源', 404), 404, '该资源不存在或已不可访问。'],
    [new ApiError('禁止访问', 403), 403, '你暂时没有访问权限。'],
    [new ApiError('服务端失败', 500), 500, '服务端失败'],
    [new TypeError('网络失败'), 0, '网络失败'],
    [Object.assign(new Error('意外中止'), { name: 'AbortError' }), 0, '意外中止'],
    [new Error('真实失败'), 0, '真实失败'],
    ['未知拒绝原因', 0, '暂时无法加载，请重试。'],
  ])('保留真实错误：%s', async (failure, status, error) => {
    const { resource } = harness(() => '保留数据');
    await resource.load(async () => { throw failure; });
    expect(resource).toMatchObject({ data: '保留数据', loading: false, status, error });
    expect(vi.getTimerCount()).toBe(0);
    resource.reset();
    expect(resource).toMatchObject({ loading: false, status: 0, error: '' });
  });

  test('真实 DOM AbortError 即使跨越 Error 所属运行域也仍然可见', async () => {
    const { resource } = harness(() => '保留数据');
    await resource.load(async () => { throw new DOMException('意外中止', 'AbortError'); });
    expect(resource.error).not.toBe('');
    expect(resource).toMatchObject({ data: '保留数据', loading: false, status: 0 });
    expect(vi.getTimerCount()).toBe(0);
  });

  test('获取函数同步抛出错误时清理超时定时器', async () => {
    const { resource } = harness(() => '初始数据');
    await resource.load(() => { throw new Error('同步失败'); });
    expect(resource).toMatchObject({ data: '初始数据', loading: false, error: '同步失败' });
    expect(vi.getTimerCount()).toBe(0);
  });
});

const skillReads: [string, string, (signal: AbortSignal) => Promise<unknown>][] = [
  ['list', '/api/v1/skills?search=fox', (signal) => api.skills.list({ search: 'fox' }, { signal })],
  ['get', '/api/v1/skills/a%2Fb', (signal) => api.skills.get('a/b', { signal })],
  ['versions', '/api/v1/skills/a%2Fb/versions', (signal) => api.skills.versions('a/b', { signal })],
  ['version', '/api/v1/skills/a%2Fb/versions/1%2F2', (signal) => api.skills.version('a/b', '1/2', { signal })],
  ['comments', '/api/v1/skills/a%2Fb/comments?limit=5', (signal) => api.skills.comments('a/b', { limit: 5 }, { signal })],
  ['rating', '/api/v1/skills/a%2Fb/rating', (signal) => api.skills.rating('a/b', { signal })],
  ['my', '/api/v1/me/skills', (signal) => api.skills.my({ signal })],
  ['categories', '/api/v1/skills/categories', (signal) => api.skills.categories({ signal })],
  ['tags', '/api/v1/skills/tags', (signal) => api.skills.tags({ signal })],
];

describe('目录 API 请求取消', () => {
  test.each(skillReads)('将 %s 的选项传给 fetch，并在重置时清理', async (_, path, read) => {
    const requests = transport();
    const { resource } = harness<unknown>(() => null);
    let removeListener!: ReturnType<typeof vi.spyOn>;
    const pending = resource.load((signal) => {
      removeListener = vi.spyOn(signal, 'removeEventListener');
      return read(signal);
    });
    expect(requests).toHaveLength(1);
    expect(requests[0].path).toBe(path);
    expect(requests[0].signal.aborted).toBe(false);
    expect(vi.getTimerCount()).toBe(2);
    resource.reset();
    expect(requests[0].signal.aborted).toBe(true);
    await pending;
    await flushPromises();
    expect(removeListener).toHaveBeenCalledWith('abort', expect.any(Function));
    expect(resource).toMatchObject({ data: null, loading: false, error: '', status: 0 });
    expect(routeBusy.value).toBe(false);
    expect(scrollRestorationBusy.value).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });

  test.each(['plugins', 'skills'])('快速连续的 %s 搜索中止过时传输，而不中止最新读取', async (kind) => {
    const requests = transport();
    const { resource } = harness<unknown>(() => ({ items: ['原有数据'] }));
    const search = (q: string) => resource.load((signal) => kind === 'plugins'
      ? api.get(`/api/v1/plugins?q=${q}`, { signal })
      : api.skills.list({ search: q }, { signal }));
    const first = search('f');
    const second = search('fo');
    const third = search('fox');
    expect(requests.map((item) => item.signal.aborted)).toEqual([true, true, false]);
    await Promise.all([first, second]);
    await flushPromises();
    expect(resource).toMatchObject({ data: { items: ['原有数据'] }, loading: true, error: '' });
    expect(routeBusy.value).toBe(true);
    expect(scrollRestorationBusy.value).toBe(true);
    expect(vi.getTimerCount()).toBe(2);
    requests[2].respond({ items: ['最新数据'], total: 1 });
    await third;
    expect(resource).toMatchObject({ data: { items: ['最新数据'], total: 1 }, loading: false, error: '' });
    expect(routeBusy.value).toBe(false);
    expect(scrollRestorationBusy.value).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });

  test('共享的 12 秒时限仍报超时错误、中止 fetch 并释放两个定时器', async () => {
    const requests = transport();
    const { resource } = harness<unknown>(() => '保留数据');
    let signal!: AbortSignal;
    const pending = resource.load((value) => {
      signal = value;
      return api.get('/api/v1/plugins', { signal });
    });
    expect(vi.getTimerCount()).toBe(2);
    await vi.advanceTimersByTimeAsync(12000);
    await pending;
    expect(signal.aborted).toBe(true);
    expect(requests[0].signal.aborted).toBe(true);
    expect(resource).toMatchObject({ data: '保留数据', loading: false, error: '请求超时，请重试。', status: 408 });
    expect(routeBusy.value).toBe(false);
    expect(scrollRestorationBusy.value).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
    const retry = resource.load((nextSignal) => api.get('/api/v1/plugins', { signal: nextSignal }));
    expect(requests[1].signal.aborted).toBe(false);
    requests[1].respond('重试数据');
    await retry;
    expect(resource).toMatchObject({ data: '重试数据', loading: false, error: '', status: 0 });
    expect(vi.getTimerCount()).toBe(0);
  });

  test('API 提前超时的错误不被隐藏，且会清理资源超时定时器', async () => {
    const requests = transport();
    const { resource } = harness<unknown>(() => null);
    const pending = resource.load((signal) => api.get('/api/v1/skills', { signal, timeout: 1000 }));
    await vi.advanceTimersByTimeAsync(1000);
    await pending;
    expect(requests[0].signal.aborted).toBe(true);
    expect(resource).toMatchObject({ loading: false, error: '请求超时，请重试。', status: 408 });
    expect(routeBusy.value).toBe(false);
    expect(scrollRestorationBusy.value).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });

  test.each([
    [404, '该资源不存在或已不可访问。'],
    [403, '你暂时没有访问权限。'],
  ])('保持真实 HTTP %s 错误可见', async (status, error) => {
    const requests = transport();
    const { resource } = harness<unknown>(() => '保留数据');
    const pending = resource.load((signal) => api.skills.get('fox', { signal }));
    requests[0].respond({ error: { message: '服务端错误' } }, status);
    await pending;
    expect(resource).toMatchObject({ data: '保留数据', loading: false, error, status });
    expect(vi.getTimerCount()).toBe(0);
    expect(routeBusy.value).toBe(false);
    expect(scrollRestorationBusy.value).toBe(false);
  });

  test('保持真实网络失败可见', async () => {
    const requests = transport();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true);
    const { resource } = harness<unknown>(() => null);
    const pending = resource.load((signal) => api.get('/api/v1/plugins', { signal }));
    requests[0].reject(new TypeError('请求失败'));
    await pending;
    expect(resource).toMatchObject({ loading: false, error: '无法连接服务，请稍后重试。', status: 0 });
    expect(vi.getTimerCount()).toBe(0);
    expect(routeBusy.value).toBe(false);
    expect(scrollRestorationBusy.value).toBe(false);
  });

  test('卸载时取消目录读取，但不取消独立的修改操作', async () => {
    const requests = transport();
    const { resource, unmount } = harness<unknown>(() => null);
    const reading = resource.load((signal) => api.skills.get('fox', { signal }));
    const mutation = api.skills.toggleLike('fox');
    unmount();
    expect(requests[0].signal.aborted).toBe(true);
    expect(requests[1].signal.aborted).toBe(false);
    await reading;
    await flushPromises();
    expect(resource).toMatchObject({ loading: false, error: '' });
    expect(routeBusy.value).toBe(false);
    expect(scrollRestorationBusy.value).toBe(false);
    expect(vi.getTimerCount()).toBe(1);
    requests[1].respond({ liked: true });
    await expect(mutation).resolves.toEqual({ liked: true });
    expect(vi.getTimerCount()).toBe(0);
  });
});
