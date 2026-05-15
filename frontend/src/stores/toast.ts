import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useToastStore = defineStore('toast', () => {
  const message = ref('')
  const kind = ref('')
  const visible = ref(false)
  let timer: ReturnType<typeof setTimeout> | null = null

  function show(msg: string, type = ''): void {
    message.value = msg
    kind.value = type
    visible.value = true
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => { visible.value = false }, 2600)
  }

  return { message, kind, visible, show }
})
