<template>
  <div class="container daily-page">
    <section class="daily-shell">
      <div class="daily-header-card">
        <div class="daily-controls">
          <div class="daily-group-selector" v-if="groups.length">
            <div class="daily-group-selector-header">
              <div>
                <div class="daily-filters-eyebrow">Groups</div>
                <h2 class="daily-filters-title">Choose Snapshot</h2>
              </div>
            </div>
            <div class="daily-group-strip">
              <button
                v-for="(group, index) in groups"
                :key="group.generatedAt || index"
                class="daily-group-pill"
                :class="{ active: index === currentGroupIndex }"
                @click="switchGroup(index)"
                :aria-label="`Switch to group ${index + 1}`"
              >
                <span class="daily-group-pill-top">
                  <span class="daily-group-pill-label">Group {{ index + 1 }}</span>
                  <span class="daily-group-pill-count">{{ (group.galleries || []).length }}</span>
                </span>
                <span class="daily-group-pill-date">{{ formatDate(group.generatedAt) || 'Unknown' }}</span>
              </button>
            </div>
          </div>

          <div class="daily-meta" v-if="currentGroup?.generatedAt">
            <span>Updated {{ formatDate(currentGroup.generatedAt) }}</span>
            <span class="daily-meta-sep">•</span>
            <span>Since {{ currentGroup.cutoffDate }}</span>
            <span class="daily-meta-sep">•</span>
            <span>{{ totalRecords }} galleries</span>
          </div>
        </div>

        <div class="daily-filters" v-if="currentGroup?.filters?.length">
          <div class="daily-filters-header">
            <div>
              <div class="daily-filters-eyebrow">Filters</div>
              <h2 class="daily-filters-title">Match Rules</h2>
            </div>
            <div class="daily-filters-count">{{ currentGroup.filters.length }} rules</div>
          </div>
          <div class="daily-filter-groups">
            <div class="daily-filter-group" v-if="includeFilters.length">
              <span class="daily-filter-group-label">Include</span>
              <div class="daily-filter-chip-list">
                <span
                  v-for="chip in includeFilters"
                  :key="`include-${chip}`"
                  class="filter-chip"
                >{{ chip }}</span>
              </div>
            </div>
            <div class="daily-filter-group" v-if="excludeFilters.length">
              <span class="daily-filter-group-label exclude">Exclude</span>
              <div class="daily-filter-chip-list">
                <span
                  v-for="chip in excludeFilters"
                  :key="`exclude-${chip}`"
                  class="filter-chip filter-chip-exclude"
                >{{ chip.replace(/^-/, '') }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="toolbar">
        <div class="paginator-mini" v-if="totalPages > 1">
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

      <GalleryList :items="normalizedItems" :loading="loading" @click="handleGalleryClick" />

      <div v-if="totalPages > 1" class="toolbar">
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
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useViewMode } from '@/composables/useViewMode'
import GalleryList from '@/components/GalleryList.vue'

const { viewMode } = useViewMode()

const router = useRouter()
const route = useRoute()
const baseUrl = import.meta.env.BASE_URL

const groups = ref([])
const currentGroupIndex = ref(0)
const translationData = ref(null)
const loading = ref(false)
const currentPage = ref(1)
const perPage = ref(30)
const totalRecords = ref(0)
const results = ref([])

const currentGroup = computed(() => groups.value[currentGroupIndex.value] ?? null)
const currentGalleries = computed(() => currentGroup.value?.galleries ?? [])
const includeFilters = computed(() => (currentGroup.value?.filters ?? []).filter(chip => !chip.startsWith('-')))
const excludeFilters = computed(() => (currentGroup.value?.filters ?? []).filter(chip => chip.startsWith('-')))

const typeClassMap = {
  'Doujinshi': 'red', 'Manga': 'orange', 'Artist CG': 'yellow',
  'Game CG': 'green', 'Western': 'gold', 'Non-H': 'lightblue',
  'Image Set': 'blue', 'Cosplay': 'purple', 'Asian Porn': 'pink', 'Misc': 'gray',
}

const totalPages = computed(() => Math.max(1, Math.ceil(totalRecords.value / perPage.value)))
const pageJumpValue = ref('1')

function formatTimestamp(timestamp) {
  if (!timestamp) return ''
  const ts = typeof timestamp === 'string' ? parseInt(timestamp) : timestamp
  if (isNaN(ts)) return ''
  const date = ts.toString().length === 10 ? new Date(ts * 1000) : new Date(ts)
  if (isNaN(date.getTime())) return ''
  return date.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/\//g, '-')
}

function formatDate(isoStr) {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  if (isNaN(d.getTime())) return isoStr
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/\//g, '-')
}

function enrichTags(tags) {
  if (!translationData.value || !Array.isArray(tags)) return []
  return tags
    .filter(tag => typeof tag === 'string' && tag.includes(':'))
    .map(tag => {
      const [namespace, value] = tag.split(':', 2)
      const detail = translationData.value.data
        ?.find(item => item.namespace === namespace)?.data?.[value]
      return { tag, namespace, value, tag_cn: detail?.name || '' }
    })
}

function paginate(page = 1) {
  const galleries = currentGalleries.value
  totalRecords.value = galleries.length
  const start = (page - 1) * perPage.value
  results.value = galleries.slice(start, start + perPage.value).map(item => ({
    gid: item.gid,
    type: item.category,
    typeClass: typeClassMap[item.category] || 'default',
    title: item.title,
    title_jpn: item.title_jpn,
    thumb: item.thumb,
    published: formatTimestamp(item.posted),
    filecount: item.filecount,
    rating: parseFloat(item.rating) || null,
    tags: enrichTags(item.tags || []),
  }))
  currentPage.value = page
}

function goToPage(page) {
  const p = Math.max(1, Math.min(totalPages.value, Number(page)))
  if (p !== currentPage.value) paginate(p)
  pageJumpValue.value = String(p)
}

function submitPageJump() {
  const n = parseInt(pageJumpValue.value)
  if (!isNaN(n)) goToPage(n)
}

function switchGroup(index) {
  if (index < 0 || index >= groups.value.length) return
  currentGroupIndex.value = index
  paginate(1)
  pageJumpValue.value = '1'
}

watch(currentPage, page => {
  pageJumpValue.value = String(page)
  router.replace({ query: page > 1 ? { page: String(page) } : {} })
})

watch(viewMode, () => { paginate(1) })

async function loadData() {
  try {
    const [dailyRes, transRes] = await Promise.all([
      fetch(`${baseUrl}data/daily_search.json`),
      fetch(`${baseUrl}data/translations.json`),
    ])
    if (dailyRes.ok) {
      const data = await dailyRes.json()
      groups.value = Array.isArray(data) ? data : []
    }
    if (transRes.ok) {
      translationData.value = await transRes.json()
    }
  } catch (e) {
    console.error('Error loading daily_search data:', e)
  }
}

const normalizedItems = computed(() => results.value.map(item => ({
  key: item.gid,
  gid: item.gid,
  thumb: item.thumb,
  title: item.title_jpn || item.title,
  badge: item.type,
  badgeClass: item.typeClass,
  tags: item.tags.slice(0, 8).map(t => t.tag_cn || t.value),
  pages: item.filecount ? `${item.filecount}p` : null,
  date: item.published || null,
  rating: item.rating,
  fav: null,
  refId: null,
  noMeta: false,
  noMetaText: null,
})))

function handleGalleryClick(item) {
  if (item.gid) router.push(`/gallery/${item.gid}/?source=daily`)
}

onMounted(async () => {
  loading.value = true
  await loadData()
  const pageFromUrl = parseInt(route.query.page) || 1
  paginate(pageFromUrl)
  loading.value = false
})
</script>

<style src="../assets/Home.css"></style>

<style>
.daily-page {
  padding: 16px;
}

.daily-shell {
  max-width: 1300px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.daily-header-card,
.daily-summary-card,
.daily-group-card {
  background: var(--row-bg);
  border: 1px solid var(--row-border);
  border-radius: 8px;
}

.daily-header-card {
  padding: 16px;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.daily-header-main {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.daily-copy {
  min-width: 0;
}

.daily-eyebrow {
  font-size: 11px;
  font-weight: 700;
  color: var(--muted-color);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.daily-page-title {
  margin: 8px 0 0;
  font-size: clamp(28px, 3vw, 40px);
  line-height: 1.08;
  color: var(--title-color);
}

.daily-page-subtitle {
  margin: 10px 0 0;
  color: var(--muted-color);
  font-size: 15px;
  line-height: 1.5;
  max-width: 760px;
}

.daily-summary-card {
  min-width: 220px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.daily-summary-label,
.daily-group-label {
  font-size: 12px;
  color: var(--muted-color);
  font-weight: 700;
}

.daily-summary-value,
.daily-group-title {
  font-size: 22px;
  line-height: 1.1;
  color: var(--title-color);
}

.daily-summary-sub {
  font-size: 12px;
  color: var(--muted-color);
}

.daily-controls {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.daily-group-selector {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: min(100%, 520px);
}

.daily-group-selector-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.daily-group-strip {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 4px;
  scrollbar-width: thin;
  scrollbar-color: var(--scrollbar-thumb) var(--scrollbar-track);
}

.daily-group-strip::-webkit-scrollbar {
  height: 10px;
}

.daily-group-strip::-webkit-scrollbar-track {
  background: var(--scrollbar-track);
  border-radius: 999px;
}

.daily-group-strip::-webkit-scrollbar-thumb {
  background: var(--scrollbar-thumb);
  border-radius: 999px;
  border: 2px solid transparent;
  background-clip: padding-box;
}

.daily-group-pill {
  appearance: none;
  min-width: 160px;
  padding: 12px 14px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--surface-color);
  color: var(--text-color);
  display: flex;
  flex-direction: column;
  gap: 8px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, transform 0.15s;
}

.daily-group-pill:hover {
  border-color: var(--primary-color);
  background: var(--row-hover-bg);
}

.daily-group-pill.active {
  border-color: rgba(100, 108, 255, 0.5);
  background: linear-gradient(180deg, rgba(100, 108, 255, 0.14), rgba(100, 108, 255, 0.04));
  box-shadow: inset 0 0 0 1px rgba(100, 108, 255, 0.12);
}

.daily-group-pill-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.daily-group-pill-label {
  font-size: 14px;
  font-weight: 700;
  color: var(--title-color);
}

.daily-group-pill-count {
  min-width: 28px;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: var(--row-bg);
  border: 1px solid var(--row-border);
  color: var(--muted-color);
  font-size: 12px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.daily-group-pill.active .daily-group-pill-count {
  background: rgba(100, 108, 255, 0.14);
  border-color: rgba(100, 108, 255, 0.35);
  color: #c7ceff;
}

.daily-group-pill-date {
  font-size: 12px;
  color: var(--muted-color);
}

.daily-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--muted-color);
}

.daily-meta-sep {
  opacity: 0.45;
}

.daily-filters {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-top: 4px;
  border-top: 1px solid var(--row-border);
}

.daily-filters-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.daily-filters-eyebrow {
  font-size: 11px;
  font-weight: 700;
  color: var(--muted-color);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.daily-filters-title {
  margin: 6px 0 0;
  font-size: 18px;
  color: var(--title-color);
}

.daily-filters-count {
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--surface-color);
  color: var(--muted-color);
  font-size: 12px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
}

.daily-filter-groups {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.daily-filter-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.daily-filter-group-label {
  font-size: 12px;
  font-weight: 700;
  color: #7cc3ef;
}

.daily-filter-group-label.exclude {
  color: #e28a8a;
}

.daily-filter-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  background: rgba(76, 163, 221, 0.12);
  border: 1px solid rgba(76, 163, 221, 0.24);
  color: #8fd3ff;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
}

.filter-chip-exclude {
  background: rgba(220, 80, 80, 0.12);
  border-color: rgba(220, 80, 80, 0.3);
  color: #e28a8a;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
}

@media (max-width: 900px) {
  .daily-header-main {
    flex-direction: column;
  }

  .daily-summary-card {
    min-width: 0;
    width: 100%;
  }
}

@media (max-width: 600px) {
  .daily-page {
    padding: 10px;
  }

  .daily-controls {
    align-items: stretch;
  }

  .daily-group-selector,
  .daily-group-strip {
    width: 100%;
  }

  .daily-page-title {
    font-size: 24px;
  }

  .daily-page-subtitle {
    font-size: 14px;
  }

  .daily-filters-header {
    flex-direction: column;
  }
}
</style>
