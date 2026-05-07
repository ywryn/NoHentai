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

        <!-- Card mode -->
        <div v-if="viewMode === 'card'" class="gallery-list">
          <div v-if="loading" class="empty-state">Loading…</div>
          <div v-else-if="!mappedResults.length" class="empty-state">No data</div>
          <article
            v-else
            v-for="item in mappedResults"
            :key="item.gid"
            class="gallery-row"
            @click="navigateToGallery(null, item.gid)"
          >
            <div class="gr-thumb">
              <img :src="item.thumb || ''" :alt="item.type" loading="lazy" />
            </div>
            <div class="gr-body">
              <div class="gr-top">
                <span class="gr-badge" :class="item.typeClass">{{ item.type }}</span>
                <span class="gr-title">{{ item.title_jpn || item.title }}</span>
              </div>
              <div class="gr-tags" v-if="item.tags.length">
                <span v-for="(tag, i) in item.tags.slice(0, 8)" :key="i" class="gr-tag">
                  {{ tag.tag_cn || tag.value }}
                </span>
              </div>
              <div class="gr-meta">
                <Rating :modelValue="item.rating" readonly class="gr-rating" />
                <span class="gr-pages" v-if="item.filecount">{{ item.filecount }}</span>
                <span class="gr-date">{{ item.published }}</span>
                <span class="gr-fav" v-if="item.favCategory">♥ {{ item.favCategory }}</span>
              </div>
            </div>
          </article>
        </div>

        <!-- Cover mode -->
        <div v-else class="vm-cover-grid">
          <div v-if="loading" class="empty-state" style="grid-column:1/-1">Loading…</div>
          <div v-else-if="!mappedResults.length" class="empty-state" style="grid-column:1/-1">No data</div>
          <div
            v-else
            v-for="item in mappedResults"
            :key="item.gid"
            class="vm-cover-card"
            @click="navigateToGallery(null, item.gid)"
          >
            <div class="vm-cover-img">
              <img :src="item.thumb || ''" :alt="item.type" loading="lazy" />
            </div>
            <div class="vm-cover-info">
              <div class="vm-cover-meta">
                <span class="gr-badge" :class="item.typeClass">{{ item.type }}</span>
                <span class="vm-cover-pages">{{ item.filecount }}</span>
              </div>
              <div class="vm-cover-title">{{ item.title_jpn || item.title }}</div>
            </div>
          </div>
        </div>

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
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Rating from 'primevue/rating'
import Popover from 'primevue/popover'
import { useViewMode } from '@/composables/useViewMode'

const { viewMode } = useViewMode()

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
const baseUrl = import.meta.env.BASE_URL
const router = useRouter()
const route = useRoute()

const exTypeList = [
  { name: 'Doujinshi',  color: 'red' },
  { name: 'Manga',      color: 'orange' },
  { name: 'Artist CG',  color: 'yellow' },
  { name: 'Game CG',    color: 'green' },
  { name: 'Western',    color: 'gold' },
  { name: 'Non-H',      color: 'lightblue' },
  { name: 'Image Set',  color: 'blue' },
  { name: 'Cosplay',    color: 'purple' },
  { name: 'Asian Porn', color: 'pink' },
  { name: 'Misc',       color: 'gray' }
]

const exTypeDotColors = {
  'Doujinshi': '#a22',
  'Manga': '#d67e22',
  'Artist CG': '#d6a922',
  'Game CG': '#4caf50',
  'Western': '#d4af37',
  'Non-H': '#4ca3dd',
  'Image Set': '#2a78d6',
  'Cosplay': '#7e57c2',
  'Asian Porn': '#d81b60',
  'Misc': '#757575',
}

const exTypeClassMap = Object.fromEntries(exTypeList.map(t => [t.name, t.color]))
const currentTypeClassMap = computed(() => exTypeClassMap)

const totalPages = computed(() => Math.max(1, Math.ceil(totalRecords.value / perPage.value)))
const pagerPages = computed(() => {
  const total = totalPages.value
  const cur = currentPage.value
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const set = new Set([1, total])
  for (let i = Math.max(1, cur - 1); i <= Math.min(total, cur + 1); i++) set.add(i)
  const sorted = [...set].sort((a, b) => a - b)
  const result = []
  let prev = 0
  for (const p of sorted) {
    if (p - prev > 1) result.push('…')
    result.push(p)
    prev = p
  }
  return result
})

const mappedResults = computed(() => results.value.map(item => ({
  type: item.category,
  typeClass: currentTypeClassMap.value[item.category] || 'default',
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

function formatTimestamp(timestamp) {
  if (!timestamp) return ''
  const ts = typeof timestamp === 'string' ? parseInt(timestamp) : timestamp
  if (isNaN(ts)) return ''
  const date = ts.toString().length === 10 ? new Date(ts * 1000) : new Date(ts)
  if (isNaN(date.getTime())) return ''
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit'
  }).replace(/\//g, '-')
}

function formatFavDate(value) {
  if (!value) return ''
  const str = String(value)
  const match = str.match(/\d{4}-\d{2}-\d{2}/)
  return match ? match[0] : str
}

async function loadGalleriesData() {
  try {
    const response = await fetch(`${baseUrl}data/galleries.json`)
    allGalleries.value = await response.json()
  } catch {
    allGalleries.value = []
  }
}

async function loadTranslationData() {
  try {
    const response = await fetch(`${baseUrl}data/translations.json`)
    translationData.value = await response.json()
  } catch {
    translationData.value = null
  }
}

function enrichTags(tags) {
  if (!translationData.value || !Array.isArray(tags)) return []
  const enrichedTags = []
  for (const tag of tags) {
    if (typeof tag !== 'string' || !tag.includes(':')) continue
    const [namespace, value] = tag.split(':', 2)
    try {
      const tagDetail = translationData.value.data
        .find(item => item.namespace === namespace)?.data?.[value]
      enrichedTags.push({
        tag, namespace, value,
        tag_cn: tagDetail?.name || '',
        intro: tagDetail?.intro || '',
        links: tagDetail?.links || ''
      })
    } catch {
      continue
    }
  }
  return enrichedTags
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
    if (Array.isArray(item.tags)) copy.tags = enrichTags(item.tags)
    return copy
  })
  currentPage.value = page
  setTimeout(() => { loading.value = false }, 100)
}

function performSearch() { filterAndPaginateData(1, searchQuery.value, activeType.value) }
function clearSearch() { searchQuery.value = ''; activeType.value = null; filterAndPaginateData(1) }
function toggleType(type) {
  activeType.value = activeType.value === type ? null : type
  filterAndPaginateData(1, searchQuery.value, activeType.value)
}
function navigateToGallery(id, gid) {
  if (gid) router.push(`/gallery/${gid}/`)
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

watch(currentPage, page => {
  pageJumpValue.value = String(page)
  router.replace({ query: page > 1 ? { page: String(page) } : {} })
})

watch(viewMode, () => {
  filterAndPaginateData(1, searchQuery.value, activeType.value)
})

onMounted(async () => {
  loading.value = true
  await Promise.all([loadGalleriesData(), loadTranslationData()])
  const pageFromUrl = parseInt(route.query.page) || 1
  filterAndPaginateData(pageFromUrl)
})
</script>

<style src="../assets/Home.css"></style>
