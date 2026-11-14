<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import { useAuthStore } from '@/stores/auth';
import AppIcon from './AppIcon.vue';
import FoxMark from './FoxMark.vue';
const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: [] }>();
const auth = useAuthStore();
const expanded = ref(false);
const dialog = ref<HTMLDialogElement | null>(null);
let previousFocus: HTMLElement | null = null;
const items = [
  { to: '/', label: '发现', en: 'DISCOVER', icon: 'home' },
  { to: '/browse', label: '插件目录', en: 'PLUGINS', icon: 'grid' },
  { to: '/skills', label: '技能市场', en: 'SKILLS', icon: 'skill' },
  { to: '/me', label: '我的工作台', en: 'WORKSPACE', icon: 'user' },
];
watch(
  () => props.open,
  async (open) => {
    await nextTick();
    if (open) {
      previousFocus = document.activeElement as HTMLElement;
      dialog.value?.showModal();
    } else {
      dialog.value?.close();
      previousFocus?.focus();
    }
  },
);
</script>
<template>
  <aside
    class="navigation-rail"
    :class="{ 'is-expanded': expanded }"
    aria-label="主导航"
  >
    <router-link to="/" class="rail-brand" aria-label="MoFox 首页"
      ><FoxMark :size="36" /><strong>MOFOX</strong></router-link
    >
    <button
      class="rail-expand"
      :aria-expanded="expanded"
      :aria-label="expanded ? '收起导航' : '展开导航'"
      @click="expanded = !expanded"
    >
      <AppIcon :name="expanded ? 'close' : 'menu'" :size="18" />
    </button>
    <nav class="rail-links">
      <router-link
        v-for="(item, i) in items"
        :key="item.to"
        :to="item.to"
        class="rail-link"
        v-market-tooltip:right="item.label"
        :exact-active-class="item.to === '/' ? 'is-active' : 'is-exact'"
        :active-class="item.to === '/' ? '' : 'is-active'"
        ><AppIcon :name="item.icon" /><span
          >{{ item.label }}<small>{{ item.en }}</small></span
        ><b>{{ String(i + 1).padStart(2, '0') }}</b></router-link
      >
    </nav>
    <div class="rail-bottom">
      <router-link
        v-if="auth.isAdmin"
        to="/admin"
        class="rail-link"
        v-market-tooltip:right="'管理后台'"
        ><AppIcon name="settings" /><span>管理后台</span></router-link
      ><router-link
        to="/status"
        class="rail-link"
        v-market-tooltip:right="'服务状态'"
        ><AppIcon name="status" /><span>服务状态</span></router-link
      ><span class="rail-caption" aria-hidden="true">OPEN POSSIBILITIES</span>
    </div>
  </aside>
  <dialog
    ref="dialog"
    class="mobile-navigation"
    aria-label="站点导航"
    @cancel.prevent="emit('close')"
    @click="
      (event) => {
        if (event.target === dialog) emit('close');
      }
    "
  >
    <div class="mobile-navigation__head">
      <FoxMark /><strong>MOFOX MARKET</strong
      ><button class="icon-button" aria-label="关闭导航" @click="emit('close')">
        <AppIcon name="close" />
      </button>
    </div>
    <nav>
      <router-link
        v-for="(item, i) in items"
        :key="item.to"
        :to="item.to"
        @click="emit('close')"
        ><small>0{{ i + 1 }}</small
        >{{ item.label }}<AppIcon name="arrow" /></router-link
      ><router-link to="/status" @click="emit('close')">服务状态</router-link
      ><router-link v-if="auth.isAdmin" to="/admin" @click="emit('close')"
        >管理后台</router-link
      >
    </nav>
  </dialog>
</template>
