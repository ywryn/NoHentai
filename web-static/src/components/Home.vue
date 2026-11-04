<template>
  <div class="container home-page">
    <div class="home-shell">
      <div class="home-header-card">
        <div class="home-header-main">
          <div class="home-copy">
            <div class="home-eyebrow">
              NoHentai · 共 {{ totalRecords }} 部
              <span v-if="isFiltered" class="home-eyebrow-sub">（已筛选自 {{ totalAll }} 部）</span>
            </div>
          </div>
        </div>

        <div class="home-filter-panel">
          <GallerySearchInput ref="searchInputRef" v-model="searchQuery" label="搜索画廊">
            <template #actions>
            <button
              class="home-filter-btn"
              :class="{ 'is-on': activeTypes.length }"
              type="button"
              aria-haspopup="dialog"
              :aria-expanded="categoryOpen"
              :title="activeTypes.length ? `已选 ${activeTypes.length} 个分类` : '按分类筛选'"
              @click="toggleCategoryPanel"
            >
              <span
                v-if="activeTypes.length"
                class="home-type-dot"
                :style="{ background: exTypeDotColors[activeTypes[0]] }"
              ></span>
              <svg v-else viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
                <path d="M3 5h18l-7 8v6l-4 2v-8L3 5z" />
              </svg>
              {{ categoryLabel }}
              <span class="home-filter-caret" aria-hidden="true">▾</span>
            </button>
            </template>
          </GallerySearchInput>

          <!-- 当前生效的筛选条件：逐项可移除 -->
          <div v-if="isFiltered" class="home-active-filters">
            <span class="home-active-label">当前条件</span>
            <button
              v-for="term in activeTerms"
              :key="`t-${term.raw}`"
              class="home-filter-chip"
              :class="{ 'is-exclude': term.mode === 'exclude', 'is-or': term.mode === 'or' }"
              type="button"
              :title="`移除条件：${term.raw}`"
              @click="removeTerm(term)"
            >
              <span v-if="term.mode === 'exclude'" class="chip-sign">−</span>
              <span v-else-if="term.mode === 'or'" class="chip-sign">或</span>
              {{ term.raw.replace(/^[-~]/, '') }}
              <span class="chip-x" aria-hidden="true">×</span>
            </button>
            <button
              v-for="type in activeTypes"
              :key="`c-${type}`"
              class="home-filter-chip is-category"
              type="button"
              :title="`移除分类：${type}`"
              @click="toggleType(type)"
            >
              <span class="home-type-dot" :style="{ background: exTypeDotColors[type] }"></span>
              {{ type }}
              <span class="chip-x" aria-hidden="true">×</span>
            </button>
            <button class="home-clear-all" type="button" @click="clearAll">全部清除</button>
          </div>
        </div>
      </div>

      <section class="home-content-panel">
        <div v-if="error" role="alert"><p>{{ error }}</p><button type="button" @click="fetchPage">重新加载</button></div>
        <Paginator v-if="totalPages > 1" :page="currentPage" :total="totalPages" @go="goToPage" />

        <GalleryList
          :items="normalizedItems"
          :loading="loading"
          :skeleton-count="perPage"
          empty-text="没有匹配的画廊"
          empty-hint="试试放宽条件，或点搜索框右侧的「语法」查看高级用法"
        />

        <Paginator v-if="totalPages > 1" :page="currentPage" :total="totalPages" @go="goToPage" />
      </section>

      <Popover ref="categoryPopover" class="category-popover">
        <div class="category-panel">
          <div class="category-panel-head">
            <span class="category-panel-title">按分类筛选</span>
            <button
              v-if="activeTypes.length"
              class="category-reset"
              type="button"
              @click="activeTypes = []"
            >清除</button>
          </div>
          <ul class="category-list">
            <li v-for="opt in categoryOptions" :key="opt.name">
              <label class="category-row" :class="{ 'is-empty': opt.count === 0 && !opt.checked }">
                <input
                  type="checkbox"
                  class="category-check"
                  :checked="opt.checked"
                  :disabled="opt.count === 0 && !opt.checked"
                  @change="toggleType(opt.name)"
                />
                <span class="home-type-dot" :style="{ background: opt.color }"></span>
                <span class="category-name">{{ opt.name }}</span>
                <span class="category-count">{{ opt.count }}</span>
              </label>
            </li>
          </ul>
        </div>
      </Popover>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Popover from 'primevue/popover'
import GalleryList from '@/components/GalleryList.vue'
import Paginator from '@/components/Paginator.vue'
import GallerySearchInput from '@/components/GallerySearchInput.vue'
import { exTypeList, exTypeDotColors, exTypeClassMap, formatTimestamp } from '@/utils/galleryUtils'
import { loadGalleryPage, watchPublicRevision } from '@/composables/useGalleryData'
import {
  parseQuery,
  parsedTerms,
  removeQueryTerm,
} from '@/utils/gallerySearch'

const PER_PAGE = 30

const router = useRouter()
const route = useRoute()

function setQuery(patch) {
  const query = { ...route.query, ...patch }
  for (const key of Object.keys(query)) if (query[key] === undefined || query[key] === '') delete query[key]
  if (JSON.stringify(query) !== JSON.stringify(route.query)) router.replace({ query })
}
const appliedQuery = computed({
  get: () => String(route.query.q || ''),
  set: q => { if (q.trim() !== String(route.query.q || '')) setQuery({ q: q.trim(), page: undefined }) },
})
const searchQuery = appliedQuery
const activeTypes = computed({
  get: () => String(route.query.type || '').split(',').filter(Boolean),
  set: types => setQuery({ type: types.join(','), page: undefined }),
})
const currentPage = computed({
  get: () => Math.max(1, Number.parseInt(route.query.page) || 1),
  set: page => setQuery({ page: page > 1 ? String(page) : undefined }),
})
const pageItems = ref([]), totalRecords = ref(0), totalAll = ref(0)
const typeCounts = ref({}), totalTypeCounts = ref({})
const perPage = ref(PER_PAGE), loading = ref(true), error = ref('')

const searchInputRef = ref()
const categoryPopover = ref()
const categoryOpen = ref(false)


/* ── 过滤（即时，与 Printed 页行为一致） ───────────────────────── */

const parsedQuery = computed(() => parseQuery(appliedQuery.value.trim()))
const activeTerms = computed(() => parsedTerms(parsedQuery.value))

/**
 * 分类选项。
 * 以 exTypeList 为基准，另外补上数据里出现过但不在标准分类表中的类目
 * （如收藏夹里的 private），否则这些画廊无法通过分类筛到。
 * 按全量数量降序，显示的是当前查询下的数量，便于预判点击结果。
 */
const categoryOptions = computed(() => {
  const known = new Set(exTypeList.map(t => t.name))
  const extras = Object.keys(totalTypeCounts.value).filter(name => name && !known.has(name))
  return [...exTypeList.map(t => t.name), ...extras]
    .map(name => ({
      name,
      color: exTypeDotColors[name] || 'var(--faint-color)',
      count: typeCounts.value[name] || 0,
      total: totalTypeCounts.value[name] || 0,
      checked: activeTypes.value.includes(name),
    }))
    .sort((a, b) => b.total - a.total)
})

const categoryLabel = computed(() => {
  const n = activeTypes.value.length
  if (n === 0) return '分类'
  if (n === 1) return activeTypes.value[0]
  return `${activeTypes.value[0]} +${n - 1}`
})

const totalPages = computed(() => Math.max(1, Math.ceil(totalRecords.value / perPage.value)))
const isFiltered = computed(() => activeTerms.value.length > 0 || activeTypes.value.length > 0)

const normalizedItems = computed(() =>
  pageItems.value.map(item => {
    return {
      key: item.gid,
      gid: item.gid,
      to: item.gid ? `/gallery/${item.gid}/` : null,
      thumb: item.thumb,
      title: item.title_jpn || item.title,
      badge: item.category,
      badgeClass: exTypeClassMap[item.category] || 'default',
      tags: item.tagLabels || [],
      pages: item.filecount ? `${item.filecount}p` : null,
      date: item.posted ? formatTimestamp(item.posted) : null,
      rating: item.rating,
      fav: item.favCategory || null,
      refId: null,
      noMeta: false,
      noMetaText: null,
    }
  })
)

function toggleType(type) {
  activeTypes.value = activeTypes.value.includes(type)
    ? activeTypes.value.filter(t => t !== type) : [...activeTypes.value, type]
}

function removeTerm(term) {
  searchQuery.value = removeQueryTerm(searchQuery.value, term)
}

function clearAll() {
  searchInputRef.value?.reset()
  setQuery({ q: undefined, type: undefined, page: undefined })
}

function goToPage(page) {
  currentPage.value = Math.max(1, Math.min(totalPages.value, Number(page) || 1))
}

function toggleCategoryPanel(event) {
  categoryOpen.value = !categoryOpen.value
  categoryPopover.value?.toggle(event)
}

/* Query state lives in the URL. Abort obsolete requests and ignore stale replies. */
let pageController, requestVersion = 0
async function fetchPage() {
  pageController?.abort()
  pageController = new AbortController()
  const version = ++requestVersion
  loading.value = true; error.value = ''
  try {
    const result = await loadGalleryPage({ q: appliedQuery.value, types: activeTypes.value.join(','),
      page: currentPage.value, per_page: perPage.value }, pageController.signal)
    if (version !== requestVersion) return
    pageItems.value = result.items; totalRecords.value = result.total; totalAll.value = result.totalAll
    typeCounts.value = result.categoryCounts; totalTypeCounts.value = result.totalCategoryCounts
    if (result.page !== currentPage.value) currentPage.value = result.page
  } catch (e) {
    if (version === requestVersion && e.name !== 'AbortError') error.value = e.message || '画廊加载失败，请重试'
  } finally { if (version === requestVersion) loading.value = false }
}
watch(() => [route.query.q, route.query.type, route.query.page], fetchPage, { immediate: true })
const stopRevision = watchPublicRevision(fetchPage)
onBeforeUnmount(() => {
  pageController?.abort(); stopRevision()
})
</script>

<style src="../assets/Home.css"></style>
