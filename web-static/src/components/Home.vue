<template>
  <div class="container home-page">
    <div class="seo-description">
      <h1>NoHentai – ExHentai & E-Hentai Favorites Backup and Gallery Browser</h1>
      <p>NoHentai is a backup and browsing platform designed for ExHentai and E-Hentai favorite galleries. It allows users to organize and browse doujinshi, manga, artist CG, game CG, and related gallery content with structured metadata. Features include advanced tag filtering, category browsing, keyword search, Japanese title support, tag translation, and detailed gallery information, enabling efficient archive management and discovery of ExHentai and E-Hentai collections.</p>
    </div>

    <div class="home-shell">
      <div class="home-header-card">
        <div class="home-header-main">
          <div class="home-copy">
            <div class="home-eyebrow">NoHentai · {{ totalRecords }} {{ activeType || 'Galleries' }}</div>
          </div>
        </div>

        <div class="home-filter-panel">
          <div class="home-search-row">
            <div class="home-search-wrap">
              <svg class="home-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <circle cx="11" cy="11" r="7.5"/><line x1="20" y1="20" x2="15.5" y2="15.5"/>
              </svg>
              <input
                v-model.trim="searchQuery"
                class="home-search-input"
                placeholder="Search…"
                @keyup.enter="performSearch"
              />
              <span
                class="home-search-help"
                role="button"
                tabindex="0"
                @click="toggleSearchHelp"
                @keyup.enter="toggleSearchHelp"
              >?</span>
            </div>
            <button class="home-search-btn" @click="performSearch">Search</button>
            <button class="home-clear-btn" @click="clearSearch">Clear</button>
          </div>

          <div class="home-filter-meta">
            <div class="home-filter-copy">
              <div class="home-filter-eyebrow">Categories</div>
            </div>
          </div>

          <div class="home-type-grid">
            <button
              class="home-type-pill all-pill"
              :class="{ active: !activeType }"
              @click="toggleType(null)"
            >
              <span class="home-type-dot" style="background:#334155"></span>
              All
            </button>
            <button
              v-for="type in exTypeList"
              :key="type.name"
              class="home-type-pill"
              :class="{ active: activeType === type.name }"
              @click="toggleType(type.name)"
            >
              <span class="home-type-dot" :style="{ background: exTypeDotColors[type.name] }"></span>
              {{ type.name }}
            </button>
          </div>
        </div>
      </div>

      <section class="home-content-panel">
        <div class="toolbar">
          <div class="pagination-control" v-if="totalPages > 1">
            <div class="paginator-mini">
              <button class="pag-btn pag-nav" :disabled="currentPage <= 1" @click="goToPage(1)">«</button>
              <button class="pag-btn pag-nav" :disabled="currentPage <= 1" @click="goToPage(currentPage - 1)">‹</button>
              <label class="pag-jump-inline">
                <input
                  v-model="pageJumpValue"
                  class="pag-jump-input"
                  inputmode="numeric"
                  autocomplete="off"
                  spellcheck="false"
                  @keydown.enter.prevent="submitPageJump"
                />
                <span class="pag-jump-total">/ {{ totalPages }}</span>
              </label>
              <button class="pag-btn pag-nav" :disabled="currentPage >= totalPages" @click="goToPage(currentPage + 1)">›</button>
              <button class="pag-btn pag-nav" :disabled="currentPage >= totalPages" @click="goToPage(totalPages)">»</button>
            </div>
          </div>
        </div>

        <GalleryList :items="normalizedItems" :loading="loading" @click="handleGalleryClick" />

        <div class="home-pagination-footer" v-if="totalPages > 1">
          <div class="pagination-control">
            <div class="paginator-mini">
              <button class="pag-btn pag-nav" :disabled="currentPage <= 1" @click="goToPage(1)">«</button>
              <button class="pag-btn pag-nav" :disabled="currentPage <= 1" @click="goToPage(currentPage - 1)">‹</button>
              <label class="pag-jump-inline">
                <input
                  v-model="pageJumpValue"
                  class="pag-jump-input"
                  inputmode="numeric"
                  autocomplete="off"
                  spellcheck="false"
                  @keydown.enter.prevent="submitPageJump"
                />
                <span class="pag-jump-total">/ {{ totalPages }}</span>
              </label>
              <button class="pag-btn pag-nav" :disabled="currentPage >= totalPages" @click="goToPage(currentPage + 1)">›</button>
              <button class="pag-btn pag-nav" :disabled="currentPage >= totalPages" @click="goToPage(totalPages)">»</button>
            </div>
          </div>
        </div>
      </section>

      <Popover ref="searchHelpPopover" class="search-help-popover">
        <div class="search-help-content">
          <div class="search-help-title">Search Syntax</div>
          <div class="search-help-list">
            <div>AND: space separated terms</div>
            <div>Exclude: -term</div>
            <div>OR: ~term (any ~term matches)</div>
            <div>Phrase: "exact words"</div>
            <div>Wildcard: term*</div>
            <div>Exact tag: tag$</div>
            <div>Fields: title:, uploader:, category:, gid:</div>
            <div>Tags: tag:, f:/m:/a:/p:/c:/l:/g:/o:</div>
          </div>
        </div>
      </Popover>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Popover from 'primevue/popover'
import GalleryList from '@/components/GalleryList.vue'
import { exTypeList, exTypeDotColors, exTypeClassMap, formatTimestamp, enrichTags } from '@/utils/galleryUtils'
import { loadGalleries, loadTranslations } from '@/composables/useGalleryData'

const searchQuery = ref('')
const results = ref([])
const allGalleries = ref([])
const translationData = ref(null)
const currentPage = ref(1)
const perPage = ref(30)
const totalRecords = ref(0)
const activeType = ref(null)
const loading = ref(false)
const pageJumpValue = ref('1')

const searchHelpPopover = ref()
const router = useRouter()
const route = useRoute()

const totalPages = computed(() => Math.max(1, Math.ceil(totalRecords.value / perPage.value)))

const mappedResults = computed(() => results.value.map(item => ({
  type: item.category,
  typeClass: exTypeClassMap[item.category] || 'default',
  title: item.title,
  title_jpn: item.title_jpn,
  published: item.posted ? formatTimestamp(item.posted) : '',
  gid: item.gid,
  filecount: item.filecount ? `${item.filecount}p` : '',
  tags: Array.isArray(item.tags) ? item.tags : [],
  rating: item.rating,
  thumb: item.thumb,
  favTime: formatFavDate(item.favTime),
  favCategory: item.favCategory || '',
})))

function formatFavDate(value) {
  if (!value) return ''
  const str = String(value)
  const match = str.match(/\d{4}-\d{2}-\d{2}/)
  return match ? match[0] : str
}

const namespaceAliases = {
  f: 'female', m: 'male', a: 'artist', p: 'parody',
  c: 'character', l: 'language', g: 'group', o: 'other',
  cos: 'cosplayer', x: 'mixed', r: 'reclass'
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
      if (['title', 'uploader', 'category', 'gid', 'tag'].includes(prefix)) {
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
  if (term.wildcard) return target.startsWith(term.value)
  if (term.quoted) return target.includes(term.value)
  return target.includes(term.value)
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
  if (term.field === 'gid') return String(item.gid || '') === term.value
  if (term.field === 'title') return matchText(item.title, term) || matchText(item.title_jpn, term)
  if (term.field === 'uploader') return matchText(item.uploader, term)
  if (term.field === 'category') return matchText(item.category, term)
  if (term.field === 'tag') return matchTagList(item.tags, term)
  return matchText(item.title, term) || matchText(item.title_jpn, term) ||
    matchText(item.uploader, term) || matchText(item.category, term) ||
    matchTagList(item.tags, term)
}

function filterAndPaginateData(page = 1, keyword = '', type = null) {
  loading.value = true
  let filtered = [...allGalleries.value]
  const query = keyword.trim()
  if (query) {
    const parsed = parseQuery(query)
    filtered = filtered.filter(item => {
      if (!parsed.include.every(term => matchTerm(item, term))) return false
      if (parsed.exclude.some(term => matchTerm(item, term))) return false
      if (parsed.orTerms.length > 0 && !parsed.orTerms.some(term => matchTerm(item, term))) return false
      return true
    })
  }
  if (type) filtered = filtered.filter(item => item.category === type)
  totalRecords.value = filtered.length
  const start = (page - 1) * perPage.value
  results.value = filtered.slice(start, start + perPage.value).map(item => {
    const copy = { ...item }
    if (Array.isArray(item.tags)) copy.tags = enrichTags(item.tags, translationData.value)
    return copy
  })
  currentPage.value = page
  pageJumpValue.value = String(page)
  loading.value = false

  // Sync state to URL so back-navigation restores it
  const q = {}
  if (query) q.q = query
  if (type) q.type = type
  if (page > 1) q.page = String(page)
  router.replace({ query: q })
}

function performSearch() { filterAndPaginateData(1, searchQuery.value, activeType.value) }
function clearSearch() { searchQuery.value = ''; activeType.value = null; filterAndPaginateData(1) }
function toggleType(type) {
  activeType.value = activeType.value === type ? null : type
  filterAndPaginateData(1, searchQuery.value, activeType.value)
}
const normalizedItems = computed(() => mappedResults.value.map(item => ({
  key: item.gid,
  gid: item.gid,
  thumb: item.thumb,
  title: item.title_jpn || item.title,
  badge: item.type,
  badgeClass: item.typeClass,
  tags: item.tags.slice(0, 8).map(t => t.tag_cn || t.value),
  pages: item.filecount || null,
  date: item.published || null,
  rating: item.rating,
  fav: item.favCategory || null,
  refId: null,
  noMeta: false,
  noMetaText: null,
})))

function handleGalleryClick(item) {
  if (item.gid) router.push(`/gallery/${item.gid}/`)
}
function submitPageJump() {
  const normalized = pageJumpValue.value.replace(/[^\d]/g, '')
  if (!normalized) {
    pageJumpValue.value = String(currentPage.value)
    return
  }
  goToPage(normalized)
}
function goToPage(page) {
  const p = Math.max(1, Math.min(totalPages.value, Number(page)))
  if (p !== currentPage.value) filterAndPaginateData(p, searchQuery.value, activeType.value)
}
function toggleSearchHelp(event) { searchHelpPopover.value?.toggle(event) }

onMounted(async () => {
  loading.value = true
  allGalleries.value = await loadGalleries()
  const q = route.query.q || ''
  const type = route.query.type || null
  const page = parseInt(route.query.page) || 1
  searchQuery.value = q
  activeType.value = type
  filterAndPaginateData(page, q, type)

  // Load translations in background; re-enrich tags when ready
  loadTranslations().then(data => {
    translationData.value = data
    filterAndPaginateData(currentPage.value, searchQuery.value, activeType.value)
  })
})
</script>

<style src="../assets/Home.css"></style>
