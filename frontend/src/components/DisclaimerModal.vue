<script setup lang="ts">
import { ref, onMounted } from 'vue'

const DISCLAIMER_ACK_KEY = 'mofox_market_disclaimer_ack_v1'
const DISCLAIMER_DELAY_SECONDS = 3

const visible = ref(false)
const remaining = ref(DISCLAIMER_DELAY_SECONDS)
const disabled = ref(true)
let timer: ReturnType<typeof setInterval> | null = null

function hasAccepted() {
  try { return localStorage.getItem(DISCLAIMER_ACK_KEY) === '1' }
  catch { return false }
}

function markAccepted() {
  try { localStorage.setItem(DISCLAIMER_ACK_KEY, '1') }
  catch {}
}

function close() {
  if (disabled.value) return
  if (timer !== null) clearInterval(timer)
  markAccepted()
  visible.value = false
  document.body.classList.remove('modal-open')
}

onMounted(() => {
  if (hasAccepted()) return
  visible.value = true
  document.body.classList.add('modal-open')
  timer = setInterval(() => {
    remaining.value -= 1
    if (remaining.value <= 0) {
      if (timer !== null) clearInterval(timer)
      disabled.value = false
    }
  }, 1000)
})
</script>

<template>
  <div v-if="visible" class="disclaimer-overlay">
    <div class="disclaimer-modal" role="dialog" aria-modal="true" aria-labelledby="disclaimer-title">
      <div class="disclaimer-kicker">MoFox-Studio</div>
      <h2 id="disclaimer-title">首次使用安全提示</h2>
      <div class="disclaimer-copy">
        <p>插件市场中的所有插件均由用户自行上传，可能包含安全风险、兼容性问题或恶意代码。</p>
        <p>在安装或使用任何插件前，请务必确认你信任该插件的发布者，并且已经阅读过源码。</p>
        <p>因使用第三方插件造成的任何数据丢失、账号风险、设备损坏或其他损失，MoFox-Studio 不承担责任。</p>
      </div>
      <div class="disclaimer-actions">
        <button
          type="button"
          class="btn btn-primary"
          :disabled="disabled"
          @click="close"
        >{{ disabled ? `我已知悉（${remaining}s）` : '我已知悉' }}</button>
      </div>
    </div>
  </div>
</template>
