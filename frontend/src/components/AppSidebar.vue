<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useTaxonomyStore } from '@/stores/taxonomy'
import { categoryLabel } from '@/utils/format'
import AppSidebarLink from '@/components/AppSidebarLink.vue'

type SidebarGroup = 'home' | 'market' | 'me' | 'admin'

interface SidebarItem {
  label: string
  to: RouteLocationRaw
  meta?: string
}

interface SidebarSection {
  title: string
  hint: string
  items: SidebarItem[]
}

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const route = useRoute()
const auth = useAuthStore()
const taxonomy = useTaxonomyStore()
const drawerRef = ref<HTMLElement | null>(null)

const routeGroup = computed<SidebarGroup>(() => {
  const metaGroup = route.meta.shellGroup
  if (metaGroup === 'home' || metaGroup === 'me' || metaGroup === 'admin' || metaGroup === 'market') {
    return metaGroup
  }
  if (String(route.name || '').startsWith('admin')) {
    return 'admin'
  }
  if (String(route.name || '').startsWith('me')) {
    return 'me'
  }
  if (route.name === 'home') {
    return 'home'
  }
  return 'market'
})

const marketSections = computed<SidebarSection[]>(() => {
  const categoryItems = taxonomy.categories.slice(0, 6).map((category) => ({
    label: categoryLabel(category),
    to: { name: 'market', query: { category } },
    meta: '分类',
  }))
  const tagItems = taxonomy.tags.slice(0, 6).map((tag) => ({
    label: `#${tag}`,
    to: { name: 'market', query: { tag } },
    meta: '标签',
  }))

  return [
    {
      title: '排序方式',
      hint: '不同视角看同一份插件库。',
      items: [
        { label: '最近更新', to: { name: 'market', query: { sort: 'updated' } }, meta: '默认' },
        { label: '综合热度', to: { name: 'market', query: { sort: 'popular' } }, meta: '排序' },
        { label: '高分优先', to: { name: 'market', query: { sort: 'rating' } }, meta: '排序' },
        { label: '下载最多', to: { name: 'market', query: { sort: 'downloads' } }, meta: '排序' },
        { label: '趋势上升', to: { name: 'market', query: { sort: 'trending' } }, meta: '排序' },
      ],
    },
    {
      title: '分类捷径',
      hint: '从高频分类直接跳到插件库筛选。',
      items: categoryItems,
    },
    {
      title: '热门标签',
      hint: '常用标签保留在全局侧栏里。',
      items: tagItems,
    },
    {
      title: '其他入口',
      hint: '来回穿梭。',
      items: [
        { label: '回到推荐页', to: { name: 'home' }, meta: 'Home' },
      ],
    },
  ]
})

const homeSections = computed<SidebarSection[]>(() => [
  {
    title: '本期市集',
    hint: '推荐页的栏目快速跳转。',
    items: [
      { label: '回到顶部', to: { name: 'home' }, meta: '推荐' },
      { label: '前往浏览页', to: { name: 'market' }, meta: '全部' },
      { label: '最近更新', to: { name: 'market', query: { sort: 'updated' } }, meta: '排序' },
      { label: '高分优先', to: { name: 'market', query: { sort: 'rating' } }, meta: '排序' },
      { label: '官方插件', to: { name: 'market', query: { trust_level: 'official' } }, meta: '信任' },
      { label: '认证作者', to: { name: 'market', query: { trust_level: 'verified' } }, meta: '信任' },
    ],
  },
])

const meSections = computed<SidebarSection[]>(() => {
  const publicProfile = auth.viewer
    ? { name: 'author', params: { id: auth.viewer.author_id } }
    : { name: 'market' }

  return [
    {
      title: '我的空间',
      hint: '聚焦个人工作台和公开主页入口。',
      items: [
        { label: '工作台总览', to: { name: 'me', hash: '#me-overview' }, meta: '概览' },
        { label: '个人空间设置', to: { name: 'me-profile' }, meta: 'Profile' },
        { label: '插件列表', to: { name: 'me', hash: '#me-plugins' }, meta: '管理' },
        { label: '信箱入口', to: { name: 'inbox' }, meta: 'Inbox' },
        { label: '版本与治理', to: { name: 'me', hash: '#me-operations' }, meta: '操作' },
        { label: '公开主页', to: publicProfile, meta: 'Author' },
        { label: '返回市场', to: { name: 'market' }, meta: '市场' },
      ],
    },
  ]
})

const adminSections = computed<SidebarSection[]>(() => [
  {
    title: '管理后台',
    hint: '把高频治理分区固定在全局侧栏。',
    items: [
      { label: '仪表盘', to: { name: 'admin-dashboard' }, meta: '概览' },
      { label: '插件治理', to: { name: 'admin-plugins' }, meta: '插件' },
      { label: '版本治理', to: { name: 'admin-versions' }, meta: '版本' },
      { label: '作者管理', to: { name: 'admin-authors' }, meta: '作者' },
      { label: '评论审核', to: { name: 'admin-comments' }, meta: '评论' },
      { label: '精选配置', to: { name: 'admin-curation' }, meta: '精选' },
    ],
  },
])

const sections = computed<SidebarSection[]>(() => {
  if (routeGroup.value === 'me') {
    return meSections.value
  }
  if (routeGroup.value === 'admin') {
    return adminSections.value
  }
  if (routeGroup.value === 'home') {
    return homeSections.value
  }
  return marketSections.value
})

const chipItems = computed(() => sections.value[0]?.items.slice(0, 6) || [])

watch(routeGroup, (group) => {
  if (group === 'market' || group === 'home') {
    void taxonomy.load()
  }
}, { immediate: true })

watch(() => route.fullPath, () => {
  emit('close')
})

function closeDrawer(): void {
  emit('close')
}

function focusableNodes(): HTMLElement[] {
  if (!drawerRef.value) {
    return []
  }
  return Array.from(
    drawerRef.value.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])')
  ).filter((node) => !node.hasAttribute('disabled'))
}

function onDocumentKeydown(event: KeyboardEvent): void {
  if (!props.open) {
    return
  }

  if (event.key === 'Escape') {
    event.preventDefault()
    closeDrawer()
    return
  }

  if (event.key !== 'Tab') {
    return
  }

  const focusables = focusableNodes()
  if (!focusables.length) {
    return
  }

  const first = focusables[0]
  const last = focusables[focusables.length - 1]
  const active = document.activeElement as HTMLElement | null

  if (event.shiftKey && active === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && active === last) {
    event.preventDefault()
    first.focus()
  }
}

function teardownDrawer(): void {
  if (typeof document === 'undefined') {
    return
  }
  document.body.classList.remove('modal-open')
  document.removeEventListener('keydown', onDocumentKeydown)
}

watch(() => props.open, async (open) => {
  if (typeof document === 'undefined') {
    return
  }

  if (!open) {
    teardownDrawer()
    return
  }

  document.body.classList.add('modal-open')
  document.addEventListener('keydown', onDocumentKeydown)
  await nextTick()
  const initial = drawerRef.value?.querySelector<HTMLElement>('[data-sidebar-initial-focus]')
  initial?.focus()
})

onBeforeUnmount(() => {
  teardownDrawer()
})
</script>

<template>
  <div class="app-sidebar-shell">
    <aside class="app-sidebar-desktop" :data-group="routeGroup">
      <div class="app-sidebar-panel">
        <section v-for="section in sections" :key="section.title" class="app-sidebar-group">
          <div class="app-sidebar-group-head">
            <h2>{{ section.title }}</h2>
            <p>{{ section.hint }}</p>
          </div>
          <div class="app-sidebar-links">
            <AppSidebarLink
              v-for="item in section.items"
              :key="`${section.title}-${item.label}`"
              :to="item.to"
              :label="item.label"
              :meta="item.meta"
            />
          </div>
        </section>
      </div>
    </aside>

    <div class="app-sidebar-chipbar" :data-group="routeGroup">
      <div class="app-sidebar-chiprow">
        <AppSidebarLink
          v-for="item in chipItems"
          :key="`chip-${item.label}`"
          :to="item.to"
          :label="item.label"
          compact
          @navigate="closeDrawer"
        />
      </div>
    </div>

    <div v-if="open" class="app-sidebar-overlay" @click.self="closeDrawer">
      <div ref="drawerRef" class="app-sidebar-drawer" role="dialog" aria-modal="true" aria-label="站点导航">
        <div class="app-sidebar-drawer-head">
          <div>
            <span class="app-sidebar-kicker">Navigation</span>
            <strong>{{
              routeGroup === 'admin' ? '管理导航'
                : routeGroup === 'me' ? '我的空间'
                : routeGroup === 'home' ? '本期市集'
                : '浏览导航'
            }}</strong>
          </div>
          <button type="button" class="btn btn-ghost btn-sm" data-sidebar-initial-focus @click="closeDrawer">关闭</button>
        </div>
        <section v-for="section in sections" :key="`drawer-${section.title}`" class="app-sidebar-group">
          <div class="app-sidebar-group-head">
            <h2>{{ section.title }}</h2>
            <p>{{ section.hint }}</p>
          </div>
          <div class="app-sidebar-links">
            <AppSidebarLink
              v-for="item in section.items"
              :key="`drawer-${section.title}-${item.label}`"
              :to="item.to"
              :label="item.label"
              :meta="item.meta"
              @navigate="closeDrawer"
            />
          </div>
        </section>
      </div>
    </div>
  </div>
</template>