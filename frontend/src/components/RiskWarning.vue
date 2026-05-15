<script setup lang="ts">
defineProps({
  kind: { type: String, default: 'panel' },
})
</script>

<template>
  <div :class="['risk-warning', `risk-warning-${kind}`]" role="alert">
    <strong>风险提示</strong>
    <p>所有插件均为用户自行上传，可能存在安全风险。下载或使用前，请务必确认你信任该插件，并已阅读其源码。</p>
    <p>因插件使用造成的任何损失，MoFox-Studio 不承担责任。</p>
  </div>
</template>
