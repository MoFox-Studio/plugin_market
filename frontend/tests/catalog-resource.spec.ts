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
    const abort = () => pending.reject(new DOMException('Transport aborted', 'AbortError'));
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

describe('catalog resource lifecycle', () => {
  test('replacing a hung fetcher aborts and settles it without ending the current loading state', async () => {
    const { resource } = harness(() => 'previous data');
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
    old.reject(new ApiError('late forbidden', 403));
    await flushPromises();
    expect(resource).toMatchObject({ data: 'previous data', loading: true, error: '', status: 0 });

    next.resolve('current data');
    await current;
    expect(resource).toMatchObject({ data: 'current data', loading: false, error: '', status: 0 });
    expect(nextSignal.aborted).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });

  test.each(['resolve', 'reject'] as const)('ignores a stale %s even if fetcher ignores abort', async (outcome) => {
    const { resource } = harness(() => 'initial');
    const old = deferred<string>();
    const previous = resource.load(() => old.promise);
    await resource.load(async () => 'newest');
    await previous;
    if (outcome === 'resolve') old.resolve('stale data');
    else old.reject(new ApiError('stale missing', 404));
    await flushPromises();
    expect(resource).toMatchObject({ data: 'newest', loading: false, error: '', status: 0 });
    expect(vi.getTimerCount()).toBe(0);
  });

  test('reset aborts immediately, restores identity-specific data and allows another load', async () => {
    let viewer = 'alice';
    const { resource } = harness(() => `${viewer}: empty`);
    resource.data = 'alice: private data';
    const old = deferred<string>();
    let oldSignal!: AbortSignal;
    const pending = resource.load((signal) => {
      oldSignal = signal;
      return old.promise;
    });
    viewer = 'bob';
    resource.reset();
    expect(oldSignal.aborted).toBe(true);
    expect(resource).toMatchObject({ data: 'bob: empty', loading: false, error: '', status: 0 });
    expect(vi.getTimerCount()).toBe(0);
    await pending;
    old.resolve('alice: late private data');
    await flushPromises();
    expect(resource.data).toBe('bob: empty');
    await resource.load(async () => 'bob: fresh data');
    expect(resource.data).toBe('bob: fresh data');
  });

  test('unmount aborts and settles a hung fetcher without accepting its late result', async () => {
    const { resource, unmount } = harness(() => 'retained data');
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
    old.resolve('too late');
    await flushPromises();
    expect(resource).toMatchObject({ data: 'retained data', loading: false, error: '', status: 0 });
  });

  test('releases completed requests rather than aborting them later', async () => {
    const { resource, unmount } = harness(() => 'initial');
    let signal!: AbortSignal;
    await resource.load(async (value) => {
      signal = value;
      return 'done';
    });
    resource.reset();
    unmount();
    expect(signal.aborted).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });

  test('a hung fetcher times out at 12s, aborts its signal, keeps data and can retry', async () => {
    const { resource } = harness(() => 'retained data');
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
    expect(resource).toMatchObject({ data: 'retained data', loading: false, error: '请求超时，请重试。', status: 408 });
    expect(vi.getTimerCount()).toBe(0);

    const retry = deferred<string>();
    const retrying = resource.load((nextSignal) => {
      expect(nextSignal).not.toBe(signal);
      expect(nextSignal.aborted).toBe(false);
      return retry.promise;
    });
    expect(resource).toMatchObject({ data: 'retained data', loading: true, error: '', status: 0 });
    retry.resolve('retried');
    await retrying;
    old.resolve('late timeout result');
    await flushPromises();
    expect(resource).toMatchObject({ data: 'retried', loading: false, error: '', status: 0 });
    expect(vi.getTimerCount()).toBe(0);
  });

  test.each([
    [new ApiError('not found', 404), 404, '该资源不存在或已不可访问。'],
    [new ApiError('forbidden', 403), 403, '你暂时没有访问权限。'],
    [new ApiError('server failed', 500), 500, 'server failed'],
    [new TypeError('network failed'), 0, 'network failed'],
    [Object.assign(new Error('unexpected abort'), { name: 'AbortError' }), 0, 'unexpected abort'],
    [new Error('real failure'), 0, 'real failure'],
    ['unknown rejection', 0, '暂时无法加载，请重试。'],
  ])('preserves genuine errors: %s', async (failure, status, error) => {
    const { resource } = harness(() => 'retained data');
    await resource.load(async () => { throw failure; });
    expect(resource).toMatchObject({ data: 'retained data', loading: false, status, error });
    expect(vi.getTimerCount()).toBe(0);
    resource.reset();
    expect(resource).toMatchObject({ loading: false, status: 0, error: '' });
  });

  test('a genuine DOM AbortError remains visible even across Error realms', async () => {
    const { resource } = harness(() => 'retained data');
    await resource.load(async () => { throw new DOMException('unexpected abort', 'AbortError'); });
    expect(resource.error).not.toBe('');
    expect(resource).toMatchObject({ data: 'retained data', loading: false, status: 0 });
    expect(vi.getTimerCount()).toBe(0);
  });

  test('cleans up the deadline when fetcher throws synchronously', async () => {
    const { resource } = harness(() => 'initial');
    await resource.load(() => { throw new Error('synchronous failure'); });
    expect(resource).toMatchObject({ data: 'initial', loading: false, error: 'synchronous failure' });
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

describe('catalog API cancellation', () => {
  test.each(skillReads)('forwards %s options to fetch and cleans up on reset', async (_, path, read) => {
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

  test.each(['plugins', 'skills'])('rapid %s searches abort obsolete transports, not the latest read', async (kind) => {
    const requests = transport();
    const { resource } = harness<unknown>(() => ({ items: ['previous'] }));
    const search = (q: string) => resource.load((signal) => kind === 'plugins'
      ? api.get(`/api/v1/plugins?q=${q}`, { signal })
      : api.skills.list({ search: q }, { signal }));
    const first = search('f');
    const second = search('fo');
    const third = search('fox');
    expect(requests.map((item) => item.signal.aborted)).toEqual([true, true, false]);
    await Promise.all([first, second]);
    await flushPromises();
    expect(resource).toMatchObject({ data: { items: ['previous'] }, loading: true, error: '' });
    expect(routeBusy.value).toBe(true);
    expect(scrollRestorationBusy.value).toBe(true);
    expect(vi.getTimerCount()).toBe(2);
    requests[2].respond({ items: ['newest'], total: 1 });
    await third;
    expect(resource).toMatchObject({ data: { items: ['newest'], total: 1 }, loading: false, error: '' });
    expect(routeBusy.value).toBe(false);
    expect(scrollRestorationBusy.value).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });

  test('the shared 12s deadline remains a timeout error, aborts fetch and releases both timers', async () => {
    const requests = transport();
    const { resource } = harness<unknown>(() => 'retained data');
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
    expect(resource).toMatchObject({ data: 'retained data', loading: false, error: '请求超时，请重试。', status: 408 });
    expect(routeBusy.value).toBe(false);
    expect(scrollRestorationBusy.value).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
    const retry = resource.load((nextSignal) => api.get('/api/v1/plugins', { signal: nextSignal }));
    expect(requests[1].signal.aborted).toBe(false);
    requests[1].respond('retried');
    await retry;
    expect(resource).toMatchObject({ data: 'retried', loading: false, error: '', status: 0 });
    expect(vi.getTimerCount()).toBe(0);
  });

  test('an earlier API deadline is not silenced and clears the resource deadline', async () => {
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
  ])('keeps real HTTP %s visible', async (status, error) => {
    const requests = transport();
    const { resource } = harness<unknown>(() => 'retained data');
    const pending = resource.load((signal) => api.skills.get('fox', { signal }));
    requests[0].respond({ error: { message: 'server error' } }, status);
    await pending;
    expect(resource).toMatchObject({ data: 'retained data', loading: false, error, status });
    expect(vi.getTimerCount()).toBe(0);
    expect(routeBusy.value).toBe(false);
    expect(scrollRestorationBusy.value).toBe(false);
  });

  test('keeps a genuine network failure visible', async () => {
    const requests = transport();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true);
    const { resource } = harness<unknown>(() => null);
    const pending = resource.load((signal) => api.get('/api/v1/plugins', { signal }));
    requests[0].reject(new TypeError('Failed to fetch'));
    await pending;
    expect(resource).toMatchObject({ loading: false, error: '无法连接服务，请稍后重试。', status: 0 });
    expect(vi.getTimerCount()).toBe(0);
    expect(routeBusy.value).toBe(false);
    expect(scrollRestorationBusy.value).toBe(false);
  });

  test('unmount cancels catalog reads without canceling an independent mutation', async () => {
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
