<script setup lang="ts">
import { computed, ref } from 'vue'
import type { PinnedPlugin, Plugin } from '@/types'

const props = withDefaults(defineProps<{
  pins: PinnedPlugin[]
  availablePlugins: Plugin[]
  busy?: boolean
  limit?: number
}>(), {
  busy: false,
  limit: 6,
})

const emit = defineEmits<{
  (e: 'add', payload: { pluginId: string; reason: string | null }): void
  (e: 'update-reason', payload: { pluginId: string; reason: string | null }): void
  (e: 'remove', pluginId: string): void
}>()

const selectedPluginId = ref('')
const draftReason = ref('')

const pinnedIds = computed(() => new Set(props.pins.map((item) => item.plugin_id)))
const addablePlugins = computed(() => props.availablePlugins.filter((item) => !pinnedIds.value.has(item.plugin_id)))
const isAtLimit = computed(() => props.pins.length >= props.limit)

function addPin(): void {
  if (!selectedPluginId.value || isAtLimit.value) {
    return
  }
  emit('add', {
    pluginId: selectedPluginId.value,
    reason: draftReason.value.trim() || null,
  })
  selectedPluginId.value = ''
  draftReason.value = ''
}
</script>

<template>
  <section class="pin-editor">
    <div class="pin-editor-head">
      <span class="pin-editor-counter" :class="{ 'is-danger': isAtLimit }">{{ pins.length }} / {{ limit }}</span>
      <p v-if="isAtLimit" class="pin-editor-error">已达到 {{ limit }} 个置顶上限，请先取消一个再新增。</p>
    </div>

    <div class="pin-editor-list" v-if="pins.length">
      <article v-for="item in pins" :key="item.plugin_id" class="pin-editor-item">
        <div class="pin-editor-item-icon" aria-hidden="true">
          <img v-if="item.plugin?.icon_url" :src="item.plugin.icon_url" :alt="item.plugin.display_name">
          <template v-else>{{ (item.plugin?.display_name || item.plugin_id)[0]?.toUpperCase() || '?' }}</template>
        </div>
        <div class="pin-editor-item-body">
          <strong>{{ item.plugin?.display_name || item.plugin_id }}</strong>
          <small>{{ item.plugin_id }}</small>
          <p v-if="item.pinned_reason">{{ item.pinned_reason }}</p>
          <p v-else class="is-empty">还没有置顶理由</p>
        </div>
        <div class="pin-editor-item-actions">
          <button type="button" class="btn btn-ghost btn-xs" :disabled="busy" @click="emit('update-reason', { pluginId: item.plugin_id, reason: null })">清空理由</button>
          <button type="button" class="btn btn-xs" :disabled="busy" @click="emit('remove', item.plugin_id)">取消置顶</button>
        </div>
      </article>
    </div>
    <div v-else class="pin-editor-empty">
      <strong>还没有置顶作品</strong>
      <p>从下方选择一个你拥有的插件添加为置顶。</p>
    </div>

    <div class="pin-editor-create" v-if="!isAtLimit">
      <select v-model="selectedPluginId" class="pin-editor-input" :disabled="busy || isAtLimit">
        <option value="">选择一个插件</option>
        <option v-for="plugin in addablePlugins" :key="plugin.plugin_id" :value="plugin.plugin_id">{{ plugin.display_name }}</option>
      </select>
      <input v-model="draftReason" class="pin-editor-input" type="text" maxlength="200" :disabled="busy || isAtLimit" placeholder="置顶理由（可选，最多 200 字）">
      <button type="button" class="btn btn-primary btn-sm" :disabled="busy || isAtLimit || !selectedPluginId" @click="addPin">新增置顶</button>
    </div>
  </section>
</template>

<style scoped>
.pin-editor { display: grid; gap: var(--space-3); }

.pin-editor-head {
  display: flex; align-items: center; justify-content: space-between;
  gap: var(--space-3); flex-wrap: wrap;
}
.pin-editor-counter {
  font-family: var(--font-mono); font-size: 12px; color: var(--ink-500);
  background: var(--surface-soft);
  padding: 2px 10px;
  border-radius: var(--radius-pill);
}
.pin-editor-counter.is-danger { color: var(--coral); font-weight: 700; }
.pin-editor-error { margin: 0; color: var(--coral); font-size: 12px; }

.pin-editor-list { display: grid; gap: 8px; }
.pin-editor-item {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: var(--space-3);
  padding: 12px;
  background: var(--surface-soft);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  align-items: center;
}
.pin-editor-item-icon {
  width: 40px; height: 40px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, var(--blue-500), var(--blue-700));
  color: var(--ink-on-blue);
  display: grid; place-items: center;
  font-family: var(--font-display); font-weight: 800; font-size: 16px;
  flex: 0 0 auto;
  overflow: hidden;
}
.pin-editor-item-icon img { width: 100%; height: 100%; object-fit: cover; }

.pin-editor-item-body { display: grid; gap: 2px; min-width: 0; }
.pin-editor-item-body strong {
  font-size: 14px; font-weight: 700; color: var(--ink-900);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.pin-editor-item-body small {
  font-family: var(--font-mono); font-size: 11px; color: var(--ink-500);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.pin-editor-item-body p {
  margin: 4px 0 0;
  font-size: 12.5px; color: var(--ink-700);
  line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.pin-editor-item-body p.is-empty { color: var(--ink-300); font-style: italic; }
.pin-editor-item-actions { display: flex; gap: 4px; flex-direction: column; align-items: flex-end; }

.pin-editor-empty {
  padding: var(--space-4);
  background: var(--surface-soft);
  border: 1.5px dashed var(--line);
  border-radius: var(--radius-md);
  text-align: center;
}
.pin-editor-empty strong { display: block; color: var(--ink-700); font-size: 13.5px; }
.pin-editor-empty p { margin: 4px 0 0; color: var(--ink-500); font-size: 12px; }

.pin-editor-create {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr) auto;
  gap: 8px;
  padding: var(--space-3);
  border-top: 1px dashed var(--line);
}
@media (max-width: 720px) {
  .pin-editor-create { grid-template-columns: 1fr; }
  .pin-editor-item { grid-template-columns: auto 1fr; }
  .pin-editor-item-actions { grid-column: 1 / -1; flex-direction: row; }
}

.pin-editor-input {
  padding: 8px 12px;
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--surface);
  font: inherit;
  font-size: 13px;
  color: var(--ink-900);
  min-width: 0;
}
.pin-editor-input:focus { outline: none; border-color: var(--blue-500); box-shadow: var(--ring); }
.pin-editor-input:disabled { opacity: 0.6; cursor: not-allowed; }
</style>