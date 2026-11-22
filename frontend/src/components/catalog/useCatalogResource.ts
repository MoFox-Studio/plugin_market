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
  function reset() {
    attempt++;
    state.data = initial();
    state.loading = false;
    state.error = '';
    state.status = 0;
  }
  async function load(fetcher: () => Promise<T>) {
    const current = ++attempt;
    state.loading = true;
    state.error = '';
    state.status = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      const result = await Promise.race([
        fetcher(),
        new Promise<never>((_, reject) => {
          timer = setTimeout(
            () => reject(new Error('请求超时，请重试。')),
            12000,
          );
        }),
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
      if (timer) clearTimeout(timer);
      if (current === attempt) state.loading = false;
    }
  }
  onBeforeUnmount(() => {
    attempt++;
  });
  return Object.assign(state, { load, reset });
}
