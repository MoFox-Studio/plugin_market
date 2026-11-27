<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import AppIcon from './AppIcon.vue';

const router = useRouter();
const query = ref('');
function search() {
  const q = query.value.trim();
  void router.push({ name: 'market', query: q ? { q } : {} });
}
</script>

<template>
  <div class="home-finder">
    <form
      class="finder-form"
      role="search"
      aria-label="首页插件搜索"
      @submit.prevent="search"
    >
      <AppIcon name="search" :size="18" />
      <input
        v-model="query"
        type="search"
        name="q"
        aria-label="搜索插件名称或功能"
        placeholder="插件名或功能"
      />
      <button type="submit">搜索插件 <AppIcon name="arrow" :size="15" /></button>
    </form>
    <nav class="finder-entries" aria-label="插件入口">
      <router-link class="finder-all" to="/browse">
        <span class="finder-all-label"
          ><AppIcon name="grid" :size="18" /><span>全部插件</span></span
        ><AppIcon name="arrow" :size="17" />
      </router-link>
    </nav>
  </div>
</template>

<style scoped>
.home-finder {
  max-width: 430px;
  min-width: 0;
}
.finder-form {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 6px 7px 6px 14px;
  background: var(--surface);
  color: var(--ink-500);
  border: 1px solid var(--line-strong);
  border-left: 3px solid var(--blue-700);
  box-shadow: var(--shadow-1);
}
.finder-form:focus-within {
  outline: 2px solid var(--blue-500);
  outline-offset: 2px;
}
.finder-form input {
  min-width: 0;
  width: 100%;
  height: 38px;
  padding: 0;
  border: 0;
  outline: 0;
  color: var(--ink-900);
  background: transparent;
  font: 500 16px/1.5 var(--font-sans);
}
.finder-form button {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  justify-content: center;
  min-height: 42px;
  padding: 0 14px;
  border: 0;
  border-radius: var(--radius-sm);
  background: var(--blue-700);
  color: var(--ink-on-blue);
  font: 700 15px/1.3 var(--font-sans);
  white-space: nowrap;
}
.finder-form input::placeholder {
  color: var(--ink-700);
  opacity: 1;
}
.finder-form button:hover { background: var(--blue-900); }
.finder-entries {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 11px;
  margin-top: 14px;
}
.finder-entries > a {
  display: inline-flex;
  align-items: center;
  min-width: 0;
  color: var(--ink-900);
  font-family: var(--font-sans);
  text-decoration: none;
  white-space: nowrap;
}
.finder-entries .finder-all {
  justify-content: space-between;
  gap: 14px;
  min-height: 54px;
  padding-inline: 16px;
  border: 1px solid var(--blue-700);
  border-radius: var(--radius-sm);
  background: var(--blue-700);
  color: var(--ink-on-blue);
  font-size: 16px;
  font-weight: 700;
  box-shadow: var(--shadow-1);
}
.finder-all-label {
  display: inline-flex;
  align-items: center;
  gap: 9px;
}
.finder-entries .finder-all:hover {
  background: var(--blue-900);
  color: var(--ink-on-blue);
}
.finder-entries .finder-all:focus-visible {
  outline: 3px solid var(--blue-500);
  outline-offset: 3px;
}
@media (max-width: 700px) {
  .finder-form input {
    height: 44px;
    font-size: 16px;
  }
  .finder-form {
    gap: 6px;
    padding: 3px 4px 3px 9px;
  }
  .finder-form button {
    min-height: 44px;
    gap: 4px;
    padding-inline: 10px;
  }
  .finder-entries {
    gap: 9px;
    margin-top: 9px;
  }
  .finder-entries .finder-all {
    min-height: 50px;
    gap: 6px;
    padding-inline: 12px;
  }
}
</style>
