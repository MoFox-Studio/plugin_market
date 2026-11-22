<script setup lang="ts">
withDefaults(
  defineProps<{ type?: 'cards' | 'detail' | 'rows'; count?: number }>(),
  { type: 'cards', count: 6 },
);
</script>
<template>
  <div
    class="page-skeleton"
    :class="'page-skeleton--' + type"
    role="status"
    aria-label="正在加载内容"
  >
    <span class="sr-only">正在加载内容</span>
    <div
      v-for="i in count"
      :key="i"
      class="page-skeleton__item"
      aria-hidden="true"
    >
      <i class="skeleton page-skeleton__icon"></i><span class="skeleton"></span
      ><span class="skeleton"></span><span class="skeleton"></span>
    </div>
  </div>
</template>
<style scoped>
.page-skeleton {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
.page-skeleton__item {
  min-height: 224px;
  padding: 24px;
  border: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.page-skeleton__item > span {
  height: 12px;
  width: 90%;
}
.page-skeleton__item > span:last-child {
  width: 50%;
}
.page-skeleton__icon {
  width: 44px;
  height: 44px;
  display: block;
  margin-bottom: 12px;
}
.page-skeleton--rows {
  grid-template-columns: 1fr;
}
.page-skeleton--rows .page-skeleton__item {
  min-height: 88px;
  display: grid;
  grid-template-columns: 44px 1fr 1fr;
  align-items: center;
}
.page-skeleton--rows .page-skeleton__item > span:last-child {
  display: none;
}
.page-skeleton--detail {
  grid-template-columns: 1fr;
}
.page-skeleton--detail .page-skeleton__item {
  min-height: 200px;
}
@media (max-width: 900px) {
  .page-skeleton {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .page-skeleton--rows,
  .page-skeleton--detail {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 560px) {
  .page-skeleton {
    grid-template-columns: 1fr;
  }
}
</style>
