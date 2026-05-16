<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import type { Announcement } from '@/types'

const props = defineProps<{
  announcement: Announcement
}>()

const emit = defineEmits<{
  (e: 'dismiss', announcement: Announcement): void
  (e: 'close', announcement: Announcement): void
}>()

const dialogRef = ref<HTMLElement | null>(null)

const actionLabel = computed(() => props.announcement.dismissible ? '知道了，不再提示' : '关闭')

function focusableNodes(): HTMLElement[] {
  if (!dialogRef.value) {
    return []
  }
  return Array.from(
    dialogRef.value.querySelectorAll<HTMLElement>('button, a[href], [tabindex]:not([tabindex="-1"])')
  ).filter((node) => !node.hasAttribute('disabled'))
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.preventDefault()
    if (props.announcement.dismissible) {
      emit('dismiss', props.announcement)
      return
    }
    emit('close', props.announcement)
    return
  }

  if (event.key !== 'Tab') {
    return
  }

  const focusables = focusableNodes()
  if (!focusables.length) {
    return
  }

  const first = focusables[0]
  const last = focusables[focusables.length - 1]
  const active = document.activeElement as HTMLElement | null

  if (event.shiftKey && active === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && active === last) {
    event.preventDefault()
    first.focus()
  }
}

watch(() => props.announcement.id, async () => {
  if (typeof document === 'undefined') {
    return
  }
  document.body.classList.add('modal-open')
  document.addEventListener('keydown', onKeydown)
  await nextTick()
  const initial = dialogRef.value?.querySelector<HTMLElement>('[data-modal-initial-focus]')
  initial?.focus()
}, { immediate: true })

onBeforeUnmount(() => {
  if (typeof document === 'undefined') {
    return
  }
  document.body.classList.remove('modal-open')
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="announcement-modal-backdrop" @click.self="$emit('close', announcement)">
    <section ref="dialogRef" class="announcement-modal" role="dialog" aria-modal="true" :aria-labelledby="`announcement-modal-title-${announcement.id}`">
      <div class="announcement-modal-head">
        <span class="announcement-modal-kicker" :class="`is-${announcement.severity}`">{{ announcement.severity }}</span>
        <button type="button" class="btn btn-ghost btn-sm" aria-label="关闭公告" @click="$emit('close', announcement)">关闭</button>
      </div>
      <div class="announcement-modal-body">
        <h2 :id="`announcement-modal-title-${announcement.id}`">{{ announcement.title }}</h2>
        <p>{{ announcement.body_markdown }}</p>
      </div>
      <div class="announcement-modal-actions">
        <button
          type="button"
          class="btn btn-primary"
          data-modal-initial-focus
          @click="announcement.dismissible ? $emit('dismiss', announcement) : $emit('close', announcement)"
        >
          {{ actionLabel }}
        </button>
      </div>
    </section>
  </div>
</template>