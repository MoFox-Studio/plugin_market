<script setup lang="ts">
import { useRoute } from 'vue-router';
defineProps<{
  active: string;
  versions?: number;
  comments?: number;
  kind?: string;
  documentLabel?: string;
}>();
const route = useRoute();
const chapters = [
  { id: 'overview', label: '档案概览', number: 'Ⅰ' },
  { id: 'readme', label: '使用文档', number: 'Ⅱ' },
  { id: 'versions', label: '版本记录', number: 'Ⅲ' },
  { id: 'comments', label: '社区讨论', number: 'Ⅳ' },
];
</script>
<template>
  <nav class="dossier-navigation" :aria-label="`${kind || '资源'}详情章节`">
    <span class="dossier-navigation__label">篇目</span>
    <router-link
      v-for="chapter in chapters"
      :key="chapter.id"
      :to="{ path: route.path, query: route.query, hash: `#${chapter.id}` }"
      :class="{ active: active === chapter.id }"
      :aria-current="active === chapter.id ? 'location' : undefined"
    >
      <span class="dossier-navigation__number" aria-hidden="true">{{ chapter.number }}</span>
      <span class="dossier-navigation__copy"><strong>{{ chapter.id === 'readme' && documentLabel ? documentLabel : chapter.label }}</strong></span>
      <span
        v-if="chapter.id === 'versions' && versions !== undefined"
        class="dossier-navigation__count"
        >{{ versions }}</span
      >
      <span
        v-if="chapter.id === 'comments' && comments !== undefined"
        class="dossier-navigation__count"
        >{{ comments }}</span
      >
    </router-link>
  </nav>
</template>
<style scoped>
.dossier-navigation {
  position: sticky;
  top: var(--topbar-h, 64px);
  z-index: 12;
  display: grid;
  grid-template-columns: 76px repeat(4, minmax(0, 1fr));
  background: var(--surface);
  border-block: 3px double var(--ink-500);
  min-width: 0;
}
.dossier-navigation__label {
  display: grid;
  align-content: center;
  gap: 5px;
  padding: 14px 18px;
  font: 600 14px/1.5 var(--font-editorial, serif);
  color: var(--ink-500);
  border-right: 1px solid var(--line);
}
.dossier-navigation a {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 15px 18px;
  color: var(--ink-500);
  min-width: 0;
  border-right: 1px solid var(--line-soft);
}
.dossier-navigation a:last-child {
  border: 0;
}
.dossier-navigation a::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 3px;
  background: transparent;
}
.dossier-navigation a:hover {
  background: var(--surface-soft);
  color: var(--ink-900);
}
.dossier-navigation a.active {
  background: var(--blue-50);
  color: var(--blue-700);
}
.dossier-navigation a.active::after {
  background: var(--blue-500);
}
.dossier-navigation__number {
  font: italic 400 14px var(--font-editorial, serif);
  opacity: 0.7;
}
.dossier-navigation__copy {
  display: grid;
  gap: 5px;
  min-width: 0;
}
.dossier-navigation__copy strong {
  font: 700 15px var(--font-editorial, serif);
  white-space: nowrap;
}
.dossier-navigation__count {
  margin-left: auto;
  font: 10px var(--font-mono);
}
@media (max-width: 1100px) {
  .dossier-navigation {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
  .dossier-navigation__label {
    display: none;
  }
  .dossier-navigation a {
    padding: 15px 12px;
    gap: 8px;
  }
}
@media (max-width: 620px) {
  .dossier-navigation {
    margin-inline: -16px;
    border-left: 0;
    border-right: 0;
  }
  .dossier-navigation a {
    padding: 13px 8px;
    gap: 6px;
    justify-content: center;
  }
  .dossier-navigation__copy strong {
    font-size: 13px;
  }
  .dossier-navigation__count {
    display: none;
  }
  .dossier-navigation__number {
    font-size: 9px;
  }
}

@media(min-width: 1181px) {
  .dossier-navigation { display: flex; flex-direction: column; top: calc(var(--topbar-h, 64px) + 18px); padding: 2px 0 12px; border: 0; background: transparent; }
  .dossier-navigation__label { display: block; border: 0; padding: 0 0 12px; margin-bottom: 6px; color: var(--blue-700); font: 11px var(--font-sans); letter-spacing: .12em; }
  .dossier-navigation a { gap: 7px; padding: 10px 3px; border: 0; }
  .dossier-navigation__copy strong { font-size: 13px; }
  .dossier-navigation__number { min-width: 13px; font-size: 11px; }
  .dossier-navigation__count { display: none; }
  .dossier-navigation a.active { background: transparent; }
  .dossier-navigation a.active::after { top: 8px; bottom: 8px; left: -6px; right: auto; width: 2px; height: auto; }
}
</style>
