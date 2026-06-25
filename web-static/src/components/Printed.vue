<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import * as OpenCC from 'opencc-js'
import { useViewMode } from '@/composables/useViewMode'
import GalleryList from '@/components/GalleryList.vue'
import { exTypeClassMap } from '@/utils/galleryUtils'
import { loadGalleries, loadTranslations } from '@/composables/useGalleryData'

const { viewMode } = useViewMode()

const typeClassMap = exTypeClassMap

function getGallery(sid) {
  if (sid == null || sid === '') return null
  return galleryMap.value[String(sid)] ?? null
}

const SKIP_NAMESPACES = new Set(['language', 'other'])

function getTagValues(tags) {
  if (!Array.isArray(tags)) return []
  return tags
    .filter(t => {
      if (!t.includes(':')) return true
      const ns = t.split(':', 2)[0]
      return !SKIP_NAMESPACES.has(ns)
    })
    .slice(0, 6)
    .map(t => {
      if (!t.includes(':') || !translationData.value) return t
      const [ns, val] = t.split(':', 2)
      const cn = translationData.value.data
        ?.find(item => item.namespace === ns)?.data?.[val]?.name
      return cn || val
    })
}

const router = useRouter()
const route = useRoute()

// 将输入转为繁体，与原始输入一起作为查询词（字段不转换）
const toTraditional = OpenCC.Converter({ from: 'cn', to: 'tw' })

const items = ref([])
const galleryMap = ref({})
const translationData = ref(null)
const loading = ref(true)
const error = ref('')

function parseCSV(text) {
  const rows = []
  let row = [], value = '', inQuotes = false, i = 0
  while (i < text.length) {
    const ch = text[i]
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') { value += '"'; i += 2; continue }
        inQuotes = false; i++; continue
      }
      value += ch; i++; continue
    }
    if (ch === '"') { inQuotes = true; i++; continue }
    if (ch === ',') { row.push(value); value = ''; i++; continue }
    if (ch === '\n' || ch === '\r') {
      if (value !== '' || row.length) { row.push(value); rows.push(row); row = []; value = '' }
      if (ch === '\r' && text[i + 1] === '\n') i++
      i++; continue
    }
    value += ch; i++
  }
  if (value !== '' || row.length) { row.push(value); rows.push(row) }
  if (rows.length < 2) return []
  const headers = rows[0]
  return rows.slice(1).map(r => Object.fromEntries(headers.map((h, j) => [h, r[j] ?? ''])))
}

onMounted(async () => {
  try {
    const [digeRes, galleries, translations] = await Promise.all([
      fetch('/data/future_digi.csv'),
      loadGalleries(),
      loadTranslations(),
    ])
    if (!digeRes.ok) throw new Error('future_digi.csv not found')
    const csvText = await digeRes.text()

    items.value = parseCSV(csvText)
    galleryMap.value = Object.fromEntries(galleries.map(g => [String(g.gid), g]))
    translationData.value = translations
    const pageFromUrl = parseInt(route.query.page) || 1
    if (pageFromUrl > 1) {
      currentPage.value = pageFromUrl
      pageJumpValue.value = String(pageFromUrl)
    }
  } catch (e) {
    error.value = '数据加载失败：' + e.message
  } finally {
    loading.value = false
  }
})

function getThumb(item) {
  if (item?.cover) return `/printed-cover/${encodeURIComponent(item.cover)}`
  const sid = item?.sid
  if (!sid && sid !== 0) return null
  return galleryMap.value[String(sid)]?.thumb ?? null
}

const matchedCount = computed(
  () => items.value.filter((item) => getThumb(item)).length
)

const searchQuery = ref('')
const toast = ref('')
let toastTimer = null

const activeSearchToken = computed(() => {
  const query = searchQuery.value
  let inQuote = false, lastBreak = -1
  for (let i = 0; i < query.length; i++) {
    const ch = query[i]
    if (ch === '"') inQuote = !inQuote
    if (!inQuote && (ch === ' ' || ch === ',')) lastBreak = i
  }
  return query.slice(lastBreak + 1).trim()
})

const tagSuggestions = computed(() => {
  const token = activeSearchToken.value.trim().toLowerCase()
  const translations = translationData.value?.data
  if (!token || !translations || token.length < 2) return []
  if (token.includes('$') || token.startsWith('-') || token.startsWith('~')) return []
  const normalized = token.includes(':') ? token.split(':', 2)[1].replace(/^"|"$/g, '') : token.replace(/^"|"$/g, '')
  if (!normalized) return []
  const suggestions = []
  for (const namespaceEntry of translations) {
    const namespace = namespaceEntry.namespace
    const values = namespaceEntry.data || {}
    for (const [value, detail] of Object.entries(values)) {
      const valueLower = value.toLowerCase()
      const cnLower = (detail?.name || '').toLowerCase()
      const nsLower = namespace.toLowerCase()
      const score =
        valueLower === normalized ? 0 :
        valueLower.startsWith(normalized) ? 1 :
        cnLower.startsWith(normalized) ? 2 :
        nsLower.startsWith(normalized) ? 3 :
        valueLower.includes(normalized) ? 4 :
        cnLower.includes(normalized) ? 5 : -1
      if (score === -1) continue
      suggestions.push({ tag: `${namespace}:${value}`, namespace, value, tag_cn: detail?.name || '', score })
    }
  }
  return suggestions
    .sort((a, b) => a.score - b.score || a.namespace.localeCompare(b.namespace) || a.value.localeCompare(b.value))
    .slice(0, 8)
})

function applyTagSuggestion(item) {
  const query = searchQuery.value
  let inQuote = false, lastBreak = -1
  for (let i = 0; i < query.length; i++) {
    const ch = query[i]
    if (ch === '"') inQuote = !inQuote
    if (!inQuote && (ch === ' ' || ch === ',')) lastBreak = i
  }
  const prefix = query.slice(0, lastBreak + 1).trimEnd()
  const replacement = `${item.namespace}:"${item.value}$"`
  searchQuery.value = prefix ? `${prefix} ${replacement} ` : `${replacement} `
}

function clearSearch() { searchQuery.value = '' }

function showToast(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 2500)
}

const normalizedItems = computed(() => pagedItems.value.map((item, index) => {
  const gallery = getGallery(item.sid)
  return {
    key: `${item.ID}-${index}`,
    gid: gallery ? String(item.sid) : null,
    thumb: getThumb(item),
    title: item['书名'] || item['日文名'],
    badge: gallery?.category ?? null,
    badgeClass: gallery ? (typeClassMap[gallery.category] || 'default') : null,
    tags: gallery ? getTagValues(gallery.tags) : [],
    pages: gallery?.filecount ? `${gallery.filecount}p` : null,
    date: null,
    rating: gallery?.rating ?? null,
    fav: null,
    refId: `#${item.ID}`,
    noMeta: !gallery,
    noMetaText: '— 暂无匹配元数据 —',
  }
}))

function handleGalleryClick(item) {
  if (item.gid) {
    router.push(`/gallery/${item.gid}/`)
  } else {
    showToast('未匹配元数据')
  }
}

// ── Advanced search (同 Home.vue，扩展 Printed 专有字段) ──────────────────────

const namespaceAliases = {
  f: 'female', m: 'male', a: 'artist', p: 'parody',
  c: 'character', l: 'language', g: 'group', o: 'other',
  cos: 'cosplayer', x: 'mixed', r: 'reclass',
}

function tokenizeQuery(query) {
  const tokens = []
  let buffer = '', inQuote = false, wasQuoted = false
  for (const ch of query) {
    if (ch === '"') { inQuote = !inQuote; wasQuoted = true; continue }
    if (!inQuote && (ch === ' ' || ch === ',')) {
      if (buffer) { tokens.push({ text: buffer, quoted: wasQuoted }); buffer = ''; wasQuoted = false }
      continue
    }
    buffer += ch
  }
  if (buffer) tokens.push({ text: buffer, quoted: wasQuoted })
  return tokens
}

function parseQuery(query) {
  const include = [], exclude = [], orTerms = []
  for (const token of tokenizeQuery(query)) {
    let raw = token.text.trim()
    if (!raw) continue
    let mode = 'include'
    if (raw.startsWith('-')) { mode = 'exclude'; raw = raw.slice(1) }
    else if (raw.startsWith('~')) { mode = 'or'; raw = raw.slice(1) }
    raw = raw.replace(/_/g, ' ').trim()
    if (!raw) continue
    let exactTag = false
    if (raw.endsWith('$')) { exactTag = true; raw = raw.slice(0, -1) }
    let wildcard = false
    if (raw.endsWith('*') || raw.endsWith('%')) { wildcard = true; raw = raw.slice(0, -1) }
    let field = 'any', namespace = null, value = raw
    if (raw.includes(':')) {
      const [prefixRaw, rest] = raw.split(':', 2)
      const prefix = prefixRaw.toLowerCase()
      const printedFields = ['id', 'name', 'jpname', 'sid']
      const galleryFields = ['title', 'uploader', 'category', 'gid', 'tag']
      if (printedFields.includes(prefix) || galleryFields.includes(prefix)) {
        field = prefix; value = rest || ''
      } else {
        field = 'tag'; namespace = namespaceAliases[prefix] || prefix; value = rest || ''
      }
    }
    value = value.trim().toLowerCase()
    if (!value) continue
    const term = { field, value, wildcard, exactTag, namespace, quoted: token.quoted }
    if (mode === 'exclude') exclude.push(term)
    else if (mode === 'or') orTerms.push(term)
    else include.push(term)
  }
  return { include, exclude, orTerms }
}

function matchText(text, term) {
  if (!text) return false
  const target = String(text).toLowerCase()
  const check = (val) => {
    if (!val) return false
    if (term.wildcard) return target.startsWith(val)
    return target.includes(val)
  }
  if (check(term.value)) return true
  const trad = toTraditional(term.value)
  return trad !== term.value && check(trad)
}

function matchTagList(tags, term) {
  if (!Array.isArray(tags)) return false
  for (const tag of tags) {
    if (typeof tag !== 'string') continue
    const tagLower = tag.toLowerCase()
    if (term.namespace) {
      if (!tagLower.startsWith(`${term.namespace}:`)) continue
      const tagValue = tagLower.slice(term.namespace.length + 1)
      if (term.exactTag) { if (tagValue === term.value) return true }
      else if (term.wildcard) { if (tagValue.startsWith(term.value)) return true }
      else if (tagValue.includes(term.value)) return true
    } else {
      const tagValue = tagLower.includes(':') ? tagLower.split(':', 2)[1] : tagLower
      if (term.exactTag) { if (tagValue === term.value) return true }
      else if (term.wildcard) { if (tagValue.startsWith(term.value)) return true }
      else if (tagLower.includes(term.value)) return true
    }
  }
  return false
}

function matchTerm(item, term) {
  const gallery = galleryMap.value[String(item.sid)]
  if (term.field === 'id')      return String(item.ID || '').toLowerCase().includes(term.value)
  if (term.field === 'name')    return matchText(item['书名'], term)
  if (term.field === 'jpname')  return matchText(item['日文名'], term)
  if (term.field === 'sid')     return String(item.sid || '') === term.value
  if (term.field === 'gid')     return String(gallery?.gid || '') === term.value
  if (term.field === 'title')   return matchText(gallery?.title, term) || matchText(gallery?.title_jpn, term)
  if (term.field === 'uploader') return matchText(gallery?.uploader, term)
  if (term.field === 'category') return matchText(gallery?.category, term)
  if (term.field === 'tag')     return matchTagList(gallery?.tags, term)
  // any: 搜所有字段
  return matchText(item.ID, term) ||
    matchText(item['书名'], term) ||
    matchText(item['日文名'], term) ||
    matchText(gallery?.title, term) ||
    matchText(gallery?.title_jpn, term) ||
    matchText(gallery?.uploader, term) ||
    matchText(gallery?.category, term) ||
    matchTagList(gallery?.tags, term)
}

const filteredItems = computed(() => {
  const raw = searchQuery.value.trim()
  if (!raw) return items.value
  const parsed = parseQuery(raw)
  return items.value.filter(item => {
    if (!parsed.include.every(term => matchTerm(item, term))) return false
    if (parsed.exclude.some(term => matchTerm(item, term))) return false
    if (parsed.orTerms.length > 0 && !parsed.orTerms.some(term => matchTerm(item, term))) return false
    return true
  })
})

const currentPage = ref(1)
const perPage = ref(30)
const pageJumpValue = ref('1')

const totalPages = computed(() => Math.max(1, Math.ceil(filteredItems.value.length / perPage.value)))

const pagedItems = computed(() => {
  const start = (currentPage.value - 1) * perPage.value
  return filteredItems.value.slice(start, start + perPage.value)
})

watch(filteredItems, () => {
  currentPage.value = 1
  pageJumpValue.value = '1'
})

watch(viewMode, () => {
  currentPage.value = 1
  pageJumpValue.value = '1'
})

watch(currentPage, (v) => {
  pageJumpValue.value = String(v)
  router.replace({ query: v > 1 ? { page: String(v) } : {} })
})

function goToPage(page) {
  currentPage.value = Math.max(1, Math.min(totalPages.value, page))
}

function submitPageJump() {
  const n = parseInt(pageJumpValue.value)
  if (!isNaN(n)) goToPage(n)
}
</script>

<template>
  <div class="digi-container">
    <div class="digi-header">
      <h2 class="digi-title">Printed</h2>
      <div class="digi-stats" v-if="!loading && !error">
        <span>共 {{ items.length }} 部</span>
        <span class="digi-dot">·</span>
        <span>已关联封面 {{ matchedCount }} 部</span>
        <template v-if="searchQuery.trim()">
          <span class="digi-dot">·</span>
          <span>结果 {{ filteredItems.length }} 部</span>
        </template>
      </div>
    </div>

    <div class="digi-search-row" v-if="!loading && !error">
      <div class="digi-search-wrap">
        <svg class="digi-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <circle cx="11" cy="11" r="7.5"/><line x1="20" y1="20" x2="15.5" y2="15.5"/>
        </svg>
        <input
          v-model="searchQuery"
          class="digi-search-input"
          placeholder="搜索 ID / 书名 / 日文名 / sid / tag（如 artist:xxx）"
        />
        <div v-if="tagSuggestions.length" class="digi-tag-suggest">
          <button
            v-for="item in tagSuggestions"
            :key="item.tag"
            type="button"
            class="digi-tag-suggest-item"
            @click="applyTagSuggestion(item)"
          >
            <span class="digi-tag-suggest-main">{{ item.namespace }}:"{{ item.value }}$"</span>
            <span class="digi-tag-suggest-sub">{{ item.tag_cn || item.value }}</span>
          </button>
        </div>
      </div>
      <button class="digi-clear-btn" @click="clearSearch">Clear</button>
    </div>

    <div v-if="loading" class="digi-empty">Loading…</div>
    <div v-else-if="error" class="digi-empty digi-error">{{ error }}</div>
    <div v-else-if="!filteredItems.length" class="digi-empty">No results</div>

    <template v-else>
      <!-- Top paginator -->
      <div v-if="totalPages > 1" class="digi-pagination">
        <div class="paginator-mini">
          <button class="pag-btn pag-nav" :disabled="currentPage <= 1" @click="goToPage(1)">«</button>
          <button class="pag-btn pag-nav" :disabled="currentPage <= 1" @click="goToPage(currentPage - 1)">‹</button>
          <label class="pag-jump-inline">
            <input v-model="pageJumpValue" class="pag-jump-input" inputmode="numeric" autocomplete="off" spellcheck="false" @keydown.enter.prevent="submitPageJump" />
            <span class="pag-jump-total">/ {{ totalPages }}</span>
          </label>
          <button class="pag-btn pag-nav" :disabled="currentPage >= totalPages" @click="goToPage(currentPage + 1)">›</button>
          <button class="pag-btn pag-nav" :disabled="currentPage >= totalPages" @click="goToPage(totalPages)">»</button>
        </div>
      </div>

      <GalleryList :items="normalizedItems" @click="handleGalleryClick" />

      <!-- Bottom paginator -->
      <div v-if="totalPages > 1" class="digi-pagination">
        <div class="paginator-mini">
          <button class="pag-btn pag-nav" :disabled="currentPage <= 1" @click="goToPage(1)">«</button>
          <button class="pag-btn pag-nav" :disabled="currentPage <= 1" @click="goToPage(currentPage - 1)">‹</button>
          <label class="pag-jump-inline">
            <input v-model="pageJumpValue" class="pag-jump-input" inputmode="numeric" autocomplete="off" spellcheck="false" @keydown.enter.prevent="submitPageJump" />
            <span class="pag-jump-total">/ {{ totalPages }}</span>
          </label>
          <button class="pag-btn pag-nav" :disabled="currentPage >= totalPages" @click="goToPage(currentPage + 1)">›</button>
          <button class="pag-btn pag-nav" :disabled="currentPage >= totalPages" @click="goToPage(totalPages)">»</button>
        </div>
      </div>
    </template>

    <Transition name="digi-toast">
      <div v-if="toast" class="digi-toast">{{ toast }}</div>
    </Transition>
  </div>
</template>

<style scoped src="@/assets/Printed.css"></style>
