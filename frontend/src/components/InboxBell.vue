<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useInboxStore } from '@/stores/inbox'
import InboxList from '@/components/InboxList.vue'

const inbox = useInboxStore()

const open = ref(false)
const panelRef = ref<HTMLElement | null>(null)

async function toggleOpen(): Promise<void> {
  open.value = !open.value
  if (open.value) {
    await inbox.loadMessages({ offset: 0, limit: 20 })
    await nextTick()
    panelRef.value?.querySelector<HTMLElement>('[data-inbox-initial-focus]')?.focus()
  }
}

function closeDrawer(): void {
  open.value = false
}

function onDocumentClick(event: MouseEvent): void {
  if (!open.value || !panelRef.value) {
    return
  }
  if (panelRef.value.contains(event.target as Node)) {
    return
  }
  closeDrawer()
}

function onDocumentKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    closeDrawer()
  }
}

watch(open, (value) => {
  if (typeof document === 'undefined') {
    return
  }
  if (value) {
    document.addEventListener('click', onDocumentClick)
    document.addEventListener('keydown', onDocumentKeydown)
    return
  }
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onDocumentKeydown)
})

onBeforeUnmount(() => {
  if (typeof document === 'undefined') {
    return
  }
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onDocumentKeydown)
})
</script>

<template>
  <div ref="panelRef" class="inbox-bell-shell">
    <button
      type="button"
      class="inbox-bell"
      :class="{ 'is-open': open }"
      aria-label="打开信箱"
      :aria-expanded="open"
      @click.stop="toggleOpen"
    >
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M15 17h5l-1.4-1.4A2 2 0 0 1 18 14.2V11a6 6 0 1 0-12 0v3.2a2 2 0 0 1-.6 1.4L4 17h5" />
        <path d="M9.5 17a2.5 2.5 0 0 0 5 0" />
      </svg>
      <span class="inbox-bell-label">信箱</span>
      <span v-if="inbox.hasUnread" class="inbox-bell-badge">{{ inbox.unreadBadge }}</span>
    </button>

    <transition name="inbox-drawer">
      <section v-if="open" class="inbox-drawer" aria-label="最近信箱消息">
        <div class="inbox-drawer-head">
          <div>
            <span class="inbox-drawer-kicker">Inbox</span>
            <strong>最近 20 条消息</strong>
          </div>
          <button type="button" class="btn btn-ghost btn-sm" data-inbox-initial-focus @click="closeDrawer">关闭</button>
        </div>
        <InboxList eager @navigated="closeDrawer" />
      </section>
    </transition>
  </div>
</template>