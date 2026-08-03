<script setup>
import { ref, computed, onMounted, watch, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import * as OpenCC from 'opencc-js'
import { useViewMode } from '@/composables/useViewMode'
import GalleryList from '@/components/GalleryList.vue'
import Paginator from '@/components/Paginator.vue'
import { exTypeClassMap } from '@/utils/galleryUtils'
import { loadGalleries, loadTranslations } from '@/composables/useGalleryData'
import {
  parseQuery,
  passesQuery,
  matchText,
  matchTagList,
  matchGalleryTerm,
  activeToken,
  applySuggestion,
  suggestTags,
} from '@/utils/gallerySearch'

const PER_PAGE = 30
/** Printed 专有字段，叠加在通用画廊字段之上 */
const PRINTED_FIELDS = ['id', 'name', 'jpname', 'sid']
const SKIP_NAMESPACES = new Set(['language', 'other'])

const router = useRouter()
const route = useRoute()
const { viewMode } = useViewMode()

/* 输入转繁体后与原文一起匹配（字段本身不转换） */
const toTraditional = OpenCC.Converter({ from: 'cn', to: 'tw' })

const items = ref([])
const galleryMap = ref({})
const translationData = ref(null)
const loading = ref(true)
const error = ref('')
const searchQuery = ref('')
const currentPage = ref(1)
const perPage = ref(PER_PAGE)
const toast = ref('')
const highlightIndex = ref(-1)
const suggestDismissed = ref(false)
const searchInputRef = ref()

let toastTimer = null
let blurTimer = null

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

function getGallery(sid) {
  if (sid == null || sid === '') return null
  return galleryMap.value[String(sid)] ?? null
}

function getTagValues(tags) {
  if (!Array.isArray(tags)) return []
  return tags
    .filter(t => {
      if (!t.includes(':')) return true
      return !SKIP_NAMESPACES.has(t.split(':', 2)[0])
    })
    .slice(0, 6)
    .map(t => {
      if (!t.includes(':') || !translationData.value) return t
      const [ns, val] = t.split(':', 2)
      return translationData.value.data?.find(x => x.namespace === ns)?.data?.[val]?.name || val
    })
}

function getThumb(item) {
  if (item?.cover) return `/printed-cover/${encodeURIComponent(item.cover)}`
  const sid = item?.sid
  if (!sid && sid !== 0) return null
  return galleryMap.value[String(sid)]?.thumb ?? null
}

/* ── 搜索（与首页共用同一套解析/匹配实现） ─────────────────────── */

function matchTerm(item, term) {
  const gallery = galleryMap.value[String(item.sid)]
  const expand = toTraditional
  switch (term.field) {
    case 'id': return String(item.ID || '').toLowerCase().includes(term.value)
    case 'name': return matchText(item['书名'], term, expand)
    case 'jpname': return matchText(item['日文名'], term, expand)
    case 'sid': return String(item.sid || '') === term.value
    case 'gid':
    case 'title':
    case 'uploader':
    case 'category':
    case 'tag':
      return matchGalleryTerm(gallery, term, expand)
    default:
      return (
        matchText(item.ID, term, expand) ||
        matchText(item['书名'], term, expand) ||
        matchText(item['日文名'], term, expand) ||
        matchText(gallery?.title, term, expand) ||
        matchText(gallery?.title_jpn, term, expand) ||
        matchText(gallery?.uploader, term, expand) ||
        matchText(gallery?.category, term, expand) ||
        matchTagList(gallery?.tags, term)
      )
  }
}

const filteredItems = computed(() => {
  const raw = searchQuery.value.trim()
  if (!raw) return items.value
  const parsed = parseQuery(raw, PRINTED_FIELDS)
  return items.value.filter(item => passesQuery(item, parsed, matchTerm))
})

const matchedCount = computed(() => items.value.filter(item => getThumb(item)).length)

const totalPages = computed(() => Math.max(1, Math.ceil(filteredItems.value.length / perPage.value)))

const pagedItems = computed(() => {
  const start = (currentPage.value - 1) * perPage.value
  return filteredItems.value.slice(start, start + perPage.value)
})

const normalizedItems = computed(() =>
  pagedItems.value.map((item, index) => {
    const gallery = getGallery(item.sid)
    const bookName = item['日文名'] || item['书名'] || ''
    return {
      key: `${item.ID}-${index}`,
      gid: gallery ? String(item.sid) : null,
      to: gallery ? `/gallery/${item.sid}/` : null,
      thumb: getThumb(item),
      title: item['书名'] || item['日文名'],
      badge: gallery?.category ?? null,
      badgeClass: gallery ? (exTypeClassMap[gallery.category] || 'default') : null,
      tags: gallery ? getTagValues(gallery.tags) : [],
      pages: gallery?.filecount ? `${gallery.filecount}p` : null,
      date: null,
      rating: gallery?.rating ?? null,
      fav: null,
      refId: `#${item.ID}`,
      noMeta: !gallery,
      noMetaText: '暂无匹配元数据 · 点击去 E-Hentai 搜索',
      /* 未关联画廊时给一条出路，而不是弹个提示了事 */
      searchUrl: gallery ? null : `https://e-hentai.org/?f_search=${encodeURIComponent(bookName)}`,
    }
  })
)

/* ── 标签联想 ─────────────────────────────────────────────────── */

const tagSuggestions = computed(() =>
  suggestTags(activeToken(searchQuery.value).text, translationData.value?.data)
)

const suggestOpen = computed(() => !suggestDismissed.value && tagSuggestions.value.length > 0)

watch(tagSuggestions, () => { highlightIndex.value = -1 })
watch(searchQuery, () => { suggestDismissed.value = false })

function onSearchKeydown(e) {
  if (e.key === 'Escape') {
    suggestDismissed.value = true
    highlightIndex.value = -1
    return
  }
  if (!suggestOpen.value) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    highlightIndex.value = (highlightIndex.value + 1) % tagSuggestions.value.length
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    highlightIndex.value =
      (highlightIndex.value - 1 + tagSuggestions.value.length) % tagSuggestions.value.length
  } else if ((e.key === 'Enter' || e.key === 'Tab') && highlightIndex.value >= 0) {
    e.preventDefault()
    applyTagSuggestion(tagSuggestions.value[highlightIndex.value])
  }
}

function applyTagSuggestion(item) {
  searchQuery.value = applySuggestion(searchQuery.value, item)
  highlightIndex.value = -1
  suggestDismissed.value = true
  searchInputRef.value?.focus()
}

function closeSuggestSoon() {
  clearTimeout(blurTimer)
  blurTimer = setTimeout(() => { suggestDismissed.value = true }, 120)
}

/* ── 交互 ─────────────────────────────────────────────────────── */

function clearSearch() {
  searchQuery.value = ''
  searchInputRef.value?.focus()
}

function showToast(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 2500)
}

function handleGalleryClick(item) {
  if (!item.searchUrl) return
  window.open(item.searchUrl, '_blank', 'noreferrer')
  showToast('未匹配元数据，已用书名打开 E-Hentai 搜索')
}

function goToPage(page) {
  currentPage.value = Math.max(1, Math.min(totalPages.value, page))
}

watch(filteredItems, () => { currentPage.value = 1 })
watch(viewMode, () => { currentPage.value = 1 })

watch(currentPage, v => {
  const query = { ...route.query }
  if (v > 1) query.page = String(v)
  else delete query.page
  router.replace({ query })
})

onMounted(async () => {
  try {
    const [digeRes, galleries, translations] = await Promise.all([
      fetch('/data/future_digi.csv'),
      loadGalleries(),
      loadTranslations(),
    ])
    if (!digeRes.ok) throw new Error('future_digi.csv not found')
    items.value = parseCSV(await digeRes.text())
    galleryMap.value = Object.fromEntries(galleries.map(g => [String(g.gid), g]))
    translationData.value = translations
    const pageFromUrl = parseInt(route.query.page) || 1
    if (pageFromUrl > 1) currentPage.value = pageFromUrl
  } catch (e) {
    error.value = '数据加载失败：' + e.message
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  clearTimeout(toastTimer)
  clearTimeout(blurTimer)
})
</script>

<template>
  <div class="digi-container">
    <div class="digi-header">
      <h1 class="digi-title">实体书单</h1>
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
        <svg class="digi-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
          <circle cx="11" cy="11" r="7.5" /><line x1="20" y1="20" x2="15.5" y2="15.5" />
        </svg>
        <input
          ref="searchInputRef"
          v-model="searchQuery"
          class="digi-search-input"
          type="search"
          aria-label="搜索书单"
          role="combobox"
          aria-autocomplete="list"
          :aria-expanded="suggestOpen"
          aria-controls="digi-tag-suggest"
          :aria-activedescendant="suggestOpen && highlightIndex >= 0 ? `digi-opt-${highlightIndex}` : undefined"
          autocomplete="off"
          spellcheck="false"
          placeholder="搜索 ID / 书名 / 日文名，也支持 id: name: jpname: sid: a: f: 等字段"
          @keydown="onSearchKeydown"
          @blur="closeSuggestSoon"
          @focus="suggestDismissed = false"
        />
        <button
          v-if="searchQuery"
          class="digi-search-clear"
          type="button"
          aria-label="清空搜索词"
          @click="clearSearch"
        >×</button>

        <ul
          v-if="suggestOpen"
          id="digi-tag-suggest"
          class="digi-tag-suggest"
          role="listbox"
          aria-label="标签建议"
        >
          <li
            v-for="(item, i) in tagSuggestions"
            :id="`digi-opt-${i}`"
            :key="item.tag"
            class="digi-tag-suggest-item"
            :class="{ 'is-active': i === highlightIndex }"
            role="option"
            :aria-selected="i === highlightIndex"
            @mousedown.prevent="applyTagSuggestion(item)"
            @mouseenter="highlightIndex = i"
          >
            <span class="digi-tag-suggest-main">{{ item.namespace }}:"{{ item.value }}$"</span>
            <span class="digi-tag-suggest-sub">{{ item.tag_cn || item.value }}</span>
          </li>
        </ul>
      </div>
    </div>

    <div v-if="error" class="digi-empty digi-error">{{ error }}</div>

    <template v-else>
      <div v-if="totalPages > 1" class="digi-pagination">
        <Paginator :page="currentPage" :total="totalPages" @go="goToPage" />
      </div>

      <GalleryList
        :items="normalizedItems"
        :loading="loading"
        :skeleton-count="12"
        empty-text="没有匹配的书目"
        empty-hint="可以按 ID、书名、日文名搜索，也支持 a: / f: 等标签字段"
        @click="handleGalleryClick"
      />

      <div v-if="totalPages > 1" class="digi-pagination">
        <Paginator :page="currentPage" :total="totalPages" @go="goToPage" />
      </div>
    </template>

    <Transition name="digi-toast">
      <div v-if="toast" class="digi-toast" role="status">{{ toast }}</div>
    </Transition>
  </div>
</template>

<style scoped src="@/assets/Printed.css"></style>
