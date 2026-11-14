<script setup lang="ts">
import MarketSelect from '@/components/MarketSelect.vue';
import { computed, ref, watch } from 'vue';
import type { PinnedPlugin, Plugin } from '@/types';

const props = withDefaults(
  defineProps<{
    pins: PinnedPlugin[];
    availablePlugins: Plugin[];
    busy?: boolean;
    limit?: number;
  }>(),
  {
    busy: false,
    limit: 6,
  },
);

const emit = defineEmits<{
  (e: 'add', payload: { pluginId: string; reason: string | null }): void;
  (
    e: 'update-reason',
    payload: { pluginId: string; reason: string | null },
  ): void;
  (e: 'remove', pluginId: string): void;
}>();

const selectedPluginId = ref('');
const draftReason = ref('');
const editingId = ref('');
const editReason = ref('');
watch(
  () => props.pins,
  (pins) => {
    if (pins.some((pin) => pin.plugin_id === selectedPluginId.value)) {
      selectedPluginId.value = '';
      draftReason.value = '';
    }
    const edited = pins.find((pin) => pin.plugin_id === editingId.value);
    if (!edited || (edited.pinned_reason || '') === editReason.value.trim())
      editingId.value = '';
  },
  { deep: true },
);

const pinnedIds = computed(
  () => new Set(props.pins.map((item) => item.plugin_id)),
);
const addablePlugins = computed(() =>
  props.availablePlugins.filter((item) => !pinnedIds.value.has(item.plugin_id)),
);
const isAtLimit = computed(() => props.pins.length >= props.limit);

function addPin(): void {
  if (!selectedPluginId.value || isAtLimit.value || props.busy) {
    return;
  }
  emit('add', {
    pluginId: selectedPluginId.value,
    reason: draftReason.value.trim() || null,
  });
}
</script>

<template>
  <section class="pin-editor">
    <div class="pin-editor-head">
      <span class="pin-editor-counter" :class="{ 'is-danger': isAtLimit }"
        >{{ pins.length }} / {{ limit }}</span
      >
      <p v-if="isAtLimit" class="pin-editor-error">
        已达到 {{ limit }} 个置顶上限，请先取消一个再新增。
      </p>
    </div>

    <div class="pin-editor-list" v-if="pins.length">
      <article
        v-for="item in pins"
        :key="item.plugin_id"
        class="pin-editor-item"
      >
        <div class="pin-editor-item-icon" aria-hidden="true">
          <img
            v-if="item.plugin?.icon_url"
            :src="item.plugin.icon_url"
            :alt="item.plugin.display_name"
          />
          <template v-else>{{
            (item.plugin?.display_name || item.plugin_id)[0]?.toUpperCase() ||
            '?'
          }}</template>
        </div>
        <div class="pin-editor-item-body">
          <strong>{{ item.plugin?.display_name || item.plugin_id }}</strong>
          <small>{{ item.plugin_id }}</small>
          <div v-if="editingId === item.plugin_id" class="pin-editor-edit">
            <input
              v-model="editReason"
              class="pin-editor-input"
              aria-label="修改置顶理由"
              maxlength="200"
              :disabled="busy"
            /><button
              class="btn btn-xs"
              type="button"
              :disabled="busy"
              @click="
                emit('update-reason', {
                  pluginId: item.plugin_id,
                  reason: editReason.trim() || null,
                })
              "
            >
              保存</button
            ><button
              class="btn btn-ghost btn-xs"
              type="button"
              :disabled="busy"
              @click="editingId = ''"
            >
              取消
            </button>
          </div>
          <p v-else-if="item.pinned_reason">{{ item.pinned_reason }}</p>
          <p v-else class="is-empty">还没有置顶理由</p>
        </div>
        <div class="pin-editor-item-actions">
          <button
            type="button"
            class="btn btn-ghost btn-xs"
            :disabled="busy"
            @click="
              editingId = item.plugin_id;
              editReason = item.pinned_reason || '';
            "
          >
            修改理由
          </button>
          <button
            type="button"
            class="btn btn-xs"
            :disabled="busy"
            @click="emit('remove', item.plugin_id)"
          >
            取消置顶
          </button>
        </div>
      </article>
    </div>
    <div v-else class="pin-editor-empty">
      <strong>还没有置顶作品</strong>
      <p>从下方选择一个你拥有的插件添加为置顶。</p>
    </div>

    <div class="pin-editor-create" v-if="!isAtLimit">
      <MarketSelect
        aria-label="选择置顶插件"
        v-model="selectedPluginId"
        class="pin-editor-input"
        :disabled="busy || isAtLimit"
      >
        <option value="">选择一个插件</option>
        <option
          v-for="plugin in addablePlugins"
          :key="plugin.plugin_id"
          :value="plugin.plugin_id"
        >
          {{ plugin.display_name }}
        </option>
      </MarketSelect>
      <input
        aria-label="置顶理由"
        v-model="draftReason"
        class="pin-editor-input"
        type="text"
        maxlength="200"
        :disabled="busy || isAtLimit"
        placeholder="置顶理由（可选，最多 200 字）"
      />
      <button
        type="button"
        class="btn btn-primary btn-sm"
        :disabled="busy || isAtLimit || !selectedPluginId"
        @click="addPin"
      >
        新增置顶
      </button>
    </div>
  </section>
</template>

<style scoped>
.pin-editor {
  display: grid;
  gap: 16px;
}
.pin-editor-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.pin-editor-counter {
  font: 11px var(--font-mono);
  color: var(--ink-500);
}
.pin-editor-error {
  font-size: 12px;
  color: var(--ink-500);
  margin: 0;
}
.pin-editor-list {
  border-top: 1px solid var(--line);
}
.pin-editor-item {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  gap: 12px;
  padding: 18px 0;
  border-bottom: 1px solid var(--line);
  align-items: start;
}
.pin-editor-item-icon {
  width: 34px;
  height: 34px;
  border: 1px solid var(--line);
  border-radius: 3px;
  background: var(--surface-soft);
  color: var(--blue-500);
  display: grid;
  place-items: center;
  overflow: hidden;
}
.pin-editor-item-icon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.pin-editor-item-body {
  display: grid;
  gap: 5px;
  min-width: 0;
}
.pin-editor-item-body strong {
  font-size: 13px;
  color: var(--ink-900);
  overflow-wrap: anywhere;
}
.pin-editor-item-body small {
  font: 10px var(--font-mono);
  color: var(--ink-500);
  overflow-wrap: anywhere;
}
.pin-editor-item-body p {
  margin: 3px 0 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--ink-700);
}
.pin-editor-item-body .is-empty {
  color: var(--ink-500);
}
.pin-editor-item-actions {
  display: flex;
  gap: 5px;
  flex-direction: column;
}
.pin-editor-empty {
  padding: 26px 18px;
  border: 1px dashed var(--line);
  border-radius: 3px;
  background: var(--surface-soft);
}
.pin-editor-empty strong {
  font-size: 13px;
}
.pin-editor-empty p {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--ink-500);
}
.pin-editor-create {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
  padding-top: 8px;
}
.pin-editor-input {
  width: 100%;
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 3px;
  background: var(--surface);
  font: 12px var(--font-body);
  color: var(--ink-900);
}
.pin-editor-input:focus {
  outline: 2px solid var(--blue-500);
  outline-offset: 2px;
}
.pin-editor-edit {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.pin-editor-edit input {
  flex-basis: 100%;
}
@media (max-width: 600px) {
  .pin-editor-item {
    grid-template-columns: 30px minmax(0, 1fr);
  }
  .pin-editor-item-actions {
    grid-column: 2;
    flex-direction: row;
    flex-wrap: wrap;
  }
}
</style>
