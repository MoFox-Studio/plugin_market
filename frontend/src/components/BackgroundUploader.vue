<script setup lang="ts">
import { computed, ref, onBeforeUnmount } from 'vue';
import api from '@/api';
import { useToastStore } from '@/stores/toast';

const props = withDefaults(
  defineProps<{
    modelValue: string | null;
    disabled?: boolean;
  }>(),
  {
    modelValue: null,
    disabled: false,
  },
);

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | null): void;
  (e: 'uploaded', value: string): void;
  (e: 'busy-change', value: boolean): void;
}>();

const toast = useToastStore();
const fileInput = ref<HTMLInputElement | null>(null);
const uploading = ref(false);
let disposed = false;
onBeforeUnmount(() => {
  disposed = true;
});

const error = computed(() => {
  if (!props.modelValue) return '';
  if (props.modelValue.startsWith('/plugin-media/')) return '';
  return /^https:\/\//i.test(props.modelValue)
    ? ''
    : '请使用 https URL，或者直接上传文件。';
});

const isUpload = computed(() =>
  Boolean(props.modelValue?.startsWith('/plugin-media/')),
);

function pickFile(): void {
  if (!props.disabled && !uploading.value) fileInput.value?.click();
}

async function onFileChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!file || props.disabled || uploading.value) return;
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
    toast.show('请选择 PNG、JPEG 或 WEBP 图片', 'error');
    return;
  }
  if (file.size > 5 * 1024 * 1024) {
    toast.show('图片不能超过 5 MiB', 'error');
    return;
  }
  uploading.value = true;
  emit('busy-change', true);
  try {
    const profile = await api.me.profile.uploadBackground(file);
    if (disposed) return;
    if (profile.background_image_url) {
      emit('update:modelValue', profile.background_image_url);
      emit('uploaded', profile.background_image_url);
      toast.show('背景图已上传', 'ok');
    }
  } catch (e) {
    if (!disposed) toast.show((e as Error).message || '上传失败', 'error');
  } finally {
    uploading.value = false;
    if (!disposed) emit('busy-change', false);
  }
}

function clearImage(): void {
  emit('update:modelValue', null);
}
</script>

<template>
  <section class="bg-uploader">
    <div class="bg-uploader-row">
      <input
        class="bg-uploader-input"
        type="text"
        inputmode="url"
        aria-label="背景图片链接"
        :aria-invalid="!!error"
        :value="modelValue || ''"
        :disabled="disabled || uploading"
        :placeholder="
          isUpload
            ? '/plugin-media/profile_backgrounds/...'
            : 'https://cdn.example.com/creator-bg.jpg'
        "
        @input="
          emit(
            'update:modelValue',
            ($event.target as HTMLInputElement).value || null,
          )
        "
      />
      <button
        type="button"
        class="btn btn-sm"
        :disabled="disabled || uploading"
        @click="pickFile"
      >
        {{ uploading ? '上传中…' : '上传图片' }}
      </button>
      <button
        v-if="modelValue"
        type="button"
        class="btn btn-ghost btn-sm"
        :disabled="disabled || uploading"
        @click="clearImage"
      >
        清除
      </button>
      <input
        ref="fileInput"
        class="bg-uploader-file"
        type="file"
        accept="image/png,image/jpeg,image/webp"
        @change="onFileChange"
      />
    </div>

    <p v-if="error" class="bg-uploader-error">{{ error }}</p>
    <p class="bg-uploader-hint">
      支持 PNG / JPEG / WEBP，单张不超过 5 MiB；上传会替换之前的图片。
    </p>

    <div class="bg-uploader-preview">
      <img
        v-if="modelValue && !error"
        :src="modelValue"
        alt="背景图片预览"
        class="bg-uploader-image"
      />
      <span class="bg-uploader-kicker">PREVIEW</span>
      <strong v-if="modelValue && !error && isUpload">已上传自定义背景</strong>
      <strong v-else-if="modelValue && !error">使用外部 URL 背景</strong>
      <strong v-else-if="error">链接无效</strong>
      <strong v-else>未设置 · 使用默认蓝调渐变</strong>
    </div>
  </section>
</template>

<style scoped>
.bg-uploader {
  display: grid;
  gap: 10px;
}
.bg-uploader-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.bg-uploader-input {
  flex: 1;
  min-width: 180px;
  width: 100%;
  padding: 11px 12px;
  border: 1px solid var(--line);
  border-radius: 3px;
  background: var(--surface);
  font: 12px var(--font-mono);
  color: var(--ink-900);
}
.bg-uploader-input:focus {
  outline: 2px solid var(--blue-500);
  outline-offset: 2px;
}
.bg-uploader-input:disabled {
  opacity: 0.6;
}
.bg-uploader-file {
  display: none;
}
.bg-uploader-error {
  margin: 0;
  color: var(--danger);
  font-size: 12px;
}
.bg-uploader-hint {
  margin: 0;
  color: var(--ink-500);
  font-size: 11px;
  line-height: 1.7;
}
.bg-uploader-preview {
  position: relative;
  height: 150px;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: linear-gradient(120deg, var(--blue-700), var(--blue-500));
  display: flex;
  align-items: end;
  padding: 18px;
  overflow: hidden;
  color: var(--ink-on-blue);
}
.bg-uploader-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.bg-uploader-preview:after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.65));
}
.bg-uploader-kicker {
  position: absolute;
  top: 14px;
  left: 18px;
  z-index: 1;
  padding: 4px 6px;
  background: rgba(0, 0, 0, 0.45);
  font: 9px var(--font-mono);
  letter-spacing: 0.15em;
  color: white;
}
.bg-uploader-preview strong {
  position: relative;
  z-index: 1;
  color: white;
  font-size: 12px;
  font-weight: 500;
}
@media (max-width: 500px) {
  .bg-uploader-input {
    flex-basis: 100%;
  }
}
</style>
