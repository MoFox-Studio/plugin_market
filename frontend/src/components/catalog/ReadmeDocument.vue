<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
const props = defineProps<{ html?: string; source?: string; reservedIds?: string[] }>();
const route = useRoute();
const content = ref<HTMLElement | null>(null);
const headings = ref<{ id: string; text: string; level: number }[]>([]);
const open = ref(false);
function createSlugger() {
  const used = new Set([
    'overview',
    'readme',
    'versions',
    'comments',
    'dependencies',
    'maintainers',
    ...(props.reservedIds || []),
  ]);
  return (text: string) => {
    const base =
      text
        .toLocaleLowerCase()
        .trim()
        .replace(/[^\p{L}\p{N}\s_-]/gu, '')
        .replace(/\s/g, '-') || 'section';
    let id = base,
      index = 0;
    while (used.has(id)) id = `${base}-${++index}`;
    used.add(id);
    return id;
  };
}
// The Skill API supplies Markdown source. Keep its text exact and safe, while
// exposing actual heading anchors without executing embedded HTML.
const sourceLines = computed(() => {
  const slug = createSlugger();
  let fence = '';
  return (props.source || '').split('\n').map((text) => {
    const marker = text.match(/^\s*(`{3,}|~{3,})/)?.[1];
    if (marker) {
      if (!fence) fence = marker[0];
      else if (marker[0] === fence) fence = '';
      return { text, id: '', level: 0, title: '' };
    }
    const heading = !fence && text.match(/^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$/);
    const title = heading ? heading[2] : '';
    return {
      text,
      id: heading ? slug(title) : '',
      level: heading ? heading[1].length : 0,
      title,
    };
  });
});
const outline = computed(() =>
  props.html
    ? headings.value
    : sourceLines.value
        .filter((line) => line.id)
        .map((line) => ({ id: line.id, text: line.title, level: line.level })),
);
watch(
  () => props.html,
  async () => {
    await nextTick();
    if (!content.value) return;
    const slug = createSlugger();
    const entries = [...content.value.querySelectorAll<HTMLElement>('h1,h2,h3,h4,h5,h6')];
    const nestedDocument = entries.some((heading) => heading.tagName === 'H1');
    headings.value = entries.map((source) => {
      let heading = source;
      // The resource title owns the page's h1. Keep the README's internal hierarchy.
      if (nestedDocument) {
        const level = Math.min(6, Number(source.tagName[1]) + 1);
        heading = document.createElement(`h${level}`);
        heading.append(...source.childNodes);
        source.replaceWith(heading);
      }
      const text = heading.textContent || '';
      heading.id = slug(text);
      return { id: heading.id, text, level: Number(heading.tagName[1]) };
    });
  },
  { immediate: true, flush: 'post' },
);
</script>
<template>
  <div class="readme-document">
    <div v-if="outline.length" class="document-outline">
      <button type="button" :aria-expanded="open" @click="open = !open">
        <span
          >本文目录 <small>{{ outline.length }} 节</small></span
        ><span aria-hidden="true">{{ open ? '−' : '+' }}</span>
      </button>
      <nav v-if="open" aria-label="文档内章节">
        <router-link
          v-for="heading in outline"
          :key="heading.id"
          :to="{ path: route.path, query: route.query, hash: `#${heading.id}` }"
          :class="{ 'is-subheading': heading.level > 2 }"
          >{{ heading.text }}</router-link
        >
      </nav>
    </div>
    <!-- HTML is the backend's sanitized README response, never raw Markdown. -->
    <div v-if="html" ref="content" class="markdown-content" v-html="html"></div>
    <pre
      v-else
      class="document-source"
    ><code><span v-for="(line, index) in sourceLines" :key="index" :id="line.id || undefined" :class="{ 'source-heading': line.id }">{{ line.text || '\u200b' }}{{ index < sourceLines.length - 1 ? '\n' : '' }}</span></code></pre>
  </div>
</template>
<style scoped>
.document-outline {
  margin-bottom: 26px;
  border-block: 1px solid var(--line-strong);
  background: var(--surface-soft);
}
.document-outline > button {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  font-size: 12px;
  text-align: left;
}
.document-outline small {
  font: 8px var(--font-mono);
  margin-left: 10px;
  color: var(--ink-500);
}
.document-outline nav {
  display: grid;
  gap: 12px;
  padding: 6px 16px 18px;
}
.document-outline a {
  color: var(--blue-600);
  font-size: 12px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.document-outline .is-subheading {
  padding-left: 14px;
  border-left: 1px solid var(--line-strong);
}
.document-source {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
  padding: 20px;
  border: 1px solid var(--line);
  background: var(--surface-soft);
  font: 12px/1.95 var(--font-mono);
  color: var(--ink-700);
  tab-size: 2;
}
.document-source code {
  white-space: inherit;
  background: transparent;
  padding: 0;
  font: inherit;
}
.source-heading {
  color: var(--blue-700);
  font-weight: 600;
}
.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3) {
  font-family: var(--font-editorial, serif);
  margin-top: 1.8em;
  margin-bottom: 0.8em;
}
.markdown-content :deep(h1) {
  font-size: clamp(24px, 2.3vw, 32px);
}
.markdown-content :deep(h2) {
  font-size: clamp(21px, 2vw, 27px);
}
.markdown-content :deep(h3) {
  font-size: 19px;
}
.markdown-content :deep(blockquote) {
  margin: 20px 0;
  border-left: 3px solid var(--blue-500);
  padding: 6px 18px;
  background: var(--blue-50);
  color: var(--ink-500);
}
.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid var(--line);
  padding: 10px 14px;
}
.markdown-content :deep(th) {
  background: var(--surface-soft);
  text-align: left;
}
.markdown-content :deep(a) {
  color: var(--blue-600);
  text-decoration: underline;
  text-underline-offset: 3px;
}
</style>
