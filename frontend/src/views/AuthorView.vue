<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'
import type { Plugin } from '@/types'
import PluginCard from '@/components/PluginCard.vue'
import EmptyState from '@/components/EmptyState.vue'

const props = defineProps({ id: { type: String, required: true } })

const plugins = ref<Plugin[]>([])
const author = ref<Plugin | null>(null)
const loading = ref(true)

onMounted(async () => {
  loading.value = true
  try {
    const result = await api.get('/api/v1/plugins?limit=100&sort=popular')
    const items = (result.items || []).filter(
      (p: Plugin) => p.owner_id === props.id || (p.maintainers || []).includes(props.id)
    )
    plugins.value = items
    author.value = items.find((p: Plugin) => p.owner_id === props.id) || items[0] || null
  } catch {
    plugins.value = []
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-if="loading" class="loading-screen">加载中…</div>
  <div v-else style="padding:24px 0 64px">
    <!-- Author hero -->
    <section class="hero">
      <div>
        <h1>{{ author?.owner_display_name || author?.owner_login || id }}</h1>
        <p>@{{ author?.owner_login || id }} · 共维护 {{ plugins.length }} 个插件</p>
      </div>
      <img
        v-if="author?.owner_avatar_url"
        :src="author.owner_avatar_url"
        alt=""
        style="width:72px;height:72px;border-radius:16px"
      >
    </section>

    <!-- Plugin list -->
    <section class="section">
      <div class="section-head">
        <div><h2>公开插件</h2><p>按综合热度排序。</p></div>
      </div>
      <div v-if="plugins.length" class="grid">
        <PluginCard v-for="p in plugins" :key="p.plugin_id" :plugin="p" />
      </div>
      <EmptyState v-else title="暂无插件" message="该作者尚未发布任何已审核通过的插件。" />
    </section>
  </div>
</template>
