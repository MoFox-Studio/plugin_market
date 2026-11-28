/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PREVIEW_MOCK?: string
  readonly VITE_ROUTER_MODE?: string
  readonly VITE_PR_NUMBER?: string
  readonly VITE_PR_URL?: string
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
