import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
          description: '后续会拆出独立版本治理视图，承接版本审核与 yank/block 操作。',
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
          description: '系统状态页已预留路由，后续会拆出服务运行态和依赖状态细分视图。',
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
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0 }
  },
})

router.beforeEach(async (to) => {
  if (!to.meta.requiresAdmin) {
    return true
  }

  const auth = useAuthStore()
  await auth.loadViewer()

  if (auth.isAdmin) {
    return true
  }

  return { name: 'market' }
})

export default router
