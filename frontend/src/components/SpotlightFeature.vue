<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import type { Plugin } from '@/types';
import { categoryLabel, formatNumber } from '@/utils/format';
import SpotlightPlate from './spotlight/SpotlightPlate.vue';
import { advancePlate, folios } from './spotlight/folioCatalogue';

const props = defineProps<{ items: Plugin[] }>();
const AUTOPLAY_DELAY_MS = 5000;
const index = ref(0);
const flipped = ref(false);
const root = ref<HTMLElement | null>(null);
const plateIndex = ref(Math.floor(Math.random() * folios.length));
const mounted = ref(false);
const hovered = ref(false);
const focused = ref(false);
const pageHidden = ref(false);
const inViewport = ref(false);
const reducedMotion = ref(false);
// null follows the system preference; the play control is an explicit override.
const manualPlayback = ref<boolean | null>(null);
const autoplayEnabled = computed(
  () => manualPlayback.value ?? !reducedMotion.value,
);
const current = computed(() => props.items[index.value] || props.items[0]);
const folio = computed(() => String(index.value + 1).padStart(2, '0'));
const category = computed(() =>
  categoryLabel(current.value?.categories?.[0] || 'other'),
);
const author = computed(
  () => current.value?.owner_display_name || current.value?.owner_login,
);
const canAutoplay = computed(
  () =>
    mounted.value &&
    props.items.length > 1 &&
    autoplayEnabled.value &&
    !hovered.value &&
    !focused.value &&
    !flipped.value &&
    !pageHidden.value &&
    inViewport.value,
);
const playbackLabel = computed(() => {
  if (!autoplayEnabled.value)
    return reducedMotion.value && manualPlayback.value === null
      ? '已按减少动态偏好暂停'
      : '自动切换已暂停';
  if (flipped.value) return '翻阅档案时暂停';
  if (hovered.value || focused.value) return '阅读时暂停自动切换';
  return '每 5 秒切换下一个精选';
});

let timer: ReturnType<typeof setTimeout> | null = null;
let viewportObserver: IntersectionObserver | null = null;
let motionMedia: MediaQueryList | null = null;
let motionObserver: MutationObserver | null = null;

function stopAutoplay() {
  if (timer !== null) clearTimeout(timer);
  timer = null;
}
function scheduleAutoplay() {
  stopAutoplay();
  if (!canAutoplay.value) return;
  timer = setTimeout(() => {
    timer = null;
    if (!canAutoplay.value) return;
    step(1);
    scheduleAutoplay();
  }, AUTOPLAY_DELAY_MS);
}
function step(delta: number) {
  index.value = (index.value + delta + props.items.length) % props.items.length;
  plateIndex.value = advancePlate(plateIndex.value, delta);
}
function change(delta: number) {
  if (props.items.length < 2) return;
  step(delta);
  flipped.value = false;
  scheduleAutoplay();
}
function togglePlayback() {
  manualPlayback.value = !autoplayEnabled.value;
}
function enter(event: PointerEvent) {
  if (event.pointerType !== 'touch') hovered.value = true;
}
function leaveRoot() {
  hovered.value = false;
}
function focusOut(event: FocusEvent) {
  focused.value =
    event.relatedTarget instanceof Node &&
    Boolean(root.value?.contains(event.relatedTarget));
}
function syncVisibility() {
  pageHidden.value = document.hidden;
}
function syncMotion() {
  reducedMotion.value =
    Boolean(motionMedia?.matches) ||
    document.documentElement.dataset.reducedMotion === 'reduce';
}

watch(canAutoplay, scheduleAutoplay, { flush: 'sync' });
watch(
  () => props.items,
  () => {
    index.value = 0;
    flipped.value = false;
    scheduleAutoplay();
  },
);
watch(() => props.items.length, scheduleAutoplay);
watch(root, (element, previous) => {
  if (viewportObserver) inViewport.value = false;
  if (previous) viewportObserver?.unobserve(previous);
  if (element) viewportObserver?.observe(element);
});
onMounted(() => {
  motionMedia = window.matchMedia?.('(prefers-reduced-motion: reduce)') || null;
  syncMotion();
  motionMedia?.addEventListener('change', syncMotion);
  motionObserver = new MutationObserver(syncMotion);
  motionObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-reduced-motion'],
  });
  syncVisibility();
  document.addEventListener('visibilitychange', syncVisibility);
  if (typeof IntersectionObserver !== 'undefined') {
    viewportObserver = new IntersectionObserver(
      (entries) => {
        const entry = entries.find((item) => item.target === root.value);
        if (entry)
          inViewport.value =
            entry.isIntersecting && entry.intersectionRatio >= 0.2;
      },
      { threshold: [0, 0.2] },
    );
    if (root.value) viewportObserver.observe(root.value);
  } else inViewport.value = true;
  mounted.value = true;
});
onBeforeUnmount(() => {
  mounted.value = false;
  stopAutoplay();
  viewportObserver?.disconnect();
  motionObserver?.disconnect();
  motionMedia?.removeEventListener('change', syncMotion);
  document.removeEventListener('visibilitychange', syncVisibility);
});
</script>
<template>
  <section
    v-if="current"
    ref="root"
    class="spotlight-section"
    aria-label="精选插件"
    aria-roledescription="轮播"
    @pointerenter="enter"
    @pointerleave="leaveRoot"
    @focusin="focused = true"
    @focusout="focusOut"
  >
    <header class="selection-heading">
      <p>01 / EDITOR’S SELECTION</p>
      <div><h2>值得一试</h2><span>精选作品</span></div>
      <router-link :to="{ name: 'market', query: { sort: 'popular' } }">浏览热门 ↗</router-link>
    </header>
  <article class="spotlight">
    <SpotlightPlate :plugin="current" :index="plateIndex" />
    <div class="spotlight-content">
      <div class="spotlight-top">
        <span class="eyebrow">{{ category }}</span><span
          >{{ folio }} /
          {{ String(items.length).padStart(2, '0') }}</span
        >
      </div>
      <div
        class="spotlight-flip"
        :class="{ 'is-flipped': flipped }"
        :aria-live="canAutoplay ? 'off' : 'polite'"
        aria-atomic="true"
      >
        <div class="spotlight-flip__inner">
          <div class="spotlight-front" :aria-hidden="flipped || undefined">
            <p v-if="author" class="spotlight-owner">
              {{ author }}
            </p>
            <h3>{{ current.display_name }}</h3>
            <p class="spotlight-summary">{{ current.summary }}</p>
          </div>
          <div class="spotlight-back" :aria-hidden="!flipped || undefined">
            <span class="eyebrow">PLUGIN DOSSIER</span>
            <h3>一份新的能力</h3>
            <dl>
              <div>
                <dt>最新版本</dt>
                <dd>{{ current.latest_version || '查看版本档案' }}</dd>
              </div>
              <div>
                <dt>社区下载</dt>
                <dd>{{ formatNumber(current.downloads_count) }}</dd>
              </div>
              <div>
                <dt>使用者评价</dt>
                <dd>
                  {{
                    current.rating_count
                      ? current.rating_avg.toFixed(1) + ' / 5'
                      : '暂无评分'
                  }}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </div>
      <div class="spotlight-actions">
        <router-link
          :to="'/plugin/' + encodeURIComponent(current.plugin_id)"
          class="btn btn-primary"
          >查看插件 ↗</router-link
        ><button
          class="spotlight-flip-toggle"
          :aria-pressed="flipped"
          @click="flipped = !flipped"
        >
          {{ flipped ? '查看用途' : '翻阅档案' }} ⤾
        </button>
      </div>
      <div class="spotlight-bottom">
        <span>{{
          items.length > 1 ? playbackLabel : '由社区创造，为你精选。'
        }}</span>
        <div class="spotlight-playback-controls">
          <button
            v-if="items.length > 1"
            type="button"
            class="spotlight-playback-toggle"
            aria-label="自动切换精选"
            :aria-pressed="autoplayEnabled"
            @click="togglePlayback"
          >
            {{ autoplayEnabled ? '暂停' : '继续' }}
          </button>
          <button
            class="icon-button"
            :disabled="items.length < 2"
            aria-label="上一个精选"
            @click="change(-1)"
          >
            ←</button
          ><button
            class="icon-button"
            :disabled="items.length < 2"
            aria-label="下一个精选"
            @click="change(1)"
          >
            →
          </button>
        </div>
      </div>
    </div>
  </article>
  </section>
</template>
<style scoped>
.spotlight {
  display: grid;
  grid-template-columns: 1.05fr 1fr;
  border: 1px solid var(--line);
  min-height: 390px;
}
.spotlight-content {
  display: flex;
  flex-direction: column;
  padding: 28px 32px;
  background: var(--surface);
  min-width: 0;
}
.spotlight-top {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  font: 9px var(--font-mono);
  color: var(--ink-500);
  border-bottom: 3px double var(--line-strong);
  padding-bottom: 9px;
}
.spotlight-flip {
  perspective: 1400px;
  flex: 1;
  min-height: 210px;
  margin: 24px 0;
}
.spotlight-flip__inner {
  position: relative;
  transform-style: preserve-3d;
  transition: transform 650ms cubic-bezier(0.22, 1, 0.36, 1);
  min-height: 210px;
}
.is-flipped .spotlight-flip__inner {
  transform: rotateX(180deg);
}
.spotlight-front,
.spotlight-back {
  backface-visibility: hidden;
}
.spotlight-back {
  position: absolute;
  inset: 0;
  transform: rotateX(180deg);
}
.spotlight-owner {
  font: 11px var(--font-mono);
  color: var(--ink-500);
  margin: 0 0 16px;
}
.spotlight-content h3 {
  font-family: var(--font-editorial, Georgia, serif);
  overflow-wrap: anywhere;
  font-size: clamp(24px, 2.4vw, 36px);
  line-height: 1.25;
  letter-spacing: -0.04em;
  margin: 0 0 20px;
}
.spotlight-summary {
  font-size: 13px;
  line-height: 1.8;
  color: var(--ink-500);
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.spotlight-back h3 {
  font-size: 22px;
  margin: 12px 0;
}
.spotlight-back dl {
  font-size: 12px;
  margin: 0;
}
.spotlight-back dl > div {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--line);
}
.spotlight-back dt {
  color: var(--ink-500);
}
.spotlight-back dd {
  font-family: var(--font-mono);
}
.spotlight-actions {
  display: flex;
  align-items: center;
  gap: 24px;
}
.spotlight-flip-toggle {
  font-size: 12px;
  color: var(--ink-500);
}
.spotlight-bottom {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  font-size: 10px;
  color: var(--ink-500);
}
.spotlight-bottom > div {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  gap: 4px;
}
.spotlight-playback-toggle {
  min-width: 44px;
  min-height: 36px;
  padding: 8px;
  margin-right: 6px;
  font: inherit;
  color: var(--ink-700);
  border: 1px solid var(--line);
  border-radius: 3px;
}
.spotlight-playback-toggle:hover {
  border-color: var(--blue-500);
  color: var(--blue-700);
}
@media (max-width: 900px) {
  .spotlight {
    grid-template-columns: 0.8fr 1fr;
  }
  .spotlight-content {
    padding: 24px;
  }
}
@media (max-width: 600px) {
  .spotlight {
    grid-template-columns: 1fr;
  }
  .spotlight-content { padding: 24px; }
  .spotlight-flip, .spotlight-flip__inner { min-height: 190px; }
  .spotlight-summary { -webkit-line-clamp: 3; }
  .spotlight-content h3 { font-size: clamp(25px, 6vw, 34px); }
  .spotlight-bottom { flex-wrap: wrap; }
}
.selection-heading {
  display: grid;
  grid-template-columns: minmax(0,1fr) auto;
  align-items: end;
  gap: 12px 18px;
  padding: 20px 0 23px;
  border-top: 3px double var(--ink-500);
}
.selection-heading p {
  grid-column: 1/-1;
  margin: 0;
  font: 600 10px/1.5 var(--font-mono);
  color: var(--blue-700);
  letter-spacing: .13em;
}
.selection-heading > div { display: flex; align-items: baseline; gap: 12px; }
.selection-heading h2 { font: 800 clamp(28px, 3vw, 44px)/1.15 var(--font-editorial); margin: 0; }
.selection-heading span, .selection-heading a { font-size: 12px; color: var(--ink-500); }
.selection-heading a:hover { color: var(--blue-700); }
@media (max-width: 600px) {
  .selection-heading { padding-block: 16px; }
  .selection-heading > div { align-items: start; flex-direction: column; gap: 6px; }
}
@media (prefers-reduced-motion: reduce) {
  .spotlight-flip__inner { transition: none; }
}
:global(:root[data-reduced-motion='reduce'] .spotlight-flip__inner) { transition: none; }
</style>
