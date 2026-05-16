/**
 * Utility functions for formatting and display
 */

export function formatNumber(n: number | string | null | undefined): string {
  const num = Number(n || 0)
  if (num >= 1e6) return (num / 1e6).toFixed(1) + 'M'
  if (num >= 1e3) return (num / 1e3).toFixed(1) + 'k'
  return String(num)
}

export function formatBytes(n: number | string | null | undefined): string {
  const num = Number(n || 0)
  if (num < 1024) return num + ' B'
  if (num < 1048576) return (num / 1024).toFixed(1) + ' KB'
  return (num / 1048576).toFixed(2) + ' MB'
}

export function parseApiDate(value: unknown): Date | null {
  if (!value) return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value
  const text = String(value).trim()
  if (!text) return null
  const normalized = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(text)
    ? text.replace(' ', 'T') + 'Z'
    : text
  const parsed = new Date(normalized)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

export function formatRelative(value: unknown): string {
  const parsed = parseApiDate(value)
  if (!parsed) return '\u2014'
  const diff = Math.max(0, Date.now() - parsed.getTime())
  const m = 60000, h = 3600000, d = 86400000
  if (diff < m) return '刚刚'
  if (diff < h) return Math.floor(diff / m) + ' 分钟前'
  if (diff < d) return Math.floor(diff / h) + ' 小时前'
  if (diff < 30 * d) return Math.floor(diff / d) + ' 天前'
  if (diff < 365 * d) return Math.floor(diff / (30 * d)) + ' 个月前'
  return Math.floor(diff / (365 * d)) + ' 年前'
}

export function formatDate(v: unknown): string {
  const parsed = parseApiDate(v)
  return parsed ? parsed.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '\u2014'
}

export function formatUptime(seconds: number | string | null | undefined): string {
  const total = Number(seconds || 0)
  const days = Math.floor(total / 86400)
  const hours = Math.floor((total % 86400) / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  if (days > 0) return `${days}d ${hours}h`
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

export function escapeHtml(value: unknown): string {
  const map: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }
  return String(value ?? '').replace(/[&<>"']/g, (c) => map[c] || c)
}

export const CATEGORY_LABELS: Readonly<Record<string, string>> = Object.freeze({
  ai: 'AI增强',
  automation: '自动化',
  chat: '聊天互动',
  dev: '开发辅助',
  devtools: '开发工具',
  education: '学习教育',
  fun: '休闲娱乐',
  game: '游戏相关',
  image: '图像处理',
  information: '信息资讯',
  life: '生活服务',
  media: '音视频',
  moderation: '社区管理',
  productivity: '效率办公',
  social: '社交互动',
  tool: '实用工具',
  tools: '工具合集',
  utility: '实用增强',
})

export const EDITABLE_PLUGIN_CATEGORIES = Object.freeze([
  'chat',
  'fun',
  'information',
  'moderation',
  'tool',
])

export function categoryLabel(value: string | null | undefined): string {
  const raw = String(value ?? '').trim()
  if (!raw) return ''
  return CATEGORY_LABELS[raw] || CATEGORY_LABELS[raw.toLowerCase()] || raw
}

export function statusText(status: string | null | undefined): string {
  const labels: Record<string, string> = {
    published: '已上架',
    pending_review: '待审核',
    draft: '已退回',
    deprecated: '已下架',
    blocked: '已封禁',
    archived: '已归档',
    submitted: '已提交',
    yanked: '已撤回',
  }
  return labels[status || ''] || status || '-'
}

export function reviewActionText(action: string | null | undefined): string {
  const labels: Record<string, string> = {
    register_plugin: '注册插件',
    update_plugin: '更新插件',
    submit_version: '提交版本',
    approve_plugin: '重新上架',
    reject_plugin: '退回插件',
    block_plugin: '封禁插件',
    deprecate_plugin: '下架插件',
    archive_plugin: '归档插件',
    approve_version: '恢复版本',
    reject_version: '退回版本',
    yank_version: '下架版本',
    block_version: '封禁版本',
    sync_version: '同步版本',
    webhook_received: 'Webhook 事件',
  }
  return labels[action || ''] || action || '-'
}

export function trustLevelLabel(level: string | null | undefined): string {
  const labels: Record<string, string> = { official: '官方', verified: '认证', community: '社区' }
  return labels[level || ''] || level || '-'
}

export function starPercent(score: number | string | null | undefined): number {
  return (Math.max(0, Math.min(5, Number(score) || 0)) / 5) * 100
}
