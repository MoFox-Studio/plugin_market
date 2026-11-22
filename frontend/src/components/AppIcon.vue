<script setup lang="ts">
withDefaults(defineProps<{ name: string; size?: number }>(), { size: 20 });
// Search/GitHub and the three statistics icons retain the exact deployed SVG
// geometry from AppHeader.vue and PluginCard.vue in the original source.
const originalStats = new Set(['bookmark', 'download', 'comment']);
const paths: Record<string, string> = {
  home: 'm3 10 9-7 9 7v10H3Z M9 20v-7h6v7',
  grid: 'M3 3h7v7H3Z M14 3h7v7h-7Z M3 14h7v7H3Z M14 14h7v7h-7Z',
  skill: 'm13 2-9 12h7l-1 8 10-13h-7Z',
  user: 'M20 21v-3a5 5 0 0 0-5-5H9a5 5 0 0 0-5 5v3 M16 6a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  status: 'M2 12h4l3-8 6 16 3-8h4',
  settings: 'M4 6h16M4 12h16M4 18h16 M8 3v6M16 9v6M10 15v6',
  arrow: 'M4 12h16m-6-6 6 6-6 6',
  sun: 'M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1 M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  moon: 'M20 15A9 9 0 0 1 9 3a9 9 0 1 0 11 12',
  menu: 'M3 6h18M3 12h18M3 18h18',
  close: 'm6 6 12 12M18 6 6 18',
  bookmark: 'M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1z',
  book: 'M12 5.5C9 3.5 5.5 3.4 2.5 4.5v14c3-1.1 6.5-1 9.5 1 3-2 6.5-2.1 9.5-1v-14C18.5 3.4 15 3.5 12 5.5Zm0 0v14',
  comment: 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z',
  github:
    'M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12',
};
</script>
<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    :fill="name === 'github' ? 'currentColor' : 'none'"
    :stroke="name === 'github' ? undefined : 'currentColor'"
    :stroke-width="
      name === 'github'
        ? undefined
        : name === 'search' || originalStats.has(name)
          ? 2
          : 1.5
    "
    :stroke-linecap="
      name === 'github' || originalStats.has(name) ? undefined : 'round'
    "
    :stroke-linejoin="
      name === 'github' || originalStats.has(name) ? undefined : 'round'
    "
    aria-hidden="true"
  >
    <template v-if="name === 'search'">
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </template>
    <template v-else-if="name === 'download'">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </template>
    <path v-else :d="paths[name] || paths.grid" />
  </svg>
</template>
