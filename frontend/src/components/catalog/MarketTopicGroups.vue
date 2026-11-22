<script setup lang="ts">
import { computed, ref, watch } from 'vue';

const props = withDefaults(
  defineProps<{
    tags: string[];
    modelValue?: string;
    discovery?: boolean;
  }>(),
  { modelValue: '', discovery: false },
);
defineEmits<{ 'update:modelValue': [tag: string] }>();

// These groups organize existing tags; they are never sent to the API as filters.
const topics = [
  {
    id: 'conversation',
    label: '智能对话',
    tags: ['llm', 'auto-reply', 'persona'],
  },
  {
    id: 'knowledge',
    label: '记忆知识',
    tags: ['memory', 'graph', 'knowledge', 'search'],
  },
  {
    id: 'social',
    label: '群聊娱乐',
    tags: ['game', 'multiplayer', 'entertainment', 'sticker', 'music'],
  },
  {
    id: 'media',
    label: '图像媒体',
    tags: ['vision', 'image', 'media', 'video'],
  },
  {
    id: 'productivity',
    label: '效率自动化',
    tags: ['schedule', 'news', 'digest', 'translation', 'i18n', 'utility'],
  },
  {
    id: 'safety',
    label: '社区安全',
    tags: ['moderation', 'security', 'filter'],
  },
];
const groups = computed(() =>
  topics
    .map((topic) => ({
      ...topic,
      tags: [...new Set(props.tags)].filter((tag) =>
        topic.tags.includes(tag.toLowerCase()),
      ),
    }))
    .filter((topic) => topic.tags.length),
);
const expanded = ref<Record<string, boolean>>({});
watch(
  [groups, () => props.modelValue],
  () => {
    const selected = groups.value.find((group) =>
      group.tags.includes(props.modelValue),
    );
    if (selected) expanded.value = { ...expanded.value, [selected.id]: true };
  },
  { immediate: true },
);
</script>
<template>
  <section
    v-if="groups.length"
    class="market-topics"
    :class="{ 'is-discovery': discovery }"
    aria-label="常用主题"
  >
    <header class="market-topics__head">
      <span>按标签查阅</span>
      <h2>常用主题</h2>
      <p>展开主题，选择具体标签。</p>
    </header>
    <div class="market-topics__groups">
      <div
        v-for="group in groups"
        :key="group.id"
        class="market-topic"
        :class="{ 'has-selection': group.tags.includes(modelValue) }"
      >
        <button
          type="button"
          class="market-topic__toggle"
          :aria-expanded="!!expanded[group.id]"
          @click="expanded[group.id] = !expanded[group.id]"
        >
          <span>{{ group.label }}</span
          ><span aria-hidden="true">{{ expanded[group.id] ? '−' : '+' }}</span>
        </button>
        <div
          v-if="expanded[group.id]"
          class="market-topic__tags"
          role="group"
          :aria-label="`${group.label}标签`"
        >
          <template v-for="tag in group.tags" :key="tag">
            <router-link
              v-if="discovery"
              :to="{ name: 'market', query: { tag } }"
              >#{{ tag }}</router-link
            >
            <button
              v-else
              type="button"
              :aria-pressed="modelValue === tag"
              :class="{ active: modelValue === tag }"
              @click="$emit('update:modelValue', tag)"
            >
              #{{ tag }}
            </button>
          </template>
        </div>
      </div>
    </div>
  </section>
</template>
<style scoped>
.market-topics {
  margin-top: 30px;
  min-width: 0;
}
.market-topics__head {
  padding-bottom: 14px;
  border-bottom: 1px solid var(--line-strong);
}
.market-topics__head > span {
  font: 10px/1.5 var(--font-sans);
  letter-spacing: 0.08em;
  color: var(--blue-600);
}
.market-topics__head h2 {
  margin: 7px 0 0;
  font: 700 20px/1.4 var(--font-editorial, serif);
}
.market-topics__head p {
  margin: 7px 0 0;
  font-size: 10px;
  line-height: 1.6;
  color: var(--ink-500);
}
.market-topics__groups {
  display: grid;
  align-items: start;
}
.market-topic {
  border-bottom: 1px solid var(--line);
  min-width: 0;
}
.market-topic__toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 14px 0;
  font-size: 12px;
  text-align: left;
  color: var(--ink-700);
}
.market-topic__toggle > span:last-child {
  color: var(--blue-600);
  font: 16px var(--font-mono);
}
.market-topic.has-selection .market-topic__toggle {
  color: var(--blue-700);
}
.market-topic__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  padding: 0 0 16px;
}
.market-topic__tags > * {
  padding: 6px 8px;
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink-500);
  font: 10px/1.5 var(--font-mono);
  overflow-wrap: anywhere;
  text-align: left;
}
.market-topic__tags > *:hover,
.market-topic__tags > .active {
  color: var(--blue-700);
  border-color: var(--blue-300);
  background: var(--blue-50);
}
.market-topics.is-discovery {
  margin-top: 0;
  padding: 28px 0 32px;
  border-bottom: 1px solid var(--line);
}
.is-discovery .market-topics__head {
  border: 0;
}
.is-discovery .market-topics__groups {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0 26px;
  border-top: 1px solid var(--line);
}
@media (max-width: 980px) {
  .market-topics:not(.is-discovery) .market-topics__groups {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0 20px;
  }
}
@media (max-width: 620px) {
  .market-topics:not(.is-discovery) .market-topics__groups,
  .is-discovery .market-topics__groups {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0 18px;
  }
  .market-topics {
    margin-top: 22px;
  }
  .market-topic__tags > * {
    min-height: 36px;
    display: flex;
    align-items: center;
  }
}
</style>
