<template>
  <footer class="app-footer">
    <div class="shell footer-inner">
      <div class="footer-brand">
        <img class="footer-logo" src="/logo.png" alt="Neo-MoFox">
        <div>
          <strong>Neo-MoFox</strong>
          <p>插件社区 · 基于开放治理中枢</p>
        </div>
      </div>
      <div class="footer-links">
        <a href="https://github.com/MoFox-Studio" target="_blank" rel="noreferrer noopener">GitHub</a>
        <router-link to="/admin">管理后台</router-link>
        <router-link to="/status">服务状态</router-link>
      </div>
    </div>
  </footer>
</template>

<style scoped>
.app-footer .footer-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.app-footer .footer-brand strong {
  display: block;
  color: #fff;
  font-family: var(--font-display);
  font-weight: 900;
  font-size: 15px;
}
.app-footer .footer-brand p {
  margin: 2px 0 0;
  color: var(--ink-300);
  font-size: 12.5px;
}
</style>
