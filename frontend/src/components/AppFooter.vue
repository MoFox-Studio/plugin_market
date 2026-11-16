<script setup lang="ts">
import FoxMark from './FoxMark.vue';
</script>
<template>
  <footer class="market-footer">
    <div class="footer-identity">
      <FoxMark :size="26" /><strong>MoFox</strong>
      <i class="footer-signature" lang="zh-CN" aria-hidden="true">市场报</i>
      <span>把可能，变成能力。</span>
    </div>
    <nav aria-label="页脚导航">
      <a
        href="https://github.com/MoFox-Studio"
        target="_blank"
        rel="noopener noreferrer"
        >GitHub ↗</a
      ><router-link to="/browse">插件目录</router-link
      ><router-link to="/status">服务状态</router-link>
    </nav>
    <p>MOFOX STUDIO · 为开放社区而建</p>
  </footer>
</template>
