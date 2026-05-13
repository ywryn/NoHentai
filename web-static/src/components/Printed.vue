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

function showToast(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 2500)
}

const normalizedItems = computed(() => pagedItems.value.map(item => {
  const gallery = getGallery(item.sid)
  return {
    key: item.ID,
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

// namespace 别名表（与 Home.vue 保持一致）
const namespaceAliases = {
  f: 'female', m: 'male', a: 'artist', p: 'parody',
  c: 'character', l: 'language', g: 'group', o: 'other',
  cos: 'cosplayer', x: 'mixed', r: 'reclass',
}

/**
 * 对单条 gallery tags 数组做单个 query 词匹配。
 * 支持：namespace:value（含别名）、tag$（精确）、纯文本（模糊）
 */
function matchTagsByQuery(tags, query) {
  if (!Array.isArray(tags) || !tags.length) return false

  if (query.includes(':')) {
    const colonIdx = query.indexOf(':')
    const nsRaw = query.slice(0, colonIdx)
    const ns = namespaceAliases[nsRaw] || nsRaw
    let val = query.slice(colonIdx + 1)
    if (!val) return false
    const exact = val.endsWith('$')
    if (exact) val = val.slice(0, -1)

    return tags.some((tag) => {
      if (!tag.includes(':')) return false
      const [tagNs, tagVal] = tag.toLowerCase().split(':', 2)
      if (tagNs !== ns) return false
      return exact ? tagVal === val : tagVal.includes(val)
    })
  }

  // 纯文本：匹配任意 tag 的值部分（忽略 namespace 前缀）
  const exact = query.endsWith('$')
  const val = exact ? query.slice(0, -1) : query
  return tags.some((tag) => {
    const lower = tag.toLowerCase()
    const tagVal = lower.includes(':') ? lower.split(':', 2)[1] : lower
    return exact ? tagVal === val : tagVal.includes(val)
  })
}

const filteredItems = computed(() => {
  const raw = searchQuery.value.trim().toLowerCase()
  if (!raw) return items.value
  // 保留原始输入，同时生成繁体版本，两者都用于匹配
  const queries = [...new Set([raw, toTraditional(raw).toLowerCase()])]

  return items.value.filter((item) => {
    // 1. 原有字段匹配（ID / 书名 / 日文名 / sid）
    const fieldMatch = [item.ID, item['书名'], item['日文名'], item.sid].some((v) => {
      if (v == null) return false
      const field = String(v).toLowerCase()
      return queries.some((q) => field.includes(q))
    })
    if (fieldMatch) return true

    // 2. 关联 gallery 的 tags 匹配
    const tags = galleryMap.value[String(item.sid)]?.tags
    return queries.some((q) => matchTagsByQuery(tags, q))
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

    <div class="digi-search" v-if="!loading && !error">
      <input
        v-model="searchQuery"
        class="digi-search-input"
        placeholder="搜索 ID / 书名 / 日文名 / sid / tag（如 artist:xxx）"
        type="search"
      />
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
