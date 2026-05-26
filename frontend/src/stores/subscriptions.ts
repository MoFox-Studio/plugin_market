import { reactive } from 'vue'
import { defineStore } from 'pinia'

/**
 * Lightweight reactive overrides for plugin subscription state.
 *
 * When a subscription is toggled outside of PluginCard (e.g. Me page),
 * we record the new state here so every PluginCard instance can react
 * without re-fetching data from the server.
 */
export const useSubscriptionStore = defineStore('subscriptions', () => {
  const overrides = reactive<Record<string, boolean>>({})

  function set(pluginId: string, subscribed: boolean) {
    overrides[pluginId] = subscribed
  }

  function get(pluginId: string): boolean | undefined {
    return overrides[pluginId]
  }

  function $reset() {
    Object.keys(overrides).forEach((k) => delete overrides[k])
  }

  return { overrides, set, get, $reset }
})
