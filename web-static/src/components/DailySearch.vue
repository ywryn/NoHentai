<template>
  <div class="container daily-page">
    <section class="daily-shell">
      <div class="daily-header-card">
        <div class="daily-group-strip" v-if="groups.length">
          <button
            v-for="(group, index) in groups"
            :key="group.generatedAt || index"
            class="daily-group-pill"
            :class="{ active: index === currentGroupIndex }"
            @click="switchGroup(index)"
          >
            <span class="daily-group-pill-label">Group {{ index + 1 }}</span>
            <span class="daily-group-pill-count">{{ (group.galleries || []).length }}</span>
          </button>
        </div>

        <div class="daily-meta" v-if="currentGroup?.generatedAt">
          <span>{{ formatDate(currentGroup.generatedAt) }}</span>
          <span class="daily-meta-sep">·</span>
          <span>Since {{ currentGroup.cutoffDate }}</span>
          <span class="daily-meta-sep">·</span>
          <span>{{ totalRecords }} galleries</span>
        </div>

        <div class="daily-filter-chips" v-if="currentGroup?.filters?.length">
          <span v-for="chip in includeFilters" :key="`i-${chip}`" class="filter-chip">{{ chip }}</span>
          <span v-for="chip in excludeFilters" :key="`e-${chip}`" class="filter-chip filter-chip-exclude">{{ chip.replace(/^-/, '') }}</span>
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

.daily-header-card {
  background: var(--row-bg);
  border: 1px solid var(--row-border);
  border-radius: 8px;
  padding: 14px 16px;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.daily-group-strip {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.daily-group-pill {
  appearance: none;
  height: 34px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--surface-color);
  color: var(--text-color);
  font-size: 13px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.daily-group-pill:hover {
  background: var(--hover-bg);
  border-color: var(--primary-color);
}

.daily-group-pill.active {
  background: rgba(100, 108, 255, 0.12);
  border-color: rgba(100, 108, 255, 0.45);
  color: #c7ceff;
}

.my-app-light .daily-group-pill.active {
  color: #4f46e5;
}

.daily-group-pill-label {
  font-size: 13px;
  font-weight: 700;
}

.daily-group-pill-count {
  min-width: 22px;
  height: 18px;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--row-bg);
  border: 1px solid var(--row-border);
  color: var(--muted-color);
  font-size: 11px;
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

.daily-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--muted-color);
}

.daily-meta-sep {
  opacity: 0.4;
}

.daily-filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  background: rgba(76, 163, 221, 0.12);
  border: 1px solid rgba(76, 163, 221, 0.24);
  color: #8fd3ff;
}

.filter-chip-exclude {
  background: rgba(220, 80, 80, 0.12);
  border-color: rgba(220, 80, 80, 0.3);
  color: #e28a8a;
}

@media (max-width: 600px) {
  .daily-page {
    padding: 10px;
  }
}
</style>
