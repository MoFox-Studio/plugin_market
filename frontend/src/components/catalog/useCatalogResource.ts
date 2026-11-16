import { onBeforeUnmount, shallowReactive } from 'vue';
import { ApiError } from '@/api';

/** Only the newest attempt may update a region, including after a route change. */
export function useCatalogResource<T>(initial: () => T) {
  const state = shallowReactive({
    data: initial(),
    loading: false,
    error: '',
    status: 0,
  });
  let attempt = 0;
  let cancelPending: (() => void) | undefined;
  function invalidate() {
    attempt++;
    cancelPending?.();
    cancelPending = undefined;
  }
  function reset() {
    invalidate();
    state.data = initial();
    state.loading = false;
    state.error = '';
    state.status = 0;
  }
  async function load(fetcher: (signal: AbortSignal) => Promise<T>) {
    invalidate();
    const current = attempt;
    const controller = new AbortController();
    state.loading = true;
    state.error = '';
    state.status = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const interrupted = new Promise<never>((_, reject) => {
      cancelPending = () => {
        clearTimeout(timer);
        reject(new DOMException('请求已取消。', 'AbortError'));
        controller.abort();
      };
      // Start before fetcher/API timers, and reject before aborting the transport.
      // A timeout must remain an error even when abort immediately rejects fetch.
      timer = setTimeout(() => {
        reject(new ApiError('请求超时，请重试。', 408, 'REQUEST_TIMEOUT'));
        controller.abort();
      }, 12000);
    });
    try {
      const result = await Promise.race([
        interrupted,
        fetcher(controller.signal),
      ]);
      if (current === attempt) state.data = result;
    } catch (error) {
      if (current !== attempt) return;
      state.status = error instanceof ApiError ? error.status : 0;
      state.error =
        state.status === 404
          ? '该资源不存在或已不可访问。'
          : state.status === 403
            ? '你暂时没有访问权限。'
            : error instanceof Error
              ? error.message
              : '暂时无法加载，请重试。';
    } finally {
      clearTimeout(timer);
      if (current === attempt) {
        cancelPending = undefined;
        state.loading = false;
      }
    }
  }
  onBeforeUnmount(() => {
    invalidate();
    state.loading = false;
  });
  return Object.assign(state, { load, reset });
}
