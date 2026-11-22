<script setup lang="ts">
defineProps<{ title: string; description: string }>();
</script>

<template>
  <header class="catalog-masthead">
    <div class="masthead-title">
      <p class="masthead-section">社区资源目录</p>
      <h1>{{ title }}</h1>
      <p class="masthead-description">{{ description }}</p>
    </div>
    <div class="masthead-search"><slot /></div>
  </header>
</template>

<style scoped>
.catalog-masthead {
  display: grid;
  grid-template-columns: minmax(225px, .7fr) minmax(0, 1.3fr);
  align-items: center;
  gap: clamp(24px, 4vw, 68px);
  padding: clamp(18px, 3vw, 36px) 0;
  border-bottom: 4px double var(--ink-500);
}
.masthead-section { margin: 0; color: var(--blue-700); font-size: 12px; letter-spacing: .14em; }
.masthead-title h1 { margin: 6px 0 14px; font: 800 clamp(40px, 5vw, 70px)/1.15 var(--font-editorial); color: var(--ink-900); }
.masthead-description { margin: 0; max-width: 28em; color: var(--ink-700); font: 400 15px/1.8 var(--font-reading); }
.masthead-search { min-width: 0; border-left: 1px solid var(--line-strong); padding-left: clamp(18px, 3vw, 38px); }
@media (max-width: 900px) {
  .catalog-masthead { grid-template-columns: 1fr; gap: 20px; }
  .masthead-search { border: 0; padding: 0; }
}
</style>
