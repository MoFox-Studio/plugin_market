<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSkillsStore } from '@/stores/skills'
import VolKickerBar from '@/components/VolKickerBar.vue'

const router = useRouter()
const store = useSkillsStore()

const search = ref('')
const sort = ref('updated')
const viewMode = ref<'grid' | 'list'>('grid')

const totalPages = computed(() => Math.max(1, Math.ceil(store.total / store.pageSize)))

const presetSorts = [
  { label: '最近更新', value: 'updated' },
  { label: '最多下载', value: 'downloads' },
  { label: '评分最高', value: 'rating' },
]

function doSearch() {
  store.setFilter({ search: search.value, sort: sort.value })
}

function setSort(s: string) {
  sort.value = s
  store.setFilter({ sort: s })
}

function setCategory(c: string) {
  store.setFilter({ category: c })
}

function setTag(t: string) {
  store.setFilter({ tag: t })
}

function clearFilters() {
  search.value = ''
  store.setFilter({ search: '', category: '', tag: '', sort: 'updated' })
}

function goToSkill(skillId: string) {
  router.push({ name: 'skill', params: { id: skillId } })
}

function goPage(p: number) {
  if (p < 1 || p > totalPages.value) return
  store.setPage(p)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  store.loadSkills()
  store.loadCategories()
  store.loadTags()
})
</script>

<template>
  <VolKickerBar :page-label="'SKILLS'" :count="store.total" />

  <div class="browse-page">
    <aside class="browse-side">
      <div class="browse-side-section">
        <h4>排序</h4>
        <ul>
          <li v-for="s in presetSorts" :key="s.value">
            <button type="button" :class="{ active: sort === s.value }" @click="setSort(s.value)">{{ s.label }}</button>
          </li>
        </ul>
      </div>

      <div class="browse-side-section" v-if="store.categories.length">
        <h4>分类</h4>
        <ul>
          <li><button type="button" :class="{ active: !store.category }" @click="setCategory('')">全部分类</button></li>
          <li v-for="c in store.categories" :key="c">
            <button type="button" :class="{ active: store.category === c }" @click="setCategory(c)">{{ c }}</button>
          </li>
        </ul>
      </div>

      <div class="browse-side-section" v-if="store.tags.length">
        <h4>热门标签</h4>
        <ul>
          <li><button type="button" :class="{ active: !store.tag }" @click="setTag('')">全部标签</button></li>
          <li v-for="t in store.tags" :key="t">
            <button type="button" :class="{ active: store.tag === t }" @click="setTag(t)">#{{ t }}</button>
          </li>
        </ul>
      </div>
    </aside>

    <main class="browse-main">
      <div class="browse-crumb">
        <router-link to="/" class="browse-crumb-link">推荐</router-link>
        <span class="browse-crumb-sep">/</span>
        <span class="browse-crumb-text">Skill 市场</span>
      </div>

      <header class="browse-head">
        <div class="browse-head-titles">
          <h1>全部 Skill</h1>
          <p>发现和分享 AI 技能模块——让 MoFox 变得更聪明</p>
        </div>
        <div class="browse-head-count">
          <strong>{{ store.total }}</strong>
          <small>个结果</small>
        </div>
      </header>

      <div class="browse-toolbar">
        <div class="browse-toolbar-left">
          <div class="skills-search">
            <input
              v-model="search"
              type="text"
              placeholder="搜索 Skill…"
              @keyup.enter="doSearch"
            >
            <button class="btn btn-primary btn-sm" @click="doSearch">搜索</button>
          </div>
        </div>
        <div class="browse-toolbar-right">
          <div class="chip-group">
            <button type="button" :class="['chip', { active: viewMode === 'grid' }]" @click="viewMode = 'grid'" aria-label="网格视图">网格</button>
            <button type="button" :class="['chip', { active: viewMode === 'list' }]" @click="viewMode = 'list'" aria-label="列表视图">列表</button>
          </div>
          <button v-if="store.search || store.category || store.tag" type="button" class="btn btn-ghost btn-sm" @click="clearFilters">清除筛选</button>
        </div>
      </div>

      <div v-if="store.loading" class="grid">
        <div v-for="i in 9" :key="i" class="card skeleton" style="height: 120px"></div>
      </div>
      <div v-else-if="!store.skills.length" class="skills-empty">
        <p>还没有 Skill，快来发布第一个吧！</p>
      </div>
      <template v-else>
        <div :class="['skills-grid', { 'skills-grid-list': viewMode === 'list' }]">
          <article
            v-for="skill in store.skills"
            :key="skill.skill_id"
            class="skill-card"
            @click="goToSkill(skill.skill_id)"
          >
            <div class="skill-card-icon">
              <img v-if="skill.icon_url" :src="skill.icon_url" :alt="skill.display_name">
              <span v-else>{{ skill.display_name[0]?.toUpperCase() || '?' }}</span>
            </div>
            <div class="skill-card-body">
              <h3>{{ skill.display_name }}</h3>
              <p class="skill-card-desc">{{ skill.description.length > 200 ? skill.description.slice(0, 200) + '…' : skill.description }}</p>
              <div class="skill-card-meta">
                <span class="skill-card-author">{{ skill.owner_display_name || skill.owner_login || skill.owner_id }}</span>
                <span v-if="skill.latest_version" class="skill-card-version">v{{ skill.latest_version }}</span>
                <span class="skill-card-stat">⭐ {{ skill.rating_avg?.toFixed(1) || '-' }}</span>
                <span class="skill-card-stat">⬇ {{ skill.download_count }}</span>
              </div>
            </div>
          </article>
        </div>

        <nav v-if="totalPages > 1" class="pagination">
          <button type="button" class="page-btn" :disabled="store.page <= 1" @click="goPage(store.page - 1)">上一页</button>
          <span class="page-ellipsis">{{ store.page }} / {{ totalPages }}</span>
          <button type="button" class="page-btn" :disabled="store.page >= totalPages" @click="goPage(store.page + 1)">下一页</button>
        </nav>
      </template>
    </main>
  </div>
</template>

<style scoped>
.browse-page {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: var(--space-7);
  width: min(var(--shell-max), 100%);
  margin: 0 auto;
  padding: var(--space-6) var(--space-7) var(--space-16);
  align-items: flex-start;
}

@media (max-width: 1023px) {
  .browse-page { grid-template-columns: 1fr; padding: var(--space-5) var(--space-4) var(--space-12); }
}

.browse-side {
  position: sticky;
  top: calc(var(--topbar-h) + var(--kicker-h) + var(--space-5));
  align-self: flex-start;
  display: grid; gap: var(--space-5);
  padding: var(--space-5);
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  max-height: calc(100vh - var(--topbar-h) - var(--kicker-h) - var(--space-7));
  overflow-y: auto;
  scrollbar-width: thin;
  animation: fade-up var(--dur-slow) var(--ease-emphasized) both;
}
@media (max-width: 1023px) {
  .browse-side { position: static; max-height: none; }
}

.browse-side-section { display: grid; gap: 6px; }
.browse-side-section + .browse-side-section {
  padding-top: var(--space-4);
  border-top: 1px dashed var(--line);
}
.browse-side-section h4 {
  margin: 0 0 4px;
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 11px; color: var(--ink-500);
  text-transform: uppercase;
}
.browse-side-section ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 1px; }
.browse-side-section li button {
  width: 100%; text-align: left;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--ink-700);
  position: relative;
  transition: background var(--dur-fast), color var(--dur-fast);
}
.browse-side-section li button:hover { background: var(--surface-hover); color: var(--ink-900); }
.browse-side-section li button.active {
  background: var(--blue-100); color: var(--blue-700); font-weight: 700;
  padding-left: 14px;
}
.browse-side-section li button.active::before {
  content: ""; position: absolute;
  left: 0; top: 50%; transform: translateY(-50%);
  width: 3px; height: 16px; border-radius: 2px;
  background: var(--blue-500);
}

.browse-main {
  min-width: 0;
  display: grid; gap: var(--space-4);
  animation: fade-up var(--dur-slow) var(--ease-emphasized) both;
}

.browse-crumb {
  display: flex; align-items: center; gap: 8px;
  font-family: var(--font-mono); font-size: 11.5px;
  color: var(--ink-500); letter-spacing: 0.04em;
}
.browse-crumb-link { color: var(--blue-700); font-weight: 700; }
.browse-crumb-sep  { color: var(--ink-300); }
.browse-crumb-text { color: var(--ink-500); }

.browse-head {
  display: flex; justify-content: space-between; align-items: flex-end; gap: var(--space-4);
  flex-wrap: wrap;
}
.browse-head-titles h1 {
  margin: 0;
  font-family: var(--font-display); font-weight: 900;
  font-size: clamp(28px, 3vw, 36px);
  line-height: 1.1;
  color: var(--ink-900);
}
.browse-head-titles p {
  margin: 4px 0 0;
  color: var(--ink-500); font-size: 13.5px;
}
.browse-head-count {
  display: flex; align-items: baseline; gap: 6px;
}
.browse-head-count strong {
  font-family: var(--font-brand);
  letter-spacing: 0.04em;
  font-size: 36px;
  color: var(--ink-900);
  line-height: 1;
}
.browse-head-count small {
  font-family: var(--font-mono); font-size: 11px;
  color: var(--ink-500); letter-spacing: 0.06em;
}

.browse-toolbar {
  display: flex; justify-content: space-between; align-items: center; gap: var(--space-3);
  flex-wrap: wrap;
  padding: 10px 12px;
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
}
.browse-toolbar-left, .browse-toolbar-right {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}

.skills-search {
  display: flex; gap: 8px; align-items: center;
  flex: 1; min-width: 240px;
}
.skills-search input {
  flex: 1; min-width: 0;
  padding: 6px 12px;
  border: 1.5px solid var(--line);
  border-radius: var(--radius-sm);
  font-size: 13px;
  background: var(--surface);
}
.skills-search input:focus { outline: none; border-color: var(--blue-500); box-shadow: var(--ring); }

.chip {
  padding: 4px 10px;
  border-radius: var(--radius-pill);
  border: 1px solid var(--line);
  background: var(--surface-soft);
  font-size: 12px; font-weight: 600;
  color: var(--ink-700);
  cursor: pointer;
  transition: all var(--dur-fast);
}
.chip:hover { background: var(--blue-50); border-color: var(--blue-300); }
.chip.active { background: var(--blue-500); color: #fff; border-color: var(--blue-500); }
.chip-group {
  display: flex; gap: 6px; flex-wrap: wrap; align-items: center;
}

@keyframes fade-up {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
  .browse-side, .browse-main { animation: none; }
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
  padding: var(--space-6) 0 var(--space-4);
}
.page-btn {
  min-width: 36px;
  padding: 6px 12px;
  border: 1.5px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--surface);
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-700);
  cursor: pointer;
  transition: background var(--dur-fast), color var(--dur-fast), border-color var(--dur-fast);
}
.page-btn:hover:not(:disabled):not(.active) {
  background: var(--surface-hover);
  border-color: var(--ink-300);
  color: var(--ink-900);
}
.page-btn.active {
  background: var(--blue-600, #2563eb);
  border-color: var(--blue-600, #2563eb);
  color: #fff;
  cursor: default;
}
.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.page-ellipsis {
  padding: 0 4px;
  font-size: 14px;
  color: var(--ink-400);
  user-select: none;
}

/* Skills grid */
.skills-empty { text-align: center; padding: var(--space-12) 0; color: var(--ink-500); }

.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-4);
}
.skills-grid-list { grid-template-columns: 1fr; }

.skill-card {
  display: grid; grid-template-columns: auto 1fr; gap: var(--space-3);
  padding: var(--space-4);
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--dur-fast);
}
.skill-card:hover {
  border-color: var(--blue-300);
  box-shadow: var(--shadow-card);
  transform: translateY(-2px);
}

.skill-card-icon {
  width: 48px; height: 48px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, var(--coral), var(--lemon));
  display: grid; place-items: center;
  font-family: var(--font-display); font-weight: 800; font-size: 20px;
  color: var(--ink-900);
  overflow: hidden;
  flex-shrink: 0;
}
.skill-card-icon img { width: 100%; height: 100%; object-fit: cover; }

.skill-card-body { display: grid; gap: 4px; min-width: 0; }
.skill-card-body h3 {
  margin: 0;
  font-family: var(--font-display); font-weight: 800;
  font-size: 16px; line-height: 1.2;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.skill-card-desc {
  margin: 0;
  font-size: 13px; color: var(--ink-600);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.5;
}
.skill-card-meta {
  display: flex; gap: 12px; flex-wrap: wrap;
  font-family: var(--font-mono); font-size: 11.5px; color: var(--ink-500);
  margin-top: 4px;
}
.skill-card-author { font-weight: 600; }
.skill-card-version { color: var(--blue-600); }
.skill-card-stat { opacity: 0.8; }
</style>
