<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { initKey, decryptToUrl, hasKey } from '@/utils/telegramDecrypt'

// ── Data loading ───────────────────────────────────────────────────────────
const messages   = ref([])
const loading    = ref(true)
const error      = ref('')
const baseUrl    = import.meta.env.BASE_URL.replace(/\/$/, '')

fetch(`${baseUrl}/data/telegram_forwards.json`)
  .then(r => r.json())
  .then(d => { messages.value = d.messages || [] })
  .catch(() => { error.value = '无法加载数据' })
  .finally(() => { loading.value = false })

// ── Password unlock ────────────────────────────────────────────────────────
const PW_KEY        = 'tg_dec_pw'
const password      = ref('')
const keyReady      = ref(hasKey())
const unlocking     = ref(false)
const passwordError = ref('')

async function unlock() {
  if (!password.value.trim()) return
  unlocking.value = true
  passwordError.value = ''
  try {
    await initKey(password.value)
    localStorage.setItem(PW_KEY, password.value)
    keyReady.value = true
    password.value = ''
    for (const g of activeGroups.value) loadGroup(g)
  } catch {
    passwordError.value = '密码错误'
  } finally {
    unlocking.value = false
  }
}

function forgetKey() {
  localStorage.removeItem(PW_KEY)
  keyReady.value = false
  Object.values(urlCache.value).forEach(u => { if (u && u !== 'loading' && u !== 'error') URL.revokeObjectURL(u) })
  urlCache.value = {}
}

async function tryRestoreKey() {
  const saved = localStorage.getItem(PW_KEY)
  if (!saved || keyReady.value) return
  try {
    await initKey(saved)
    keyReady.value = true
  } catch {
    localStorage.removeItem(PW_KEY)
  }
}

// ── Sources ────────────────────────────────────────────────────────────────
const searchQuery    = ref('')
const activeSourceId = ref(null)
const mobileView     = ref('list')   // 'list' | 'chat'
const chatBodyEl     = ref(null)

const sources = computed(() => {
  const map = new Map()
  for (const msg of messages.value) {
    const chat = msg.forward_from_chat ?? msg.forward_origin?.chat
    if (!chat?.id) continue
    if (!map.has(chat.id)) {
      map.set(chat.id, { id: chat.id, title: chat.title || '未知频道', username: chat.username || null, msgs: [], latestDate: 0, preview: '' })
    }
    const s = map.get(chat.id)
    s.msgs.push(msg)
    if (msg.date > s.latestDate) {
      s.latestDate = msg.date
      s.preview = msg.caption ?? msg.text ?? (
        msg.type === 'photo' ? '[图片]' : msg.type === 'video' ? '[视频]' : msg.type === 'animation' ? '[动图]' : '[媒体]'
      )
    }
  }
  return [...map.values()].sort((a, b) => b.latestDate - a.latestDate)
})

const filteredSources = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return sources.value
  return sources.value.filter(s => s.title.toLowerCase().includes(q) || s.username?.toLowerCase().includes(q))
})

const activeSource = computed(() =>
  sources.value.find(s => s.id === activeSourceId.value) ?? sources.value[0] ?? null
)

watch(sources, val => {
  if (!activeSourceId.value && val.length > 0) activeSourceId.value = val[0].id
}, { immediate: true })

watch(() => activeSource.value, async () => {
  await nextTick()
  if (chatBodyEl.value) chatBodyEl.value.scrollTop = chatBodyEl.value.scrollHeight
})

async function selectSource(src) {
  activeSourceId.value = src.id
  mobileView.value = 'chat'
  await nextTick()
  if (chatBodyEl.value) chatBodyEl.value.scrollTop = chatBodyEl.value.scrollHeight
  if (keyReady.value) for (const g of activeGroups.value) loadGroup(g)
}

// ── Message groups ─────────────────────────────────────────────────────────
const activeGroups = computed(() => {
  if (!activeSource.value) return []
  const sorted = [...activeSource.value.msgs].sort((a, b) => a.date - b.date)
  const groups = []
  const seen = new Map()
  for (const msg of sorted) {
    if (msg.media_group_id) {
      if (seen.has(msg.media_group_id)) {
        seen.get(msg.media_group_id).items.push(msg)
      } else {
        const g = { key: msg.media_group_id, date: msg.date, caption: msg.caption, isAlbum: true, items: [msg] }
        seen.set(msg.media_group_id, g)
        groups.push(g)
      }
    } else {
      groups.push({ key: String(msg.message_id), date: msg.date, caption: msg.caption, isAlbum: false, items: [msg] })
    }
  }
  return groups
})

const chatTimeline = computed(() => {
  const out = []
  let lastLabel = null
  for (const g of activeGroups.value) {
    const label = fmtDateLabel(g.date)
    if (label !== lastLabel) { out.push({ type: 'sep', key: `sep-${label}-${g.key}`, label }); lastLabel = label }
    out.push({ type: 'msg', key: g.key, group: g })
  }
  return out
})

// ── Media decrypt cache ────────────────────────────────────────────────────
const urlCache = ref({})

async function loadMedia(msg) {
  const path = msg.media_file?.local_path
  const uid  = msg.media_meta?.file_unique_id
  if (!path || !uid || !keyReady.value || urlCache.value[uid]) return
  urlCache.value[uid] = 'loading'
  try   { urlCache.value[uid] = await decryptToUrl(path) }
  catch { urlCache.value[uid] = 'error' }
}

async function loadGroup(group) {
  if (!keyReady.value) return
  for (const msg of group.items) await loadMedia(msg)
}

function isLoaded(uid) {
  const v = urlCache.value[uid]; return v && v !== 'loading' && v !== 'error'
}

function slotPhClass(uid) {
  if (!keyReady.value) return 'ph-locked'
  if (urlCache.value[uid] === 'error') return 'ph-error'
  return 'ph-loading'
}

// ── Album layout ───────────────────────────────────────────────────────────
function getAR(msg) {
  const w = msg.media_meta?.width, h = msg.media_meta?.height
  return (w && h && h > 0) ? w / h : 4 / 3
}

function computeAlbumRows(group) {
  const items = group.items.filter(m => m.media_file)
  if (!items.length) return []
  const visible = items.slice(0, 9)
  const extra = Math.max(0, items.length - 9)
  const vn = visible.length
  let rg
  if      (vn === 1) rg = [[0]]
  else if (vn === 2) rg = [[0,1]]
  else if (vn === 3) rg = [[0],[1,2]]
  else if (vn === 4) rg = [[0,1],[2,3]]
  else if (vn === 5) rg = [[0,1],[2,3,4]]
  else if (vn === 6) rg = [[0,1,2],[3,4,5]]
  else if (vn === 7) rg = [[0,1,2],[3,4],[5,6]]
  else if (vn === 8) rg = [[0,1],[2,3,4],[5,6,7]]
  else               rg = [[0,1,2],[3,4,5],[6,7,8]]
  return rg.map((indices, ri) => ({
    isSingle: indices.length === 1,
    items: indices.map((idx, ii) => ({
      msg: visible[idx],
      extra: ri === rg.length - 1 && ii === indices.length - 1 ? extra : 0,
    })),
  }))
}

function hasMedia(group) {
  if (group.isAlbum) return group.items.some(m => m.media_file)
  const m = group.items[0]
  return (m.type === 'photo' && m.media_file) || m.type === 'video' || m.type === 'animation'
}
function hasMediaNoCaption(group) {
  return hasMedia(group) && !group.caption && !group.items[0].text
}

// ── Lightbox ───────────────────────────────────────────────────────────────
const lightboxUrl = ref(null)
function openLightbox(uid) { const u = urlCache.value[uid]; if (u && u !== 'loading' && u !== 'error') lightboxUrl.value = u }
function closeLightbox() { lightboxUrl.value = null }
function onKeydown(e) { if (e.key === 'Escape') closeLightbox() }
onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  tryRestoreKey()
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  Object.values(urlCache.value).forEach(u => { if (u && u !== 'loading' && u !== 'error') URL.revokeObjectURL(u) })
})

// ── Formatters ─────────────────────────────────────────────────────────────
function fmtTime(ts) {
  return ts ? new Date(ts * 1000).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : ''
}
function fmtDateLabel(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000), now = new Date()
  now.setHours(0,0,0,0)
  const day = new Date(d); day.setHours(0,0,0,0)
  const diff = now - day
  if (diff === 0) return '今天'
  if (diff === 86400000) return '昨天'
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
}
function fmtPreviewDate(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000), now = new Date()
  now.setHours(0,0,0,0)
  const day = new Date(d); day.setHours(0,0,0,0)
  return now - day === 0
    ? d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}
const COLORS = ['#5B8FB9','#7C6E7F','#6B8F71','#A0785A','#7B6EA0','#5C8A8A','#A07860','#697A9A']
function avatarColor(src) { return COLORS[Math.abs(src.id) % COLORS.length] }
function srcInitial(src) {
  const first = [...(src.title || '')][0] ?? '?'
  // 如果首字符是字母则转大写，否则（emoji/汉字）原样返回
  return first.toUpperCase()
}
function fmtDuration(s) { return s ? `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}` : '' }
function fmtSize(b) { return b < 1048576 ? `${(b/1024).toFixed(0)} KB` : `${(b/1048576).toFixed(1)} MB` }
</script>

<template>
  <div class="tg-root">
    <div class="tg-app" :class="`view-${mobileView}`">

      <!-- ━━━ Sidebar ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
      <aside class="tg-sidebar">
        <!-- Search -->
        <div class="tg-sidebar-top">
          <div class="tg-search-row">
            <svg class="tg-search-icon" viewBox="0 0 24 24"><path d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/></svg>
            <input v-model="searchQuery" placeholder="搜索频道" class="tg-search-input" />
          </div>
        </div>

        <!-- Unlock strip -->
        <form v-if="!keyReady" @submit.prevent="unlock" class="tg-unlock-strip">
          <svg viewBox="0 0 24 24" class="tg-strip-icon"><path d="M18 8h-1V6A5 5 0 0 0 7 6v2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10a2 2 0 0 0-2-2z" fill="currentColor"/></svg>
          <input v-model="password" type="password" placeholder="密码解锁媒体" class="tg-strip-input" :class="{ 'strip-err': passwordError }" />
          <button type="submit" :disabled="unlocking" class="tg-strip-btn">{{ unlocking ? '…' : '解锁' }}</button>
        </form>
        <div v-else class="tg-unlocked-strip">
          <svg viewBox="0 0 24 24" class="tg-strip-icon tg-icon-ok"><path d="M20 7l-11 11-5-5 1.4-1.4L9 15.2 18.6 5.6z" fill="currentColor"/></svg>
          <span style="flex:1">媒体已解锁</span>
          <button class="tg-forget-btn" @click="forgetKey" title="清除已保存密码">忘记</button>
        </div>

        <!-- Source list -->
        <div class="tg-source-list">
          <div v-if="loading" class="tg-list-hint">加载中…</div>
          <div v-else-if="error" class="tg-list-hint tg-list-err">{{ error }}</div>
          <div v-else-if="filteredSources.length === 0" class="tg-list-hint">无匹配频道</div>
          <div v-else
            v-for="src in filteredSources" :key="src.id"
            class="tg-source-item" :class="{ 'is-active': activeSource?.id === src.id }"
            @click="selectSource(src)"
          >
            <div class="tg-avatar" :style="{ background: avatarColor(src) }">{{ srcInitial(src) }}</div>
            <div class="tg-src-body">
              <div class="tg-src-row">
                <span class="tg-src-name">{{ src.title }}</span>
                <span class="tg-src-time">{{ fmtPreviewDate(src.latestDate) }}</span>
              </div>
              <div class="tg-src-preview">{{ src.preview }}</div>
            </div>
          </div>
        </div>
      </aside>

      <!-- ━━━ Chat ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
      <div class="tg-chat">

        <div v-if="!activeSource" class="tg-chat-empty">
          <svg viewBox="0 0 24 24" class="tg-empty-icon"><path d="M21.198 2.433a2.242 2.242 0 0 0-1.022.215l-16.5 8.25a2.25 2.25 0 0 0 .126 4.073l4.003 1.498 1.498 4.003a2.25 2.25 0 0 0 4.073.126l8.25-16.5a2.242 2.242 0 0 0-.428-1.665z" fill="currentColor"/></svg>
          <p>选择频道查看消息</p>
        </div>

        <template v-else>
          <!-- Header -->
          <div class="tg-chat-header">
            <button class="tg-back-btn" @click="mobileView = 'list'">
              <svg viewBox="0 0 24 24"><path d="M19 12H5M12 5l-7 7 7 7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
            <div class="tg-chat-av" :style="{ background: avatarColor(activeSource) }">{{ srcInitial(activeSource) }}</div>
            <div class="tg-chat-meta">
              <div class="tg-chat-name">{{ activeSource.title }}</div>
              <div class="tg-chat-sub">
                <a v-if="activeSource.username" :href="`https://t.me/${activeSource.username}`" target="_blank" class="tg-chat-link">@{{ activeSource.username }}</a>
                <span v-else>{{ activeSource.msgs.length }} 条消息</span>
              </div>
            </div>
          </div>

          <!-- Messages -->
          <div class="tg-messages" ref="chatBodyEl">
            <template v-for="item in chatTimeline" :key="item.key">

              <!-- Date pill -->
              <div v-if="item.type === 'sep'" class="tg-date-pill">
                <span>{{ item.label }}</span>
              </div>

              <!-- Bubble -->
              <div v-else class="tg-bubble-wrap" @vue:mounted="loadGroup(item.group)">
                <div class="tg-bubble" :class="{ 'bubble-no-caption': hasMediaNoCaption(item.group) }">

                  <!-- Album -->
                  <template v-if="item.group.isAlbum">
                    <div class="tg-bub-album">
                      <div v-for="(row, ri) in computeAlbumRows(item.group)" :key="ri" class="tg-alb-row">

                        <!-- Single-image row -->
                        <template v-if="row.isSingle">
                          <div class="tg-alb-single"
                            :class="{ 'tg-click': isLoaded(row.items[0].msg.media_meta?.file_unique_id) }"
                            @click="openLightbox(row.items[0].msg.media_meta?.file_unique_id)">
                            <img v-if="isLoaded(row.items[0].msg.media_meta?.file_unique_id)"
                              :src="urlCache[row.items[0].msg.media_meta.file_unique_id]"
                              class="tg-nat-img" loading="lazy" />
                            <div v-else class="tg-ph" :class="slotPhClass(row.items[0].msg.media_meta?.file_unique_id)">
                              <div v-if="keyReady && urlCache[row.items[0].msg.media_meta?.file_unique_id] !== 'error'" class="tg-spin"/>
                              <svg v-else viewBox="0 0 24 24"><path d="M18 8h-1V6A5 5 0 0 0 7 6v2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10a2 2 0 0 0-2-2z" fill="currentColor"/></svg>
                            </div>
                            <template v-if="row.items[0].msg.type === 'video' && isLoaded(row.items[0].msg.media_meta?.file_unique_id)">
                              <div class="tg-vid-play-overlay"><div class="tg-vid-play-btn"><svg viewBox="0 0 24 24" style="fill:#fff;width:22px;height:22px;margin-left:2px"><path d="M8 5v14l11-7z"/></svg></div></div>
                              <div class="tg-vid-badges">
                                <span class="tg-vid-badge tg-vid-type">VIDEO</span>
                                <span v-if="row.items[0].msg.media_meta?.duration" class="tg-vid-badge">{{ fmtDuration(row.items[0].msg.media_meta.duration) }}</span>
                                <span v-if="row.items[0].msg.media_meta?.file_size" class="tg-vid-badge tg-vid-size">{{ fmtSize(row.items[0].msg.media_meta.file_size) }}</span>
                              </div>
                            </template>
                            <div v-if="row.items[0].extra > 0" class="tg-extra">+{{ row.items[0].extra }}</div>
                          </div>
                        </template>

                        <!-- Multi-image row -->
                        <template v-else>
                          <div v-for="slot in row.items" :key="slot.msg.message_id"
                            class="tg-alb-slot" :style="{ flex: getAR(slot.msg) }"
                            :class="{ 'tg-click': isLoaded(slot.msg.media_meta?.file_unique_id) }"
                            @click="openLightbox(slot.msg.media_meta?.file_unique_id)">
                            <div class="tg-alb-inner" :style="{ paddingBottom: (100/getAR(slot.msg)) + '%' }">
                              <img v-if="isLoaded(slot.msg.media_meta?.file_unique_id)"
                                :src="urlCache[slot.msg.media_meta.file_unique_id]"
                                class="tg-fill-img" loading="lazy" />
                              <div v-else class="tg-ph" :class="slotPhClass(slot.msg.media_meta?.file_unique_id)">
                                <div v-if="keyReady && urlCache[slot.msg.media_meta?.file_unique_id] !== 'error'" class="tg-spin"/>
                                <svg v-else viewBox="0 0 24 24"><path d="M18 8h-1V6A5 5 0 0 0 7 6v2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10a2 2 0 0 0-2-2z" fill="currentColor"/></svg>
                              </div>
                              <template v-if="slot.msg.type === 'video' && isLoaded(slot.msg.media_meta?.file_unique_id)">
                                <div class="tg-vid-play-overlay"><div class="tg-vid-play-btn tg-vid-play-sm"><svg viewBox="0 0 24 24" style="fill:#fff;width:16px;height:16px;margin-left:2px"><path d="M8 5v14l11-7z"/></svg></div></div>
                                <div class="tg-vid-badges">
                                  <span class="tg-vid-badge tg-vid-type">VIDEO</span>
                                  <span v-if="slot.msg.media_meta?.duration" class="tg-vid-badge">{{ fmtDuration(slot.msg.media_meta.duration) }}</span>
                                </div>
                              </template>
                              <div v-if="slot.extra > 0" class="tg-extra">+{{ slot.extra }}</div>
                            </div>
                          </div>
                        </template>

                      </div>
                    </div>
                  </template>

                  <!-- Single photo -->
                  <template v-else-if="item.group.items[0].type === 'photo' && item.group.items[0].media_file">
                    <div class="tg-bub-photo"
                      :class="{ 'tg-click': isLoaded(item.group.items[0].media_meta?.file_unique_id) }"
                      @click="openLightbox(item.group.items[0].media_meta?.file_unique_id)">
                      <img v-if="isLoaded(item.group.items[0].media_meta?.file_unique_id)"
                        :src="urlCache[item.group.items[0].media_meta.file_unique_id]"
                        class="tg-nat-img" loading="lazy" />
                      <div v-else class="tg-ph tg-ph-tall" :class="slotPhClass(item.group.items[0].media_meta?.file_unique_id)">
                        <div v-if="keyReady && urlCache[item.group.items[0].media_meta?.file_unique_id] !== 'error'" class="tg-spin"/>
                        <svg v-else viewBox="0 0 24 24"><path d="M18 8h-1V6A5 5 0 0 0 7 6v2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10a2 2 0 0 0-2-2z" fill="currentColor"/></svg>
                      </div>
                    </div>
                  </template>

                  <!-- Video -->
                  <template v-else-if="item.group.items[0].type === 'video'">
                    <div class="tg-bub-video">
                      <!-- thumbnail -->
                      <div class="tg-vid-cover">
                        <img v-if="item.group.items[0].media_file && isLoaded(item.group.items[0].media_meta?.file_unique_id)"
                          :src="urlCache[item.group.items[0].media_meta.file_unique_id]"
                          class="tg-nat-img" />
                        <div v-else class="tg-ph tg-ph-tall" :class="slotPhClass(item.group.items[0].media_meta?.file_unique_id)">
                          <div v-if="keyReady" class="tg-spin"/>
                          <svg v-else viewBox="0 0 24 24"><path d="M18 8h-1V6A5 5 0 0 0 7 6v2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10a2 2 0 0 0-2-2z" fill="currentColor"/></svg>
                        </div>
                        <!-- play button -->
                        <div class="tg-vid-play-overlay">
                          <div class="tg-vid-play-btn">
                            <svg viewBox="0 0 24 24" style="fill:#fff;width:22px;height:22px;margin-left:2px"><path d="M8 5v14l11-7z"/></svg>
                          </div>
                        </div>
                        <!-- badges -->
                        <div class="tg-vid-badges">
                          <span class="tg-vid-badge tg-vid-type">VIDEO</span>
                          <span v-if="item.group.items[0].media_meta?.duration" class="tg-vid-badge">
                            {{ fmtDuration(item.group.items[0].media_meta.duration) }}
                          </span>
                          <span v-if="item.group.items[0].media_meta?.file_size" class="tg-vid-badge tg-vid-size">
                            {{ fmtSize(item.group.items[0].media_meta.file_size) }}
                          </span>
                        </div>
                      </div>
                      <!-- filename below if present -->
                      <div v-if="item.group.items[0].media_meta?.file_name" class="tg-vid-filename">
                        {{ item.group.items[0].media_meta.file_name }}
                      </div>
                    </div>
                  </template>

                  <!-- Caption / Text -->
                  <div v-if="item.group.caption || (!item.group.isAlbum && item.group.items[0].text)"
                    class="tg-bub-text">{{ item.group.caption || item.group.items[0].text }}</div>

                  <!-- Time -->
                  <div class="tg-bub-time">{{ fmtTime(item.group.date) }}</div>
                </div>
              </div>

            </template>
          </div>

          <!-- Bottom bar -->
          <div class="tg-chat-bar">
            <form v-if="!keyReady" @submit.prevent="unlock" class="tg-bar-form">
              <svg viewBox="0 0 24 24" class="tg-bar-icon"><path d="M18 8h-1V6A5 5 0 0 0 7 6v2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10a2 2 0 0 0-2-2z" fill="currentColor"/></svg>
              <input v-model="password" type="password" placeholder="输入密码解锁媒体文件" class="tg-bar-input" :class="{ 'bar-err': passwordError }"/>
              <button type="submit" :disabled="unlocking" class="tg-bar-submit">{{ unlocking ? '解密中…' : '解锁媒体' }}</button>
            </form>
            <div v-else class="tg-bar-info">
              <svg viewBox="0 0 24 24" class="tg-bar-icon tg-icon-ok"><path d="M20 7l-11 11-5-5 1.4-1.4L9 15.2 18.6 5.6z" fill="currentColor"/></svg>
              媒体已解锁 · {{ activeSource.msgs.length }} 条消息归档
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>

  <!-- Lightbox -->
  <Teleport to="body">
    <div v-if="lightboxUrl" class="tg-lightbox" @click.self="closeLightbox">
      <button class="tg-lb-close" @click="closeLightbox">✕</button>
      <img :src="lightboxUrl" class="tg-lb-img" @click.stop />
    </div>
  </Teleport>
</template>

<!-- Global theme vars for chat background -->
<style>
:root            { --tg-chat-bg: #dce3e8; }
html.my-app-dark { --tg-chat-bg: #0d1117; }
</style>

<style scoped>
/* ─── Root / App shell ───────────────────────────────────────────────────── */
.tg-root {
  position: fixed;
  top: var(--app-nav-height, 53px);
  left: 0; right: 0; bottom: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 14px;
  box-sizing: border-box;
  background: var(--bg-color);
  z-index: 0;
}

.tg-app {
  flex: 1;
  display: flex;
  min-height: 0;
  max-width: 1300px;
  width: 100%;
  margin: 0 auto;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 4px 24px rgba(0,0,0,0.12);
}

/* ─── Sidebar ────────────────────────────────────────────────────────────── */
.tg-sidebar {
  width: 300px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--surface-color);
  border-right: 1px solid var(--border-color);
  overflow: hidden;
}

.tg-sidebar-top {
  padding: 10px 12px 8px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--border-color);
}

.tg-search-row {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-color);
  border: 1px solid var(--border-color);
  border-radius: 20px;
  padding: 7px 12px;
}
.tg-search-icon { width: 15px; height: 15px; color: var(--text-color); opacity: 0.35; flex-shrink: 0; }
.tg-search-input { flex: 1; border: none; background: transparent; color: var(--text-color); font-size: 14px; outline: none; }
.tg-search-input::placeholder { color: var(--text-color); opacity: 0.38; }

/* Unlock strip */
.tg-unlock-strip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  background: rgba(100,108,255,0.06);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}
.tg-strip-icon  { width: 13px; height: 13px; flex-shrink: 0; opacity: 0.55; color: var(--text-color); }
.tg-icon-ok     { color: #4caf50; opacity: 1; }
.tg-strip-input { flex: 1; min-width: 0; border: none; background: transparent; color: var(--text-color); font-size: 12px; outline: none; }
.tg-strip-input::placeholder { color: var(--text-color); opacity: 0.38; }
.tg-strip-input.strip-err { color: #e28a8a; }
.tg-strip-btn   { font-size: 11px; padding: 3px 8px; border-radius: 10px; border: 1px solid var(--primary-color); background: transparent; color: var(--primary-color); cursor: pointer; white-space: nowrap; flex-shrink: 0; }
.tg-unlocked-strip { display: flex; align-items: center; gap: 6px; padding: 7px 12px; font-size: 11px; color: #4caf50; border-bottom: 1px solid var(--border-color); flex-shrink: 0; }
.tg-forget-btn { font-size: 11px; padding: 1px 6px; border-radius: 8px; border: 1px solid currentColor; background: transparent; color: var(--text-color); opacity: 0.35; cursor: pointer; flex-shrink: 0; }
.tg-forget-btn:hover { opacity: 0.7; }

/* Source list */
.tg-source-list { flex: 1; overflow-y: auto; overscroll-behavior: contain; }
.tg-list-hint   { padding: 24px; text-align: center; font-size: 13px; color: var(--text-color); opacity: 0.38; }
.tg-list-err    { color: #e28a8a; opacity: 1; }

.tg-source-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px;
  cursor: pointer;
  transition: background 0.1s;
  border-bottom: 1px solid var(--border-color);
}
.tg-source-item:hover  { background: var(--hover-bg); }
.tg-source-item.is-active { background: var(--primary-color); }
.tg-source-item.is-active .tg-src-name,
.tg-source-item.is-active .tg-src-time,
.tg-source-item.is-active .tg-src-preview { color: #fff !important; opacity: 1 !important; }

.tg-avatar {
  width: 46px; height: 46px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 19px; font-weight: 700; color: #fff; flex-shrink: 0;
  user-select: none;
}
.tg-src-body  { flex: 1; min-width: 0; }
.tg-src-row   { display: flex; align-items: baseline; justify-content: space-between; gap: 6px; margin-bottom: 2px; }
.tg-src-name  { font-size: 14px; font-weight: 600; color: var(--text-color); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; min-width: 0; }
.tg-src-time  { font-size: 11px; color: var(--text-color); opacity: 0.42; flex-shrink: 0; }
.tg-src-preview { font-size: 12px; color: var(--text-color); opacity: 0.48; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* ─── Chat area ──────────────────────────────────────────────────────────── */
.tg-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--tg-chat-bg);
  position: relative;
}

.tg-chat-empty {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 14px;
  color: var(--text-color); opacity: 0.25;
}
.tg-empty-icon { width: 52px; height: 52px; }
.tg-chat-empty p { font-size: 14px; margin: 0; }

/* Chat header */
.tg-chat-header {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px;
  background: var(--surface-color);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}
.tg-back-btn {
  display: none;
  width: 36px; height: 36px; padding: 0;
  border: none; background: transparent; cursor: pointer;
  color: var(--text-color); border-radius: 50%; flex-shrink: 0;
}
.tg-back-btn svg { width: 20px; height: 20px; display: block; }
.tg-chat-av {
  width: 38px; height: 38px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; font-weight: 700; color: #fff; flex-shrink: 0;
  user-select: none;
}
.tg-chat-meta { flex: 1; min-width: 0; }
.tg-chat-name { font-size: 15px; font-weight: 700; color: var(--text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tg-chat-sub  { font-size: 12px; color: var(--text-color); opacity: 0.48; }
.tg-chat-link { color: var(--primary-color); text-decoration: none; opacity: 0.82; }
.tg-chat-link:hover { opacity: 1; }

/* Messages scroll area */
.tg-messages {
  flex: 1; overflow-y: auto; overscroll-behavior: contain;
  padding: 14px 12px;
  display: flex; flex-direction: column; gap: 3px;
  background: var(--tg-chat-bg);
}

/* Date pill */
.tg-date-pill { display: flex; justify-content: center; margin: 10px 0 6px; }
.tg-date-pill span {
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  color: var(--text-color); opacity: 0.7;
  font-size: 11px; padding: 3px 13px; border-radius: 12px;
}

/* Bubble */
.tg-bubble-wrap { display: flex; justify-content: flex-start; margin-bottom: 2px; }

.tg-bubble {
  max-width: 72%;
  min-width: 100px;
  background: var(--surface-color);
  border-radius: 4px 12px 12px 12px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.1);
  overflow: hidden;
  position: relative;
}

.tg-bub-text {
  padding: 8px 10px 2px;
  font-size: 14px;
  line-height: 1.55;
  color: var(--text-color);
  white-space: pre-wrap;
  word-break: break-word;
}

.tg-bub-time {
  font-size: 11px;
  color: var(--text-color);
  opacity: 0.42;
  text-align: right;
  padding: 3px 8px 6px;
}

/* When media only (no caption), time overlays on image */
.bubble-no-caption .tg-bub-time {
  position: absolute; bottom: 0; right: 0;
  background: rgba(0,0,0,0.42);
  color: #fff; opacity: 1;
  border-radius: 8px 0 0 0;
  padding: 2px 6px 3px;
  font-size: 10px;
}

/* Album in bubble */
.tg-bub-album { overflow: hidden; }
.tg-alb-row   { display: flex; gap: 2px; }
.tg-alb-row + .tg-alb-row { margin-top: 2px; }

.tg-alb-single {
  width: 100%; line-height: 0;
  position: relative; overflow: hidden;
  display: flex; justify-content: center;
  background: var(--bg-color);
}
.tg-alb-slot { min-width: 0; overflow: hidden; background: var(--bg-color); }
.tg-alb-inner { position: relative; width: 100%; }
.tg-alb-inner > .tg-fill-img,
.tg-alb-inner > .tg-ph,
.tg-alb-inner > .tg-extra { position: absolute; inset: 0; width: 100%; height: 100%; }

/* Photos */
.tg-nat-img   { display: block; max-width: 100%; max-height: 480px; width: auto; height: auto; }
.tg-fill-img  { width: 100%; height: 100%; object-fit: cover; display: block; }
.tg-bub-photo { line-height: 0; position: relative; width: 100%; }

/* Placeholder */
.tg-ph {
  min-height: 80px; display: flex; align-items: center; justify-content: center;
  background: var(--bg-color);
}
.tg-ph-tall { min-height: 160px; }
.tg-ph svg  { width: 24px; height: 24px; opacity: 0.3; }
.ph-locked svg { color: var(--text-color); }
.ph-error svg  { color: #e28a8a; }

/* Spinner */
.tg-spin {
  width: 20px; height: 20px;
  border: 2px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Extra overlay */
.tg-extra {
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; font-weight: 800; color: #fff;
  background: rgba(0,0,0,0.42);
}

/* Video */
.tg-bub-video { overflow: hidden; }

.tg-vid-cover {
  position: relative;
  width: 100%;
  line-height: 0;
  background: #000;
}

.tg-vid-play-overlay {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.25);
}
.tg-vid-play-btn {
  width: 48px; height: 48px; border-radius: 50%;
  background: rgba(0,0,0,0.55);
  display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(2px);
}
.tg-vid-play-sm {
  width: 32px; height: 32px;
}

/* bottom-left badge row */
.tg-vid-badges {
  position: absolute; bottom: 7px; left: 8px;
  display: flex; align-items: center; gap: 5px;
}
.tg-vid-badge {
  background: rgba(0,0,0,0.52);
  color: #fff;
  font-size: 10px; font-weight: 600; letter-spacing: 0.02em;
  padding: 2px 6px; border-radius: 4px;
  backdrop-filter: blur(4px);
  line-height: 1.4;
}
.tg-vid-type { text-transform: uppercase; opacity: 0.85; }
.tg-vid-size { opacity: 0.75; }

.tg-vid-filename {
  padding: 6px 10px 4px;
  font-size: 12px; color: var(--text-color); opacity: 0.5;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  line-height: 1.4;
}

/* Click cursor */
.tg-click { cursor: zoom-in; }

/* Chat bottom bar */
.tg-chat-bar {
  flex-shrink: 0;
  padding: 10px 14px;
  background: var(--surface-color);
  border-top: 1px solid var(--border-color);
}
.tg-bar-form {
  display: flex; align-items: center; gap: 8px;
  background: var(--bg-color);
  border: 1px solid var(--border-color);
  border-radius: 22px;
  padding: 8px 14px;
}
.tg-bar-icon  { width: 16px; height: 16px; flex-shrink: 0; opacity: 0.5; color: var(--text-color); }
.tg-bar-input { flex: 1; border: none; background: transparent; color: var(--text-color); font-size: 14px; outline: none; }
.tg-bar-input::placeholder { color: var(--text-color); opacity: 0.38; }
.tg-bar-input.bar-err { color: #e28a8a; }
.tg-bar-submit {
  padding: 5px 14px; border-radius: 14px; border: none;
  background: var(--primary-color); color: #fff;
  font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap; flex-shrink: 0;
}
.tg-bar-submit:disabled { opacity: 0.5; cursor: not-allowed; }
.tg-bar-info {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: #4caf50;
  justify-content: center;
}

/* ─── Lightbox ───────────────────────────────────────────────────────────── */
.tg-lightbox {
  position: fixed; inset: 0; z-index: 9999;
  background: rgba(0,0,0,0.9);
  display: flex; align-items: center; justify-content: center;
  cursor: zoom-out; animation: lb-in 0.18s ease;
}
@keyframes lb-in { from { opacity: 0 } to { opacity: 1 } }
.tg-lb-img    { max-width: calc(100vw - 48px); max-height: calc(100vh - 48px); object-fit: contain; border-radius: 4px; cursor: default; box-shadow: 0 8px 40px rgba(0,0,0,0.6); }
.tg-lb-close {
  position: fixed; top: 16px; right: 16px;
  width: 36px; height: 36px; padding: 0; margin: 0;
  border-radius: 50%; border: none;
  background: rgba(255,255,255,0.18);
  color: #fff;
  font-size: 18px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; z-index: 10000;
  transition: background 0.15s;
  box-sizing: border-box;
}
.tg-lb-close:hover { background: rgba(255,255,255,0.32); }

/* ─── Mobile ─────────────────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .tg-app { position: relative; overflow: hidden; }

  .tg-sidebar {
    position: absolute; inset: 0;
    width: 100%; z-index: 1;
    transition: transform 0.28s ease;
  }
  .tg-chat {
    position: absolute; inset: 0;
    transition: transform 0.28s ease;
  }

  .view-list .tg-sidebar { transform: translateX(0); }
  .view-list .tg-chat    { transform: translateX(100%); }
  .view-chat .tg-sidebar { transform: translateX(-100%); }
  .view-chat .tg-chat    { transform: translateX(0); }

  .tg-back-btn { display: flex; align-items: center; justify-content: center; }
  .tg-bubble   { max-width: 90%; }
}
</style>
