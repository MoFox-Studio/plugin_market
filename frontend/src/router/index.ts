import { createRouter, createWebHistory } from 'vue-router';
import type { RouteLocationNormalized, RouteRecordRaw } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import {
  startNavigation,
  finishNavigation,
  navigationEpoch,
} from '@/composables/useLoadingState';
import { keepsReadingPosition, restoreRouteScroll } from '@/composables/useScrollRestoration';

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { shellGroup: 'home' },
  },
  {
    path: '/browse',
    name: 'market',
    component: () => import('@/views/MarketView.vue'),
    meta: { shellGroup: 'market' },
  },
  {
    path: '/plugin/:id',
    name: 'plugin',
    component: () => import('@/views/PluginDetailView.vue'),
    props: true,
    meta: { shellGroup: 'market' },
  },
  {
    path: '/me',
    name: 'me',
    component: () => import('@/views/MeView.vue'),
    meta: { shellGroup: 'me' },
  },
  {
    path: '/me/profile',
    name: 'me-profile',
    component: () => import('@/views/MeProfileView.vue'),
    meta: { shellGroup: 'me' },
  },
  {
    path: '/inbox',
    name: 'inbox',
    component: () => import('@/views/InboxView.vue'),
    meta: { shellGroup: 'me' },
  },
  {
    path: '/status',
    name: 'status',
    component: () => import('@/views/StatusView.vue'),
    meta: { shellGroup: 'market' },
  },
  {
    path: '/skills',
    name: 'skills',
    component: () => import('@/views/SkillMarketView.vue'),
    meta: { shellGroup: 'market' },
  },
  {
    path: '/skill/:id',
    name: 'skill',
    component: () => import('@/views/SkillDetailView.vue'),
    props: true,
    meta: { shellGroup: 'market' },
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('@/views/AdminLayout.vue'),
    meta: { shellGroup: 'admin', requiresAdmin: true },
    children: [
      {
        path: '',
        name: 'admin-index',
        redirect: { name: 'admin-dashboard' },
      },
      {
        path: 'dashboard',
        name: 'admin-dashboard',
        component: () => import('@/views/AdminView.vue'),
      },
      {
        path: 'plugins',
        name: 'admin-plugins',
        component: () => import('@/views/AdminPluginsView.vue'),
      },
      {
        path: 'versions',
        name: 'admin-versions',
        component: () => import('@/views/AdminPlaceholderView.vue'),
        props: {
          title: '版本治理',
          description:
            '后续会拆出独立版本治理视图，承接版本审核与 yank/block 操作。',
        },
      },
      {
        path: 'authors',
        name: 'admin-authors',
        component: () => import('@/views/AdminAuthorsView.vue'),
      },
      {
        path: 'comments',
        name: 'admin-comments',
        component: () => import('@/views/AdminCommentsView.vue'),
      },
      {
        path: 'curation',
        name: 'admin-curation',
        component: () => import('@/views/AdminCurationView.vue'),
      },
      {
        path: 'announcements',
        name: 'admin-announcements',
        component: () => import('@/views/AdminAnnouncementsView.vue'),
      },
      {
        path: 'inbox',
        name: 'admin-inbox',
        component: () => import('@/views/AdminPlaceholderView.vue'),
        props: {
          title: '后台信箱',
          description: '这里预留给后台信箱入口，后续任务会补全全屏收件箱体验。',
        },
      },
      {
        path: 'audit',
        name: 'admin-audit',
        component: () => import('@/views/AdminAuditView.vue'),
      },
      {
        path: 'system',
        name: 'admin-system',
        component: () => import('@/views/AdminPlaceholderView.vue'),
        props: {
          title: '系统状态',
          description:
            '系统状态页已预留路由，后续会拆出服务运行态和依赖状态细分视图。',
        },
      },
    ],
  },
  {
    path: '/author/:id',
    name: 'author',
    component: () => import('@/views/AuthorView.vue'),
    props: true,
    meta: { shellGroup: 'market' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'notfound',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { shellGroup: 'market' },
  },
];

const navigationTasks = new WeakMap<RouteLocationNormalized, number>();
const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    return restoreRouteScroll({
      hash: to.hash,
      savedPosition,
      keepPosition: keepsReadingPosition(to, from),
      epoch: navigationTasks.get(to) ?? -1,
      isCurrent: () => router.currentRoute.value === to,
    });
  },
});

router.beforeEach(async (to) => {
  startNavigation();
  navigationTasks.set(to, navigationEpoch.value);
  if (!to.meta.requiresAdmin) {
    return true;
  }

  const auth = useAuthStore();
  await auth.loadViewer();

  if (auth.isAdmin) {
    return true;
  }

  // The admin layout shows the precise authentication/permission state without
  // mounting private child views. Preserve the requested URL for sign-in/retry.
  return true;
});

router.afterEach((to, from) => {
  finishNavigation();
  document.title = `${({ home: '发现', market: '插件目录', skills: 'Skills', me: '工作台', inbox: '信箱', status: '服务状态' } as Record<string, string>)[String(to.name)] || '插件档案'} · MoFox`;
  if (from.matched.length && to.path !== from.path)
    requestAnimationFrame(() =>
      document.getElementById('main-content')?.focus({ preventScroll: true }),
    );
});
router.onError(() => finishNavigation('页面资源加载失败，请刷新重试。'));

export default router;
