import { createApp, nextTick } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';
import './assets/tokens.css';
import './assets/main.css';
import './assets/redesign.css';
import './assets/editorial.css';
import { failBoot, finishBoot } from './composables/useLoadingState';
import { installMarketTooltip } from './directives/marketTooltip';

async function startApp() {
  const app = createApp(App);
  app.use(createPinia());
  app.use(router);
  installMarketTooltip(app);
  app.mount('#app');
  await router.isReady();
  await nextTick();
  finishBoot();
}
void startApp().catch(failBoot);
