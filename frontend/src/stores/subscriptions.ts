import { reactive } from 'vue'
import { defineStore } from 'pinia'

/**
 * 插件订阅状态的轻量响应式覆盖层。
 *
 * 在 PluginCard 之外（例如工作台页面）切换订阅时，
 * 在此记录新状态，让所有 PluginCard 实例同步响应，
 * 无需重新向服务器请求数据。
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
