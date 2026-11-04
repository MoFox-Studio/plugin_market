<script setup lang="ts">
import { computed } from 'vue';
import type { Plugin } from '@/types';
import AppIcon from './AppIcon.vue';
import EditionArtwork from './EditionArtwork.vue';
import { categoryLabel } from '@/utils/format';

const props = defineProps<{ candidates: Plugin[] }>();
const entries = computed(() => {
  const seen = new Set<string>();
  return props.candidates
    .flatMap((item) => {
      if (
        item.status !== 'published' ||
        !item.plugin_id ||
        !item.display_name?.trim() ||
        seen.has(item.plugin_id)
      )
        return [];
      seen.add(item.plugin_id);
      const parts = item.display_name.split(/\s+·\s+/);
      const title = parts.length === 2 ? parts[1] : item.display_name;
      const caption =
        parts.length === 2 ? parts[0] : categoryLabel(item.categories?.[0]);
      return [
        {
          item,
          title,
          caption,
          path: '/plugin/' + encodeURIComponent(item.plugin_id),
        },
      ];
    })
    .slice(0, 2);
});
</script>
<template>
  <section
    v-if="entries.length"
    class="plugin-shelf"
    aria-labelledby="shelf-title"
  >
    <header>
      <span aria-hidden="true" lang="en">INDEX</span>
      <h2 id="shelf-title">插件速览</h2>
    </header>
    <ul>
      <li v-for="entry in entries" :key="entry.item.plugin_id">
        <router-link
          class="sample-work"
          :to="entry.path"
          :aria-label="'查看插件：' + entry.item.display_name"
        >
          <span class="sample-art" aria-hidden="true"
            ><EditionArtwork
              :icon="entry.item.icon_url"
              :categories="entry.item.categories"
              :tags="entry.item.tags"
          /></span>
          <span class="sample-title"
            ><strong>{{ entry.title }}</strong
            ><small>{{ entry.caption }}</small></span
          >
        </router-link>
        <div class="sample-tools">
          <router-link
            :to="{ path: entry.path, hash: '#usage' }"
            :aria-label="entry.item.display_name + '：查看说明'"
            ><AppIcon name="book" :size="17" /><span>说明</span></router-link
          >
          <router-link
            :to="{ path: entry.path, hash: '#get' }"
            :aria-label="entry.item.display_name + '：获取插件'"
            ><AppIcon name="download" :size="17" /><span
              >获取</span
            ></router-link
          >
        </div>
      </li>
    </ul>
  </section>
</template>
<style scoped>
.plugin-shelf {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: stretch;
  margin-top: clamp(18px, 2.2vw, 32px);
  border-block: 3px double var(--ink-500);
  background: var(--surface);
}
.plugin-shelf header {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 3px;
  padding: 14px clamp(14px, 1.8vw, 30px) 14px 0;
  background: var(--paper);
}
.plugin-shelf header > span {
  color: var(--blue-700);
  font: 600 10px/1 var(--font-mono);
  letter-spacing: 0.15em;
}
.plugin-shelf h2 {
  margin: 0;
  font: 800 clamp(17px, 1.5vw, 23px) / 1.4 var(--font-editorial);
}
.plugin-shelf ul {
  display: grid;
  grid-auto-columns: minmax(0, 1fr);
  grid-auto-flow: column;
  margin: 0;
  padding: 0;
  list-style: none;
}
.plugin-shelf li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  min-width: 0;
  padding: 7px clamp(8px, 1.3vw, 24px);
  border-left: 1px solid var(--line-strong);
}
.sample-work {
  display: flex;
  align-items: center;
  gap: clamp(6px, 1vw, 16px);
  flex: 1;
  min-height: 48px;
  min-width: 0;
  padding-block: 4px;
}
.sample-work:hover strong,
.sample-work:focus-visible strong {
  color: var(--blue-700);
  text-decoration: underline;
  text-underline-offset: 4px;
}
.sample-art {
  display: grid;
  place-items: center;
  width: clamp(40px, 4.5vw, 72px);
  height: clamp(40px, 4.4vw, 64px);
  flex-shrink: 0;
  background: var(--surface-soft);
  color: var(--blue-700);
}
.sample-art :deep(.edition-engraving small) {
  display: none;
}
.sample-art :deep(.edition-art-icon) {
  width: 80%;
  height: 80%;
}
.sample-title {
  display: grid;
  gap: 3px;
  min-width: 0;
}
.sample-title strong,
.sample-title small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sample-title strong {
  color: var(--ink-900);
  font: 800 clamp(16px, 1.6vw, 23px) / 1.3 var(--font-editorial);
}
.sample-title small {
  color: var(--ink-500);
  font: italic 12px/1.35 var(--font-reading);
}
.sample-tools {
  display: flex;
  border-left: 1px solid var(--line);
  padding-left: 4px;
}
.sample-tools a {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 4px;
  min-width: 44px;
  min-height: 44px;
  color: var(--blue-700);
  font: 600 11px/1.3 var(--font-sans);
}
.sample-tools a:hover,
.sample-tools a:focus-visible {
  color: var(--ink-900);
  background: var(--surface-soft);
}
@media (max-width: 940px) {
  .plugin-shelf {
    grid-template-columns: 1fr;
  }
  .plugin-shelf header {
    flex-direction: row;
    align-items: baseline;
    justify-content: flex-start;
    gap: 8px;
    padding: 6px 0;
    background: var(--paper);
    border-bottom: 1px solid var(--line);
  }
  .plugin-shelf header > span {
    order: 1;
  }
  .plugin-shelf h2 {
    font-size: 16px;
  }
  .plugin-shelf li:first-child {
    border-left: 0;
  }
}
@media (max-width: 700px) {
  .plugin-shelf {
    margin-top: 14px;
  }
  .plugin-shelf ul {
    grid-auto-flow: row;
  }
  .plugin-shelf li {
    border-left: 0;
    padding: 2px 4px;
  }
  .plugin-shelf li + li {
    border-top: 1px solid var(--line);
  }
  .sample-work {
    gap: 10px;
  }
  .sample-art {
    width: 44px;
    height: 38px;
  }
}
</style>
