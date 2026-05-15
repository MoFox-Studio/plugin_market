import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'market',
    component: () => import('@/views/MarketView.vue'),
  },
  {
    path: '/plugin/:id',
    name: 'plugin',
    component: () => import('@/views/PluginDetailView.vue'),
    props: true,
  },
  {
    path: '/me',
    name: 'me',
    component: () => import('@/views/MeView.vue'),
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('@/views/AdminView.vue'),
  },
  {
    path: '/author/:id',
    name: 'author',
    component: () => import('@/views/AuthorView.vue'),
    props: true,
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'notfound',
    component: () => import('@/views/NotFoundView.vue'),
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

export default router
