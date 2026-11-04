<script setup lang="ts">
import FoxMark from './FoxMark.vue';
</script>
<template>
  <footer class="market-footer">
    <div class="footer-identity">
      <FoxMark :size="26" /><strong>MoFox</strong>
      <i class="footer-signature" lang="en" aria-hidden="true">The Gazette</i>
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
    <p>MOFOX STUDIO · BUILT FOR THE OPEN COMMUNITY</p>
  </footer>
</template>
