<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import StatusView from './StatusView.vue';
import InboxView from './InboxView.vue';
defineProps<{ title: string; description?: string }>();
const route = useRoute();
const type = computed(() => String(route.name || ''));
</script>
<template>
  <StatusView v-if="type === 'admin-system'" /><InboxView
    v-else-if="type === 'admin-inbox'"
  />
  <section v-else class="admin-unavailable">
    <h1 class="desk-title">{{ title }}</h1>
    <p>
      独立版本治理模块尚未开放。现有插件审核与治理可在插件治理页面处理；自己发布的版本可在工作台维护。
    </p>
    <div>
      <RouterLink class="btn btn-primary" to="/admin/plugins"
        >插件治理 →</RouterLink
      ><RouterLink class="btn" to="/me">我的工作台</RouterLink>
    </div>
  </section>
</template>
<style scoped>
.admin-unavailable {
  display: grid;
  justify-items: start;
  gap: 18px;
  border-block: 3px double var(--line-strong);
  background: var(--surface);
  padding: 36px;
  border-radius: 0;
}
.admin-unavailable p {
  margin: 0;
  max-width: 560px;
  line-height: 1.9;
  color: var(--ink-500);
}
.admin-unavailable > div {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
</style>
