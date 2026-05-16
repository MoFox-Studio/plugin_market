<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Plugin } from '@/types'
import PluginCard from '@/components/PluginCard.vue'

const props = defineProps<{
  items: Plugin[]
}>()

const railRef = ref<HTMLElement | null>(null)
const activeIndex = ref(0)
const paused = ref(false)
const reducedMotion = ref(false)
const isMobile = ref(false)

let autoplayId: number | null = null
let motionMedia: MediaQueryList | null = null
let mobileMedia: MediaQueryList | null = null

const slides = computed(() => props.items.slice(0, 6))

function syncMediaState(): void {
  reducedMotion.value = Boolean(motionMedia?.matches) || document.documentElement.dataset.reducedMotion === 'reduce'
  isMobile.value = Boolean(mobileMedia?.matches)
}

function goTo(index: number): void {
  if (!slides.value.length) {
    activeIndex.value = 0
    return
  }
  activeIndex.value = (index + slides.value.length) % slides.value.length
  if (isMobile.value && railRef.value) {
    const target = railRef.value.children.item(activeIndex.value) as HTMLElement | null
    target?.scrollIntoView({ behavior: reducedMotion.value ? 'auto' : 'smooth', inline: 'start', block: 'nearest' })
  }
}

function next(): void {
  goTo(activeIndex.value + 1)
}

function previous(): void {
  goTo(activeIndex.value - 1)
}

function stopAutoplay(): void {
  if (autoplayId !== null) {
    window.clearInterval(autoplayId)
    autoplayId = null
  }
}

function startAutoplay(): void {
  stopAutoplay()
  if (!slides.value.length || reducedMotion.value || paused.value || isMobile.value) {
    return
  }
  autoplayId = window.setInterval(() => {
    next()
  }, 6000)
}

watch([slides, reducedMotion, paused, isMobile], () => {
  startAutoplay()
})

onMounted(() => {
  if (typeof window === 'undefined') {
    return
  }
  motionMedia = window.matchMedia('(prefers-reduced-motion: reduce)')
  mobileMedia = window.matchMedia('(max-width: 767px)')
  syncMediaState()
  motionMedia.addEventListener('change', syncMediaState)
  mobileMedia.addEventListener('change', syncMediaState)
  startAutoplay()
})

onBeforeUnmount(() => {
  stopAutoplay()
  motionMedia?.removeEventListener('change', syncMediaState)
  mobileMedia?.removeEventListener('change', syncMediaState)
})
</script>

<template>
  <section v-if="slides.length" class="featured-showcase" @mouseenter="paused = true" @mouseleave="paused = false" @focusin="paused = true" @focusout="paused = false">
    <div class="section-head featured-showcase-head">
      <div>
        <h2>精选展示</h2>
        <p>桌面自动轮播，移动端横向滑动浏览。</p>
      </div>
      <div class="featured-showcase-controls">
        <button class="btn btn-ghost btn-sm" type="button" @click="previous">Prev</button>
        <button class="btn btn-ghost btn-sm" type="button" @click="next">Next</button>
      </div>
    </div>

    <div class="featured-showcase-viewport">
      <div ref="railRef" class="featured-showcase-rail" :style="!isMobile ? { transform: `translateX(-${activeIndex * 100}%)` } : undefined">
        <article v-for="plugin in slides" :key="plugin.plugin_id" class="featured-showcase-slide">
          <PluginCard :plugin="plugin" />
        </article>
      </div>
    </div>

    <div class="featured-showcase-dots">
      <button v-for="(plugin, index) in slides" :key="plugin.plugin_id" type="button" :class="['featured-showcase-dot', { 'is-active': index === activeIndex }]" :aria-label="`跳转到 ${plugin.display_name}`" @click="goTo(index)"></button>
    </div>
  </section>
</template>