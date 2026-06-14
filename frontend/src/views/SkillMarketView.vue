<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSkillsStore } from '@/stores/skills'
import type { Skill } from '@/types'

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
  <div class="skills-page">
    <header class="skills-hero">
      <h1>Skill 市场</h1>
      <p>发现和分享 AI 技能模块——让 MoFox 变得更聪明</p>
    </header>

    <!-- search bar -->
    <div class="skills-toolbar">
      <div class="skills-search">
        <input
          v-model="search"
          type="text"
          placeholder="搜索 Skill…"
          @keyup.enter="doSearch"
        >
        <button class="btn btn-primary btn-sm" @click="doSearch">搜索</button>
        <button v-if="store.search || store.category || store.tag" class="btn btn-ghost btn-sm" @click="clearFilters">清除</button>
      </div>

      <div class="skills-sorts">
        <button
          v-for="s in presetSorts"
          :key="s.value"
          :class="['btn btn-sm', sort === s.value ? 'btn-primary' : 'btn-ghost']"
          @click="setSort(s.value)"
        >{{ s.label }}</button>
      </div>
    </div>

    <!-- category / tag chips -->
    <div v-if="store.categories.length || store.tags.length" class="skills-taxonomy">
      <div v-if="store.categories.length" class="skills-chip-group">
        <span class="skills-chip-label">分类</span>
        <button
          v-for="c in store.categories"
          :key="c"
          :class="['chip', { active: store.category === c }]"
          @click="setCategory(c)"
        >{{ c }}</button>
      </div>
      <div v-if="store.tags.length" class="skills-chip-group">
        <span class="skills-chip-label">标签</span>
        <button
          v-for="t in store.tags"
          :key="t"
          :class="['chip', { active: store.tag === t }]"
          @click="setTag(t)"
        >#{{ t }}</button>
      </div>
    </div>

    <!-- loading -->
    <div v-if="store.loading" class="skills-loading">加载中…</div>

    <!-- empty -->
    <div v-else-if="!store.skills.length" class="skills-empty">
      <p>还没有 Skill，快来发布第一个吧！</p>
    </div>

    <!-- grid -->
    <template v-else>
      <div class="skills-meta">
        <span>共 {{ store.total }} 个 Skill</span>
      </div>

      <div :class="['skills-grid', viewMode === 'list' ? 'skills-grid-list' : '']">
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

      <!-- pagination -->
      <div v-if="totalPages > 1" class="skills-pager">
        <button class="btn btn-sm btn-ghost" :disabled="store.page <= 1" @click="goPage(store.page - 1)">上一页</button>
        <span class="skills-pager-info">{{ store.page }} / {{ totalPages }}</span>
        <button class="btn btn-sm btn-ghost" :disabled="store.page >= totalPages" @click="goPage(store.page + 1)">下一页</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.skills-page {
  width: min(var(--shell-max), 100%);
  margin: 0 auto;
  padding: var(--space-6) var(--space-7) var(--space-16);
  display: grid; gap: var(--space-6);
}

.skills-hero {
  text-align: center;
  padding: var(--space-6) 0 var(--space-2);
}
.skills-hero h1 {
  font-family: var(--font-display); font-weight: 900;
  font-size: clamp(28px, 3.4vw, 40px);
  margin: 0;
}
.skills-hero p {
  margin: 6px 0 0;
  color: var(--ink-500);
  font-size: 14.5px;
}

.skills-toolbar {
  display: flex; gap: var(--space-3); flex-wrap: wrap;
  align-items: center; justify-content: space-between;
}
.skills-search {
  display: flex; gap: 8px; align-items: center;
  flex: 1; min-width: 240px;
}
.skills-search input {
  flex: 1; min-width: 0;
  padding: 8px 12px;
  border: 1.5px solid var(--line);
  border-radius: var(--radius-sm);
  font-size: 13px;
  background: var(--surface);
}
.skills-search input:focus { outline: none; border-color: var(--blue-500); box-shadow: var(--ring); }
.skills-sorts { display: flex; gap: 6px; flex-wrap: wrap; }

.skills-taxonomy { display: grid; gap: var(--space-3); }
.skills-chip-group {
  display: flex; gap: 6px; flex-wrap: wrap; align-items: center;
}
.skills-chip-label {
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 11px; color: var(--ink-500); text-transform: uppercase;
  margin-right: 4px;
}
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

.skills-meta { font-size: 12.5px; color: var(--ink-500); }
.skills-loading, .skills-empty { text-align: center; padding: var(--space-12) 0; color: var(--ink-500); }

.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
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

.skills-pager {
  display: flex; gap: var(--space-3); align-items: center; justify-content: center;
  padding-top: var(--space-4);
}
.skills-pager-info {
  font-family: var(--font-mono); font-size: 13px; color: var(--ink-600);
}
</style>
