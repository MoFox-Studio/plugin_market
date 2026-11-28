<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import type { ContentScrollRailItem } from '@/types/contentScrollRail';

const props = withDefaults(
  defineProps<{
    items: ContentScrollRailItem[];
    ariaLabel?: string;
  }>(),
  { ariaLabel: '页面分段导航' },
);

const route = useRoute();
const router = useRouter();
const activeId = ref(props.items[0]?.id || '');
let observer: IntersectionObserver | null = null;
let scrollFrame: number | null = null;
let reducedMotion = false;

function requestFrame(callback: FrameRequestCallback) {
  if (typeof window.requestAnimationFrame === 'function')
    return window.requestAnimationFrame(callback);
  return window.setTimeout(() => callback(performance.now()), 16);
}

function cancelFrame(frameId: number) {
  if (typeof window.cancelAnimationFrame === 'function') {
    window.cancelAnimationFrame(frameId);
  } else {
    window.clearTimeout(frameId);
  }
}

function updateFromViewport() {
  if (!props.items.length) return;
  const anchor = window.innerHeight * 0.3;
  let candidate = props.items[0];

  for (const item of props.items) {
    const section = document.getElementById(item.id);
    if (!section) continue;
    if (section.getBoundingClientRect().top <= anchor + 28) candidate = item;
  }

  if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 4) {
    candidate = props.items[props.items.length - 1];
  }
  activeId.value = candidate.id;
}

function scheduleViewportUpdate() {
  if (scrollFrame !== null) return;
  scrollFrame = requestFrame(() => {
    scrollFrame = null;
    updateFromViewport();
  });
}

function goTo(item: ContentScrollRailItem, event: MouseEvent) {
  const section = document.getElementById(item.id);
  if (!section) return;
  event.preventDefault();
  activeId.value = item.id;
  void router
    .replace({
      path: route.path,
      query: route.query,
      hash: `#${item.id}`,
    })
    .then(() => {
      section.focus({ preventScroll: true });
      section.scrollIntoView({
        behavior: reducedMotion ? 'auto' : 'smooth',
        block: 'start',
      });
    });
}

function setupObserver() {
  observer?.disconnect();
  observer = null;
  const sections = props.items
    .map((item) => document.getElementById(item.id))
    .filter((section): section is HTMLElement => Boolean(section));
  if (typeof IntersectionObserver === 'function' && sections.length) {
    observer = new IntersectionObserver(() => scheduleViewportUpdate(), {
      rootMargin: '-18% 0px -58% 0px',
      threshold: [0, 0.2, 0.6, 1],
    });
    sections.forEach((section) => observer?.observe(section));
  }
  scheduleViewportUpdate();
}

watch(
  () => props.items.map((item) => item.id).join('|'),
  async () => {
    await nextTick();
    activeId.value = props.items[0]?.id || '';
    setupObserver();
  },
);

onMounted(async () => {
  reducedMotion =
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  await nextTick();
  setupObserver();
  window.addEventListener('scroll', scheduleViewportUpdate, { passive: true });
  window.addEventListener('resize', scheduleViewportUpdate, { passive: true });
});

onBeforeUnmount(() => {
  observer?.disconnect();
  observer = null;
  window.removeEventListener('scroll', scheduleViewportUpdate);
  window.removeEventListener('resize', scheduleViewportUpdate);
  if (scrollFrame !== null) cancelFrame(scrollFrame);
});
</script>

<template>
  <nav class="content-scroll-rail" :aria-label="ariaLabel">
    <div class="content-scroll-rail__list">
      <a
        v-for="(item, index) in items"
        :key="item.id"
        class="content-scroll-rail__item"
        :class="{ 'is-active': activeId === item.id }"
        :href="`#${item.id}`"
        :aria-current="activeId === item.id ? 'location' : undefined"
        @click="goTo(item, $event)"
        @focus="activeId = item.id"
      >
        <span class="content-scroll-rail__tick" aria-hidden="true" />
        <span class="content-scroll-rail__index" aria-hidden="true">
          {{ String(index + 1).padStart(2, '0') }}
        </span>
        <span class="content-scroll-rail__copy">
          <span class="content-scroll-rail__label">{{ item.label }}</span>
        </span>
      </a>
    </div>
  </nav>
</template>

<style scoped>
.content-scroll-rail {
  position: sticky;
  top: calc(var(--topbar-h, 64px) + 24px);
  align-self: start;
  min-width: 0;
  color: var(--ink-700);
}
.content-scroll-rail__list {
  position: relative;
  display: grid;
  gap: 18px;
  min-width: 0;
  padding: 10px 0 18px 32px;
}
.content-scroll-rail__list::before {
  content: '';
  position: absolute;
  top: 8px;
  bottom: 8px;
  left: 8px;
  width: 1px;
  background: var(--line-strong);
}
.content-scroll-rail__item {
  position: relative;
  display: grid;
  gap: 4px;
  min-width: 0;
  color: var(--ink-500);
  text-decoration: none;
  transition: color var(--dur-fast) var(--ease-standard);
}
.content-scroll-rail__item:hover,
.content-scroll-rail__item:focus-visible,
.content-scroll-rail__item.is-active {
  color: var(--blue-700);
}
.content-scroll-rail__tick {
  position: absolute;
  top: 9px;
  left: -32px;
  width: 26px;
  height: 1px;
  background: var(--line-strong);
}
.content-scroll-rail__item.is-active .content-scroll-rail__tick {
  background: var(--blue-500);
}
.content-scroll-rail__index {
  color: var(--ink-300);
  font: 10px/1 var(--font-mono);
  letter-spacing: 0.04em;
  font-variant-numeric: tabular-nums;
}
.content-scroll-rail__copy {
  display: block;
  min-width: 0;
}
.content-scroll-rail__label {
  max-width: 7em;
  overflow-wrap: anywhere;
  font: 600 12px/1.45 var(--font-reading);
}
.content-scroll-rail__item.is-active .content-scroll-rail__index {
  color: var(--blue-700);
}
.content-scroll-rail__item.is-active .content-scroll-rail__label {
  font-weight: 700;
}
@supports (scroll-target-group: auto) {
  .content-scroll-rail__list {
    scroll-target-group: auto;
  }
}
@supports selector(a:target-current) {
  .content-scroll-rail__item:target-current {
    color: var(--blue-700);
    font-weight: 700;
    text-decoration: underline;
    text-decoration-thickness: 1px;
    text-underline-offset: 3px;
  }
}
.content-scroll-rail__item:focus-visible {
  outline: 2px solid var(--blue-500);
  outline-offset: 5px;
}
@media (max-width: 980px) {
  .content-scroll-rail {
    position: sticky;
    top: var(--topbar-h, 64px);
    z-index: 60;
    padding-block: 5px;
    border-bottom: 1px solid var(--line);
    background: var(--paper);
  }
  .content-scroll-rail__list {
    display: flex;
    gap: clamp(14px, 4vw, 24px);
    overflow-x: auto;
    overscroll-behavior-x: contain;
    padding: 7px 0 9px;
    scrollbar-width: thin;
  }
  .content-scroll-rail__list::before {
    top: auto;
    bottom: 0;
    left: 0;
    width: 100%;
    height: 1px;
  }
  .content-scroll-rail__item {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: center;
    flex: none;
    gap: 7px;
    padding-block: 2px 4px;
  }
  .content-scroll-rail__tick {
    top: auto;
    bottom: -10px;
    left: 0;
    width: 24px;
    height: 2px;
  }
  .content-scroll-rail__index {
    font-size: 9px;
  }
  .content-scroll-rail__copy {
    display: block;
    transform: none;
  }
  .content-scroll-rail__label {
    max-width: none;
    font-size: 11px;
    white-space: nowrap;
  }
}
@media (prefers-reduced-motion: reduce) {
  .content-scroll-rail__item,
  .content-scroll-rail__copy {
    transition: none;
  }
}
</style>
