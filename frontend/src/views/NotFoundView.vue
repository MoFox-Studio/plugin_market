<script setup lang="ts">
import { useRoute } from 'vue-router';
const route = useRoute();
</script>
<template>
  <section class="page-wrap missing-page">
    <div class="missing-rule"><b>市场索引</b><span>缺页记录</span></div>
    <div class="missing-spread">
      <div class="missing-story">
        <span class="missing-code">404</span>
        <h1>未找到这一页</h1>
        <p>这个地址没有对应的页面。可以检查链接，或从目录重新查找作品。</p>
        <dl class="missing-address"><dt>请求地址</dt><dd><code>{{ route.path }}</code></dd></dl>
        <RouterLink class="btn btn-primary" to="/browse">浏览插件目录 →</RouterLink>
      </div>
      <aside class="missing-index" aria-label="继续浏览">
        <h2>翻到其他栏目</h2>
        <RouterLink to="/"><span>发现首页</span><small>社区精选与最新作品</small><i aria-hidden="true">↗</i></RouterLink>
        <RouterLink to="/skills"><span>Skill 目录</span><small>查找可安装的技能包</small><i aria-hidden="true">↗</i></RouterLink>
      </aside>
    </div>
  </section>
</template>
<style scoped>
.missing-page { min-height: min(640px, 75dvh); }
.missing-rule { display: flex; justify-content: space-between; padding: 9px 0; border-top: 2px solid var(--ink-900); border-bottom: 1px solid var(--line-strong); font-size: 11px; letter-spacing: .13em; }
.missing-rule b { color: var(--blue-700); }
.missing-spread { display: grid; align-items: start; grid-template-columns: minmax(0, 2.25fr) minmax(200px, 1fr); gap: clamp(28px, 6vw, 88px); padding: clamp(38px, 7vw, 92px) 0; border-bottom: 3px double var(--ink-700); }
.missing-code { display: inline-block; color: var(--blue-700); font: 800 26px/1 var(--font-editorial); padding: 5px 9px; border: 1px solid currentColor; }
.missing-story h1 { margin: 18px 0; font: 800 clamp(42px, 6vw, 86px)/1.15 var(--font-editorial); letter-spacing: -.05em; }
.missing-story p { margin: 0; max-width: 36em; color: var(--ink-700); line-height: 1.85; }
.missing-address { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 12px; align-items: baseline; margin: 22px 0; padding: 13px 0; border-block: 1px solid var(--line); font-size: 12px; }
.missing-address dt { color: var(--ink-500); }
.missing-address dd { margin: 0; overflow-wrap: anywhere; }
.missing-address code { padding: 0; background: none; }
.missing-index { margin-top: 12px; border-top: 2px solid var(--ink-700); background: var(--surface); padding: 16px 18px 0; }
.missing-index h2 { margin: 0 0 15px; font: 800 20px/1.35 var(--font-editorial); }
.missing-index a { position: relative; display: grid; gap: 5px; padding: 14px 25px 14px 0; border-top: 1px solid var(--line); }
.missing-index span { font-weight: 650; }
.missing-index small { color: var(--ink-500); font-size: 12px; }
.missing-index i { position: absolute; top: 14px; right: 0; font-style: normal; color: var(--blue-700); }
@media (max-width: 720px) {
  .missing-spread { grid-template-columns: 1fr; }
  .missing-index { margin-top: 0; }
}
</style>
