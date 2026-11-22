import { onScopeDispose, readonly, shallowRef, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

interface DialogRequest {
  owner: symbol;
  mode: 'confirm' | 'prompt';
  message: string;
  initialValue: string;
  resolve: (value: string | boolean | null) => void;
}
const current = shallowRef<DialogRequest | null>(null);
export const marketDialog = readonly(current);

export function settleMarketDialog(value: string | boolean | null) {
  const request = current.value;
  current.value = null;
  request?.resolve(value);
}

/** A pending decision belongs to its page and identity, never to a later account. */
export function useMarketDialog() {
  const owner = Symbol('market-dialog-owner');
  const route = useRoute(),
    auth = useAuthStore();
  let revision = 0,
    disposed = false;
  function cancel() {
    revision++;
    if (current.value?.owner === owner) settleMarketDialog(null);
  }
  watch(() => [route.fullPath, auth.viewer?.author_id], cancel, {
    flush: 'sync',
  });
  onScopeDispose(() => {
    disposed = true;
    cancel();
  });
  async function ask(
    mode: 'confirm' | 'prompt',
    message: string,
    initialValue = '',
  ) {
    if (disposed) return null;
    // Replace a duplicate click, rather than queuing a stale destructive action.
    settleMarketDialog(null);
    const version = revision;
    const result = await new Promise<string | boolean | null>((resolve) => {
      current.value = { owner, mode, message, initialValue, resolve };
    });
    return !disposed && version === revision ? result : null;
  }
  return {
    confirm: async (message: string) =>
      (await ask('confirm', message)) === true,
    prompt: async (message: string, initialValue = '') => {
      const result = await ask('prompt', message, initialValue);
      return typeof result === 'string' ? result : null;
    },
  };
}
