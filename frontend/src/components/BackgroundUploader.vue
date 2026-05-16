<script setup lang="ts">
import { computed, ref } from 'vue'
import api from '@/api'
import { useToastStore } from '@/stores/toast'

const props = withDefaults(defineProps<{
  modelValue: string | null
  disabled?: boolean
}>(), {
  modelValue: null,
  disabled: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | null): void
  (e: 'uploaded', value: string): void
}>()

const toast = useToastStore()
const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)

const error = computed(() => {
  if (!props.modelValue) return ''
  if (props.modelValue.startsWith('/plugin-media/')) return ''
  return /^https:\/\//i.test(props.modelValue) ? '' : '请使用 https URL，或者直接上传文件。'
})

const isUpload = computed(() => Boolean(props.modelValue?.startsWith('/plugin-media/')))

function pickFile(): void {
  fileInput.value?.click()
}

async function onFileChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (file.size > 5 * 1024 * 1024) {
    toast.show('图片不能超过 5 MiB', 'error')
    return
  }
  uploading.value = true
  try {
    const profile = await api.me.profile.uploadBackground(file)
    if (profile.background_image_url) {
      emit('update:modelValue', profile.background_image_url)
      emit('uploaded', profile.background_image_url)
      toast.show('背景图已上传', 'ok')
    }
  } catch (e) {
    toast.show((e as Error).message || '上传失败', 'error')
  } finally {
    uploading.value = false
  }
}

function clearImage(): void {
  emit('update:modelValue', null)
}
</script>

<template>
  <section class="bg-uploader">
    <div class="bg-uploader-row">
      <input
        class="bg-uploader-input"
        type="url"
        :value="modelValue || ''"
        :disabled="disabled || uploading"
        :placeholder="isUpload ? '/plugin-media/profile_backgrounds/...' : 'https://cdn.example.com/creator-bg.jpg'"
        @input="emit('update:modelValue', ($event.target as HTMLInputElement).value || null)"
      >
      <button
        type="button"
        class="btn btn-sm"
        :disabled="disabled || uploading"
        @click="pickFile"
      >{{ uploading ? '上传中…' : '上传图片' }}</button>
      <button
        v-if="modelValue"
        type="button"
        class="btn btn-ghost btn-sm"
        :disabled="disabled || uploading"
        @click="clearImage"
      >清除</button>
      <input
        ref="fileInput"
        class="bg-uploader-file"
        type="file"
        accept="image/png,image/jpeg,image/webp"
        @change="onFileChange"
      >
    </div>

    <p v-if="error" class="bg-uploader-error">{{ error }}</p>
    <p class="bg-uploader-hint">支持 PNG / JPEG / WEBP，单张不超过 5 MiB；上传会替换之前的图片。</p>

    <div
      class="bg-uploader-preview"
      :style="modelValue && !error ? { backgroundImage: `linear-gradient(135deg, rgba(11,18,32,0.65), rgba(11,18,32,0.25)), url(${modelValue})` } : undefined"
    >
      <span class="bg-uploader-kicker">PREVIEW</span>
      <strong v-if="modelValue && !error && isUpload">已上传自定义背景</strong>
      <strong v-else-if="modelValue && !error">使用外部 URL 背景</strong>
      <strong v-else-if="error">链接无效</strong>
      <strong v-else>未设置 · 使用默认蓝调渐变</strong>
    </div>
  </section>
</template>

<style scoped>
.bg-uploader { display: grid; gap: 8px; }

.bg-uploader-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 8px;
  align-items: center;
}
@media (max-width: 600px) {
  .bg-uploader-row { grid-template-columns: 1fr; }
}

.bg-uploader-input {
  width: 100%;
  padding: 10px 12px;
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--surface);
  font: inherit;
  font-size: 13.5px;
  color: var(--ink-900);
  font-family: var(--font-mono);
  transition: border-color var(--dur-fast), box-shadow var(--dur-fast);
  min-width: 0;
}
.bg-uploader-input:focus { outline: none; border-color: var(--blue-500); box-shadow: var(--ring); }
.bg-uploader-input:disabled { opacity: 0.6; cursor: not-allowed; }

.bg-uploader-file { display: none; }

.bg-uploader-error { margin: 0; color: var(--coral); font-size: 12px; }
.bg-uploader-hint { margin: 0; color: var(--ink-500); font-size: 11.5px; line-height: 1.5; }

.bg-uploader-preview {
  position: relative;
  height: 140px;
  border-radius: var(--radius-md);
  border: 1.5px solid var(--line);
  background: linear-gradient(135deg, var(--blue-700) 0%, var(--blue-500) 60%, #5fb8ff 110%);
  background-size: cover;
  background-position: center;
  display: flex; align-items: flex-end;
  padding: var(--space-3);
  color: #fff;
  overflow: hidden;
}
.bg-uploader-kicker {
  position: absolute; top: 10px; left: 12px;
  padding: 2px 8px;
  background: rgba(0, 0, 0, 0.4);
  border-radius: var(--radius-pill);
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 10px; color: #fff;
}
.bg-uploader-preview strong {
  font-family: var(--font-display); font-weight: 700;
  font-size: 14px;
  color: #fff;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
}
</style>
