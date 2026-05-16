<script setup lang="ts">
const props = defineProps<{
  title: string
  description: string
  note?: string
}>()
</script>

<template>
  <section class="panel admin-placeholder-view">
    <div class="section-head compact-head">
      <div>
        <h2>{{ props.title }}</h2>
        <p>{{ props.description }}</p>
      </div>
      <span class="badge trust-community">即将接入</span>
    </div>
    <p class="soft-note">{{ props.note || '这个分区的具体功能将在后续任务中替换掉当前占位页。' }}</p>
  </section>
</template>