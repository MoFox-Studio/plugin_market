<script setup lang="ts">
import CurationEditor from '@/components/CurationEditor.vue'
</script>

<template>
  <section class="admin-subview-stack">
    <div class="section-head compact-head">
      <div>
        <h2>精选配置</h2>
        <p>直接复用现有 CurationEditor，维护精选插件、作者和 hero 位。</p>
      </div>
    </div>
    <CurationEditor />
  </section>
</template>