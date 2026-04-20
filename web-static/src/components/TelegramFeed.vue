<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { initKey, decryptToUrl, hasKey } from '@/utils/telegramDecrypt'

// ── 数据加载 ───────────────────────────────────────────────────────────────
const messages = ref([])
const loading = ref(true)
const error = ref('')

const baseUrl = import.meta.env.BASE_URL.replace(/\/$/, '')

fetch(`${baseUrl}/data/telegram_forwards.json`)
  .then(r => r.json())
  .then(data => { messages.value = data.messages || [] })
  .catch(() => { error.value = '无法加载数据' })
  .finally(() => { loading.value = false })

// ── 密码解锁 ───────────────────────────────────────────────────────────────
const password = ref('')
const keyReady = ref(hasKey())
const unlocking = ref(false)
const passwordError = ref('')

async function unlock() {
  if (!password.value.trim()) return
  unlocking.value = true
  passwordError.value = ''
  try {
    await initKey(password.value)
    keyReady.value = true
    password.value = ''
    // key 就绪后立即触发所有已挂载卡片的媒体加载
    for (const g of feedGroups.value) {
      loadGroup(g)
    }
  } catch {
    passwordError.value = '初始化失败，请重试'
  } finally {
    unlocking.value = false
  }
}

// ── 媒体分组（media_group_id 合并为相册）────────────────────────────────────
const feedGroups = computed(() => {
  const sorted = [...messages.value].sort((a, b) => b.date - a.date)
  const groups = []
  const seen = new Map()

  for (const msg of sorted) {
    if (msg.media_group_id) {
      if (seen.has(msg.media_group_id)) {
        seen.get(msg.media_group_id).items.push(msg)
      } else {
        const g = {
          key: msg.media_group_id,
          date: msg.date,
          caption: msg.caption,
          forward_from_chat: msg.forward_from_chat,
          forward_origin: msg.forward_origin,
          isAlbum: true,
          items: [msg],
        }
        seen.set(msg.media_group_id, g)
        groups.push(g)
      }
    } else {
      groups.push({
        key: String(msg.message_id),
        date: msg.date,
        caption: msg.caption,
        forward_from_chat: msg.forward_from_chat,
        forward_origin: msg.forward_origin,
        isAlbum: false,
        items: [msg],
      })
    }
  }
  return groups
})

const total = computed(() => feedGroups.value.length)

// ── 媒体解密缓存 ───────────────────────────────────────────────────────────
const urlCache = ref({})   // file_unique_id → objectUrl | 'error' | 'loading'

async function loadMedia(msg) {
  const path = msg.media_file?.local_path
  const uid = msg.media_meta?.file_unique_id
  if (!path || !uid || !keyReady.value) return
  if (urlCache.value[uid]) return
  urlCache.value[uid] = 'loading'
  try {
    urlCache.value[uid] = await decryptToUrl(path)
  } catch {
    urlCache.value[uid] = 'error'
  }
}

async function loadGroup(group) {
  if (!keyReady.value) return
  for (const msg of group.items) {
    await loadMedia(msg)
  }
}

// ── 工具函数 ───────────────────────────────────────────────────────────────
function formatDate(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return d.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function channelName(group) {
  return (
    group.forward_origin?.chat?.title ||
    group.forward_from_chat?.title ||
    '未知来源'
  )
}

function channelUsername(group) {
  return (
    group.forward_origin?.chat?.username ||
    group.forward_from_chat?.username ||
    null
  )
}

function formatDuration(sec) {
  if (!sec) return ''
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

function formatSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

// 相册布局：取前4张，超出显示 +N
function albumSlots(group) {
  const items = group.items.filter(m => m.media_file)
  return { visible: items.slice(0, 4), extra: Math.max(0, items.length - 4) }
}

onUnmounted(() => {
  Object.values(urlCache.value).forEach(u => {
    if (u && u !== 'loading' && u !== 'error') URL.revokeObjectURL(u)
  })
})
</script>

<template>
  <div class="tg-page">
    <div class="tg-shell">

      <!-- 头部卡片 -->
      <div class="tg-header-card">
        <div class="tg-header-top">
          <div class="tg-header-title">
            <span class="tg-eyebrow">TELEGRAM</span>
            <h1 class="tg-title">转发归档</h1>
          </div>
          <div class="tg-stats" v-if="!loading">
            <span class="tg-stat-item">{{ total }} 条内容</span>
            <span class="tg-stat-dot">·</span>
            <span class="tg-stat-item">{{ messages.length }} 条消息</span>
          </div>
        </div>

        <!-- 密码解锁区 -->
        <div class="tg-unlock" v-if="!keyReady">
          <div class="tg-unlock-hint">媒体文件已加密，输入密码后可查看图片</div>
          <form class="tg-unlock-form" @submit.prevent="unlock">
            <input
              v-model="password"
              type="password"
              class="tg-password-input"
              placeholder="输入解密密码"
              autocomplete="current-password"
            />
            <button type="submit" class="tg-unlock-btn" :disabled="unlocking">
              {{ unlocking ? '解密中…' : '解锁' }}
            </button>
          </form>
          <div class="tg-unlock-error" v-if="passwordError">{{ passwordError }}</div>
        </div>

        <div class="tg-unlock-ok" v-else>
          <svg viewBox="0 0 24 24" class="tg-lock-icon"><path d="M18 8h-1V6A5 5 0 0 0 7 6v2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10a2 2 0 0 0-2-2zM12 17a2 2 0 1 1 2-2 2 2 0 0 1-2 2zm3.1-9H8.9V6a3.1 3.1 0 0 1 6.2 0z"/></svg>
          <span>媒体已解锁</span>
        </div>
      </div>

      <!-- 加载中 / 错误 -->
      <div class="tg-status" v-if="loading">加载中…</div>
      <div class="tg-status tg-error" v-else-if="error">{{ error }}</div>
      <div class="tg-status" v-else-if="feedGroups.length === 0">暂无归档内容</div>

      <!-- Feed 列表 -->
      <div class="tg-feed" v-else>
        <div
          v-for="group in feedGroups"
          :key="group.key"
          class="tg-card"
          @vue:mounted="loadGroup(group)"
        >
          <!-- 来源信息 -->
          <div class="tg-card-meta">
            <div class="tg-source">
              <span class="tg-source-name">{{ channelName(group) }}</span>
              <a
                v-if="channelUsername(group)"
                :href="`https://t.me/${channelUsername(group)}`"
                target="_blank"
                class="tg-source-username"
              >@{{ channelUsername(group) }}</a>
            </div>
            <span class="tg-card-date">{{ formatDate(group.date) }}</span>
          </div>

          <!-- 相册布局 -->
          <template v-if="group.isAlbum">
            <div
              class="tg-album"
              :class="`tg-album-${Math.min(albumSlots(group).visible.length, 4)}`"
            >
              <div
                v-for="(msg, idx) in albumSlots(group).visible"
                :key="msg.message_id"
                class="tg-album-slot"
                :class="{ 'tg-album-slot-last': idx === 3 && albumSlots(group).extra > 0 }"
              >
                <img
                  v-if="urlCache[msg.media_meta?.file_unique_id] && urlCache[msg.media_meta?.file_unique_id] !== 'loading' && urlCache[msg.media_meta?.file_unique_id] !== 'error'"
                  :src="urlCache[msg.media_meta?.file_unique_id]"
                  class="tg-img"
                  loading="lazy"
                />
                <div v-else-if="!keyReady" class="tg-placeholder tg-placeholder-locked">
                  <svg viewBox="0 0 24 24"><path d="M18 8h-1V6A5 5 0 0 0 7 6v2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10a2 2 0 0 0-2-2z"/></svg>
                </div>
                <div v-else-if="urlCache[msg.media_meta?.file_unique_id] === 'error'" class="tg-placeholder tg-placeholder-error">
                  <svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm1 15h-2v-2h2zm0-4h-2V7h2z"/></svg>
                </div>
                <div v-else class="tg-placeholder tg-placeholder-loading">
                  <div class="tg-spinner" />
                </div>
                <!-- +N 遮罩 -->
                <div v-if="idx === 3 && albumSlots(group).extra > 0" class="tg-extra-overlay">
                  +{{ albumSlots(group).extra }}
                </div>
              </div>
            </div>
          </template>

          <!-- 单条消息 -->
          <template v-else>
            <div v-for="msg in group.items" :key="msg.message_id">

              <!-- 图片 -->
              <div v-if="msg.type === 'photo' && msg.media_file" class="tg-single-media">
                <img
                  v-if="urlCache[msg.media_meta?.file_unique_id] && urlCache[msg.media_meta?.file_unique_id] !== 'loading' && urlCache[msg.media_meta?.file_unique_id] !== 'error'"
                  :src="urlCache[msg.media_meta?.file_unique_id]"
                  class="tg-img tg-img-single"
                />
                <div v-else-if="!keyReady" class="tg-placeholder tg-placeholder-locked tg-placeholder-tall">
                  <svg viewBox="0 0 24 24"><path d="M18 8h-1V6A5 5 0 0 0 7 6v2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10a2 2 0 0 0-2-2z"/></svg>
                </div>
                <div v-else-if="urlCache[msg.media_meta?.file_unique_id] === 'error'" class="tg-placeholder tg-placeholder-error tg-placeholder-tall">
                  <svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm1 15h-2v-2h2zm0-4h-2V7h2z"/></svg>
                </div>
                <div v-else class="tg-placeholder tg-placeholder-loading tg-placeholder-tall">
                  <div class="tg-spinner" />
                </div>
              </div>

              <!-- 视频 -->
              <div v-else-if="msg.type === 'video'" class="tg-video-card">
                <div class="tg-video-thumb">
                  <img
                    v-if="msg.media_file && urlCache[msg.media_meta?.file_unique_id] && urlCache[msg.media_meta?.file_unique_id] !== 'loading' && urlCache[msg.media_meta?.file_unique_id] !== 'error'"
                    :src="urlCache[msg.media_meta?.file_unique_id]"
                    class="tg-img"
                  />
                  <div v-else class="tg-placeholder" :class="keyReady ? 'tg-placeholder-loading' : 'tg-placeholder-locked'">
                    <div v-if="keyReady && urlCache[msg.media_meta?.file_unique_id] !== 'error'" class="tg-spinner" />
                    <svg v-else viewBox="0 0 24 24"><path d="M18 8h-1V6A5 5 0 0 0 7 6v2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10a2 2 0 0 0-2-2z"/></svg>
                  </div>
                  <div class="tg-play-badge">
                    <svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                  </div>
                </div>
                <div class="tg-video-meta">
                  <span v-if="msg.media_meta?.duration" class="tg-video-info">
                    {{ formatDuration(msg.media_meta.duration) }}
                  </span>
                  <span v-if="msg.media_meta?.file_size" class="tg-video-info">
                    {{ formatSize(msg.media_meta.file_size) }}
                  </span>
                  <span v-if="msg.media_meta?.file_name" class="tg-video-info tg-video-name">
                    {{ msg.media_meta.file_name }}
                  </span>
                </div>
              </div>

              <!-- 纯文本 -->
              <div v-else-if="msg.type === 'text' && msg.text" class="tg-text-body">
                {{ msg.text }}
              </div>

            </div>
          </template>

          <!-- Caption -->
          <div v-if="group.caption" class="tg-caption">{{ group.caption }}</div>
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
/* ── 布局 ─────────────────────────────────────────────────────────────── */
.tg-page {
  min-height: 100vh;
  background: var(--bg-color);
  padding: 16px;
  box-sizing: border-box;
}

.tg-shell {
  max-width: 680px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ── 头部卡片 ─────────────────────────────────────────────────────────── */
.tg-header-card {
  background: var(--row-bg);
  border: 1px solid var(--row-border);
  border-radius: 8px;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.tg-header-top {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.tg-eyebrow {
  display: block;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--primary-color);
  opacity: 0.7;
  margin-bottom: 4px;
}

.tg-title {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  color: var(--text-color);
  line-height: 1.2;
}

.tg-stats {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.tg-stat-item {
  font-size: 12px;
  color: var(--text-color);
  opacity: 0.55;
}

.tg-stat-dot {
  opacity: 0.3;
  font-size: 12px;
}

/* 解锁区 */
.tg-unlock-hint {
  font-size: 12px;
  color: var(--text-color);
  opacity: 0.55;
}

.tg-unlock-form {
  display: flex;
  gap: 8px;
}

.tg-password-input {
  flex: 1;
  height: 34px;
  padding: 0 12px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: var(--bg-color);
  color: var(--text-color);
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s;
}

.tg-password-input:focus {
  border-color: var(--primary-color);
}

.tg-unlock-btn {
  height: 34px;
  padding: 0 16px;
  border-radius: 6px;
  border: 1px solid var(--primary-color);
  background: rgba(100, 108, 255, 0.15);
  color: var(--primary-color);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
  white-space: nowrap;
}

.tg-unlock-btn:hover:not(:disabled) {
  background: rgba(100, 108, 255, 0.28);
}

.tg-unlock-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.tg-unlock-error {
  font-size: 12px;
  color: #e28a8a;
}

.tg-unlock-ok {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #4caf50;
}

.tg-lock-icon {
  width: 14px;
  height: 14px;
  fill: currentColor;
  flex-shrink: 0;
}

/* ── 状态 ─────────────────────────────────────────────────────────────── */
.tg-status {
  text-align: center;
  padding: 40px;
  color: var(--text-color);
  opacity: 0.45;
  font-size: 14px;
}

.tg-error { color: #e28a8a; opacity: 1; }

/* ── Feed 卡片 ────────────────────────────────────────────────────────── */
.tg-feed {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tg-card {
  background: var(--row-bg);
  border: 1px solid var(--row-border);
  border-radius: 8px;
  overflow: hidden;
}

.tg-card-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  gap: 10px;
  border-bottom: 1px solid var(--row-border);
}

.tg-source {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
}

.tg-source-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tg-source-username {
  font-size: 11px;
  color: var(--primary-color);
  opacity: 0.75;
  text-decoration: none;
  white-space: nowrap;
}

.tg-source-username:hover { opacity: 1; }

.tg-card-date {
  font-size: 11px;
  color: var(--text-color);
  opacity: 0.4;
  white-space: nowrap;
  flex-shrink: 0;
}

/* ── 图片/占位符 ──────────────────────────────────────────────────────── */
.tg-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.tg-img-single {
  max-height: 420px;
  object-fit: contain;
  background: #000;
}

.tg-single-media {
  line-height: 0;
}

.tg-placeholder {
  width: 100%;
  height: 100%;
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tg-placeholder-tall { min-height: 220px; }

.tg-placeholder svg {
  width: 28px;
  height: 28px;
  fill: currentColor;
  opacity: 0.3;
}

.tg-placeholder-locked {
  background: var(--surface-color);
  color: var(--text-color);
}

.tg-placeholder-error {
  background: rgba(220, 80, 80, 0.06);
  color: #e28a8a;
}

.tg-placeholder-loading {
  background: var(--surface-color);
}

.tg-spinner {
  width: 22px;
  height: 22px;
  border: 2px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── 相册布局 ─────────────────────────────────────────────────────────── */
.tg-album {
  display: grid;
  gap: 2px;
  aspect-ratio: 16/10;
}

.tg-album-1 { grid-template-columns: 1fr; }
.tg-album-2 { grid-template-columns: 1fr 1fr; }
.tg-album-3 { grid-template-columns: 2fr 1fr; grid-template-rows: 1fr 1fr; }
.tg-album-3 .tg-album-slot:first-child { grid-row: span 2; }
.tg-album-4 { grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }

.tg-album-slot {
  overflow: hidden;
  position: relative;
  background: var(--surface-color);
}

.tg-album-slot-last .tg-img { filter: brightness(0.45); }

.tg-extra-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 800;
  color: #fff;
  pointer-events: none;
}

/* ── 视频卡片 ─────────────────────────────────────────────────────────── */
.tg-video-card {
  display: flex;
  gap: 12px;
  padding: 12px 14px;
  align-items: flex-start;
}

.tg-video-thumb {
  position: relative;
  width: 120px;
  height: 80px;
  border-radius: 6px;
  overflow: hidden;
  flex-shrink: 0;
  background: var(--surface-color);
}

.tg-video-thumb .tg-img { object-fit: cover; }
.tg-video-thumb .tg-placeholder { min-height: unset; height: 100%; }

.tg-play-badge {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.3);
}

.tg-play-badge svg {
  width: 28px;
  height: 28px;
  fill: rgba(255, 255, 255, 0.9);
  filter: drop-shadow(0 1px 3px rgba(0,0,0,0.5));
}

.tg-video-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 4px;
}

.tg-video-info {
  font-size: 12px;
  color: var(--text-color);
  opacity: 0.55;
}

.tg-video-name {
  opacity: 0.4;
  font-size: 11px;
  word-break: break-all;
}

/* ── Caption / 文本 ───────────────────────────────────────────────────── */
.tg-caption {
  padding: 10px 14px;
  font-size: 13px;
  color: var(--text-color);
  opacity: 0.8;
  line-height: 1.6;
  border-top: 1px solid var(--row-border);
  white-space: pre-wrap;
  word-break: break-word;
}

.tg-text-body {
  padding: 12px 14px;
  font-size: 13px;
  color: var(--text-color);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── 响应式 ───────────────────────────────────────────────────────────── */
@media (max-width: 600px) {
  .tg-page { padding: 10px; }
  .tg-shell { gap: 10px; }
  .tg-header-card { padding: 12px 14px; }
  .tg-title { font-size: 18px; }
  .tg-video-thumb { width: 90px; height: 60px; }
  .tg-unlock-form { flex-direction: column; }
  .tg-unlock-btn { height: 36px; }
}
</style>
