<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { formatNumber } from '@/utils/format'
import type { CurationEntry } from '@/types'

const props = defineProps<{
  items: CurationEntry[]
}>()

const router = useRouter()
const slides = computed(() => props.items.slice(0, 5))
const activeIndex = ref(0)
const paused = ref(false)
const reducedMotion = ref(false)

const cardRef = ref<HTMLElement | null>(null)
const tiltX = ref(0)
const tiltY = ref(0)

let autoplayId: number | null = null
let motionMedia: MediaQueryList | null = null

function syncMotion(): void {
  reducedMotion.value =
    Boolean(motionMedia?.matches) ||
    document.documentElement.dataset.reducedMotion === 'reduce'
}

function stopAutoplay(): void {
  if (autoplayId !== null) {
    window.clearInterval(autoplayId)
    autoplayId = null
  }
}

function startAutoplay(): void {
  stopAutoplay()
  if (!slides.value.length || reducedMotion.value || paused.value) return
  autoplayId = window.setInterval(() => {
    activeIndex.value = (activeIndex.value + 1) % slides.value.length
  }, 4500)
}

function goTo(idx: number): void {
  activeIndex.value = (idx + slides.value.length) % slides.value.length
}

function gotoSlide(): void {
  const slide = slides.value[activeIndex.value]
  if (!slide) return
  if (slide.plugin?.plugin_id) {
    void router.push({ name: 'plugin', params: { id: slide.plugin.plugin_id } })
    return
  }
  if (slide.author?.author_id) {
    void router.push({ name: 'author', params: { id: slide.author.author_id } })
    return
  }
  if (slide.target_type === 'plugin' && slide.target_id) {
    void router.push({ name: 'plugin', params: { id: slide.target_id } })
    return
  }
  if (slide.target_type === 'author' && slide.target_id) {
    void router.push({ name: 'author', params: { id: slide.target_id } })
  }
}

function handlePointer(e: PointerEvent): void {
  if (reducedMotion.value || !cardRef.value) return
  const rect = cardRef.value.getBoundingClientRect()
  const x = (e.clientX - rect.left) / rect.width - 0.5
  const y = (e.clientY - rect.top) / rect.height - 0.5
  tiltX.value = -y * 4
  tiltY.value = x * 6
}
function resetTilt(): void { tiltX.value = 0; tiltY.value = 0 }

watch([slides, reducedMotion, paused], () => startAutoplay())

onMounted(() => {
  if (typeof window === 'undefined') return
  motionMedia = window.matchMedia('(prefers-reduced-motion: reduce)')
  syncMotion()
  motionMedia.addEventListener('change', syncMotion)
  startAutoplay()
})

onBeforeUnmount(() => {
  stopAutoplay()
  motionMedia?.removeEventListener('change', syncMotion)
})

const current = computed(() => slides.value[activeIndex.value])
const heroTitle = computed(() => current.value?.plugin?.display_name || current.value?.author?.display_name || current.value?.target_id || '')
const heroSummary = computed(() => current.value?.plugin?.summary || '')
const heroOwner = computed(() => {
  const slide = current.value
  if (!slide) return null
  if (slide.author) return slide.author
  if (slide.plugin) {
    return {
      author_id: slide.plugin.owner_id,
      display_name: slide.plugin.owner_display_name || slide.plugin.owner_login || slide.plugin.owner_id,
      github_login: slide.plugin.owner_login || slide.plugin.owner_id,
      avatar_url: slide.plugin.owner_avatar_url,
    }
  }
  return null
})
const heroSignature = computed(() => current.value?.signature_plugin || current.value?.plugin)

const tiltStyle = computed(() => ({
  transform: `perspective(1100px) rotateX(${tiltX.value}deg) rotateY(${tiltY.value}deg)`,
}))
</script>

<template>
  <section
    v-if="current"
    ref="cardRef"
    class="hero-poster"
    :class="{ 'is-paused': paused }"
    :style="tiltStyle"
    @mouseenter="paused = true"
    @mouseleave="paused = false; resetTilt()"
    @pointermove="handlePointer"
    @focusin="paused = true"
    @focusout="paused = false"
  >
    <transition name="hero-fade" mode="out-in">
      <div :key="activeIndex" class="hero-poster-content">
        <div class="hero-poster-eyebrow">
          <span class="num">{{ String(activeIndex + 1).padStart(2, '0') }}</span>
          <span>FEATURED</span>
          <span class="of">/ {{ String(slides.length).padStart(2, '0') }}</span>
        </div>

        <h2 class="hero-poster-title">{{ heroTitle }}</h2>
        <p v-if="heroSummary" class="hero-poster-summary">{{ heroSummary }}</p>

        <div v-if="heroOwner" class="hero-poster-by">
          <span class="av" aria-hidden="true">
            <img v-if="heroOwner.avatar_url" :src="heroOwner.avatar_url" :alt="heroOwner.display_name">
            <template v-else>{{ heroOwner.display_name?.[0]?.toUpperCase() || '?' }}</template>
          </span>
          <span class="text">
            <b>@{{ heroOwner.github_login }}</b>
            <span class="meta" v-if="heroSignature && heroSignature !== current.plugin">代表作 · {{ heroSignature.display_name }}</span>
          </span>
        </div>

        <div v-if="current.plugin" class="hero-poster-stats">
          <span><b>{{ current.plugin.rating_avg.toFixed(1) }}</b><small>评分</small></span>
          <span><b>{{ formatNumber(current.plugin.downloads_count) }}</b><small>下载</small></span>
          <span><b>{{ formatNumber(current.plugin.likes_count) }}</b><small>订阅</small></span>
          <span v-if="current.plugin.latest_version"><b>v{{ current.plugin.latest_version }}</b><small>最新</small></span>
        </div>

        <div class="hero-poster-actions">
          <button type="button" class="btn btn-primary" @click="gotoSlide">查看详情</button>
          <button type="button" class="btn btn-ghost" @click="paused = !paused" :aria-pressed="paused">
            {{ paused ? '▶ 继续轮播' : '❚❚ 暂停' }}
          </button>
        </div>
      </div>
    </transition>

    <div class="hero-poster-dots" role="tablist" aria-label="精选切换">
      <button
        v-for="(slide, idx) in slides"
        :key="slide.id || idx"
        type="button"
        :aria-current="idx === activeIndex ? 'true' : undefined"
        :aria-label="`切到第 ${idx + 1} 张`"
        @click="goTo(idx)"
      ></button>
    </div>
  </section>
</template>

<style scoped>
.hero-poster {
  position: relative;
  background: linear-gradient(135deg, var(--blue-700) 0%, var(--blue-500) 100%);
  color: #fff;
  border-radius: var(--radius-lg);
  overflow: hidden;
  min-height: 440px;
  padding: var(--space-8);
  display: grid;
  align-content: end;
  gap: var(--space-3);
  box-shadow: var(--shadow-poster);
  isolation: isolate;
  transition: transform var(--dur-slow) var(--ease-emphasized);
  will-change: transform;
}
.hero-poster.is-paused { transform: perspective(1100px) rotateX(0) rotateY(0) !important; }

.hero-poster::before {
  content: ""; position: absolute; inset: 0;
  background: var(--halftone);
  opacity: 0.18; mix-blend-mode: screen;
  pointer-events: none; z-index: 0;
}
.hero-poster::after {
  content: ""; position: absolute;
  left: 0; right: 0; bottom: 0;
  height: 56px;
  background: var(--paper);
  clip-path: polygon(0 100%, 100% 100%, 100% 0, 0 80%);
  z-index: 1;
  pointer-events: none;
  transition: height var(--dur-slow) var(--ease-emphasized),
              clip-path var(--dur-slow) var(--ease-emphasized),
              background var(--dur-slow);
}
.hero-poster:hover::after {
  /* hover 时斜切高度抬高，角度反向，制造一次撕开动作 */
  height: 84px;
  clip-path: polygon(0 100%, 100% 100%, 100% 32%, 0 86%);
  background: linear-gradient(180deg, var(--lemon) 0%, var(--paper) 100%);
}

.hero-poster-content {
  position: relative; z-index: 2;
  display: grid; gap: var(--space-3);
}

.hero-poster-eyebrow {
  display: flex; align-items: center; gap: 12px;
  font-family: var(--font-brand);
  letter-spacing: var(--letter-kicker);
  font-size: 12px;
  opacity: 0.92;
}
.hero-poster-eyebrow .num {
  display: grid; place-items: center;
  width: 36px; height: 36px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  font-family: var(--font-display);
  font-weight: 900; font-size: 15px;
  letter-spacing: 0;
}
.hero-poster-eyebrow .of { opacity: 0.6; }

.hero-poster-title {
  margin: 0;
  font-family: var(--font-display);
  font-weight: 900;
  font-size: clamp(32px, 4.4vw, 48px);
  line-height: 1.05;
  letter-spacing: -0.012em;
}

.hero-poster-summary {
  margin: 0;
  font-size: 15px; line-height: 1.6;
  max-width: 56ch;
  opacity: 0.94;
}

.hero-poster-by {
  display: flex; align-items: center; gap: 10px;
  font-size: 13px;
}
.hero-poster-by .av {
  width: 34px; height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--lemon), var(--coral));
  display: grid; place-items: center;
  color: var(--ink-900);
  font-family: var(--font-display);
  font-weight: 800; font-size: 13px;
  border: 2px solid #fff;
  flex: 0 0 auto;
  overflow: hidden;
}
.hero-poster-by .av img { width: 100%; height: 100%; object-fit: cover; }
.hero-poster-by .text { display: flex; flex-direction: column; gap: 2px; }
.hero-poster-by b {
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--lemon);
}
.hero-poster-by .meta { color: rgba(255, 255, 255, 0.78); font-size: 12px; }

.hero-poster-stats {
  display: flex; gap: var(--space-6);
  font-family: var(--font-mono);
  font-size: 12px; letter-spacing: 0.04em;
}
.hero-poster-stats span { display: grid; gap: 2px; }
.hero-poster-stats b {
  font-family: var(--font-brand);
  font-size: 22px; letter-spacing: 0.06em;
  color: var(--lemon);
}
.hero-poster-stats small { font-size: 11px; opacity: 0.82; }

.hero-poster-actions {
  display: flex; gap: var(--space-2);
  margin-top: var(--space-3);
  position: relative;
  z-index: 4;
}
.hero-poster-actions .btn {
  transform: none;
}
.hero-poster-actions .btn:hover,
.hero-poster-actions .btn:active {
  transform: none;
}
.hero-poster-actions .btn-primary {
  background: #fff; color: var(--blue-700); border-color: #fff;
}
.hero-poster-actions .btn-primary:hover {
  background: var(--lemon); border-color: var(--lemon); color: var(--ink-900);
}
.hero-poster-actions .btn-ghost { color: rgba(255, 255, 255, 0.92); }
.hero-poster-actions .btn-ghost:hover { background: rgba(255, 255, 255, 0.14); color: #fff; }

.hero-poster-dots {
  position: absolute;
  bottom: 18px; right: var(--space-7);
  display: flex; gap: 6px;
  z-index: 3;
}
.hero-poster-dots button {
  width: 22px; height: 5px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.36);
  transition: width var(--dur-base) var(--ease-emphasized), background var(--dur-fast);
}
.hero-poster-dots button:hover { background: rgba(255, 255, 255, 0.62); }
.hero-poster-dots button[aria-current="true"] { width: 36px; background: var(--lemon); }

/* Slide transitions */
.hero-fade-enter-active, .hero-fade-leave-active {
  transition: opacity var(--dur-base) var(--ease-emphasized),
              transform var(--dur-base) var(--ease-emphasized);
}
.hero-fade-enter-from { opacity: 0; transform: translate3d(28px, 0, 0); }
.hero-fade-leave-to   { opacity: 0; transform: translate3d(-28px, 0, 0); }

@media (max-width: 768px) {
  .hero-poster { min-height: 360px; padding: var(--space-6); }
  .hero-poster-stats { gap: var(--space-3); flex-wrap: wrap; }
}

@media (prefers-reduced-motion: reduce) {
  .hero-poster { transition: none; transform: none !important; }
  .hero-poster::after { transition: none; }
  .hero-poster:hover::after { height: 56px; clip-path: polygon(0 100%, 100% 100%, 100% 0, 0 80%); background: var(--paper); }
  .hero-fade-enter-active, .hero-fade-leave-active { transition: opacity var(--dur-base); }
  .hero-fade-enter-from, .hero-fade-leave-to { transform: none; }
}
</style>
