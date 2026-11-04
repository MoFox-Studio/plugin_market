<script setup lang="ts">
import { computed } from 'vue';
import { formatRelative } from '@/utils/format';
import { parseMentionsRoundTrip } from '@/utils/mentions';
import type { Comment, SkillComment } from '@/types';
const props = defineProps<{
  comment: Comment | SkillComment;
  removable?: boolean;
  deleting?: boolean;
}>();
defineEmits<{ remove: [] }>();
const segments = computed(() =>
  parseMentionsRoundTrip(
    props.comment.content,
    'mentions' in props.comment ? props.comment.mentions || [] : [],
  ),
);
</script>
<template>
  <article :id="`comment-${comment.id}`" class="catalog-comment">
    <router-link
      class="comment-avatar"
      :to="`/author/${encodeURIComponent(comment.author.author_id)}`"
      :aria-label="`查看 ${comment.author.display_name}`"
      ><img
        v-if="comment.author.avatar_url"
        :src="comment.author.avatar_url"
        alt=""
        loading="lazy"
      /><span v-else>{{
        comment.author.display_name?.[0]?.toUpperCase() || '?'
      }}</span></router-link
    >
    <div class="comment-body">
      <header>
        <router-link
          :to="`/author/${encodeURIComponent(comment.author.author_id)}`"
          >{{ comment.author.display_name }}</router-link
        ><span v-if="comment.author.is_admin">管理员</span
        ><time :datetime="comment.created_at">{{
          formatRelative(comment.created_at)
        }}</time>
      </header>
      <p v-if="comment.is_deleted" class="deleted">这条评论已删除</p>
      <p v-else>
        <template v-for="(segment, index) in segments" :key="index"
          ><router-link
            v-if="segment.type === 'mention' && segment.mention"
            class="mention"
            :to="`/author/${encodeURIComponent(segment.mention.author_id)}`"
            >{{ segment.text }}</router-link
          ><span v-else>{{ segment.text }}</span></template
        >
      </p>
      <button
        v-if="removable && !comment.is_deleted"
        class="comment-remove"
        :disabled="deleting"
        @click="$emit('remove')"
      >
        {{ deleting ? '删除中…' : '删除' }}
      </button>
    </div>
  </article>
</template>
<style scoped>
.catalog-comment {
  display: flex;
  gap: 13px;
  padding: 22px 0;
  border-bottom: 1px solid var(--line-soft);
  scroll-margin-top: 100px;
}
.comment-avatar {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  flex: none;
  background: var(--surface-soft);
  border: 1px solid var(--line);
  border-radius: 50%;
  overflow: hidden;
  font-size: 13px;
  color: var(--blue-700);
}
.comment-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.comment-body {
  min-width: 0;
  flex: 1;
}
.comment-body header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.comment-body header > a {
  font-weight: 650;
}
.comment-body header > span {
  color: var(--blue-700);
  font-size: 10px;
}
.comment-body time {
  font-size: 10px;
  color: var(--ink-500);
}
.comment-body p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  margin: 9px 0 0;
  line-height: 1.8;
  font-size: 13px;
  color: var(--ink-700);
}
.comment-body .deleted {
  color: var(--ink-500);
}
.mention {
  color: var(--blue-600);
}
.comment-remove {
  font-size: 11px;
  color: var(--ink-500);
  padding: 7px 0 0;
}
.comment-remove:hover {
  color: var(--danger-ink);
}
</style>
