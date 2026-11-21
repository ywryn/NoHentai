<template>
  <div class="container home-page">
    <div class="home-shell">
      <div class="home-header-card">
        <div class="home-header-main">
          <div class="home-copy">
            <h1 class="catalog-title">收藏画廊</h1>
            <span class="catalog-count" aria-live="polite">{{ loading ? '正在加载…' : `${totalRecords.toLocaleString()} 部` }}<span v-if="isFiltered && !loading"> / {{ totalAll.toLocaleString() }} 部</span></span>
          </div>
        </div>

        <GalleryFilters :query="appliedQuery" :types="activeTypes" :counts="typeCounts" :totals="totalTypeCounts"
          @change="changeFilters" />
      </div>

      <section class="home-content-panel catalog-results" :aria-busy="loading" aria-label="画廊列表">
        <div v-if="error" class="catalog-error" role="alert"><p>{{ error }}</p><button type="button" @click="fetchPage">重新加载</button></div>
        <Paginator v-if="totalPages > 1 && !error" :page="currentPage" :total="totalPages" @go="goToPage" />

        <GalleryList v-if="!error"
          :items="normalizedItems"
          :loading="loading"
          :skeleton-count="perPage"
          empty-text="没有匹配的画廊"
          empty-hint="试试其他关键词，或清除筛选条件。"
        />

        <Paginator v-if="totalPages > 1 && !error" :page="currentPage" :total="totalPages" @go="goToPage" />
      </section>

    </div>
  </div>
</template>

<script setup>
import GalleryFilters from './GalleryFilters.vue'
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import GalleryList from '@/components/GalleryList.vue'
import Paginator from '@/components/Paginator.vue'
import { exTypeClassMap, formatTimestamp } from '@/utils/galleryUtils'
import { loadGalleryPage, watchPublicRevision } from '@/composables/useGalleryData'
import {
  parseQuery,
  parsedTerms,
} from '@/utils/gallerySearch'

const PER_PAGE = 30

const router = useRouter()
const route = useRoute()

function setQuery(patch, history = false) {
  const query = { ...route.query, ...patch }
  for (const key of Object.keys(query)) if (query[key] === undefined || query[key] === '') delete query[key]
  if (JSON.stringify(query) !== JSON.stringify(route.query)) router[history ? 'push' : 'replace']({ query })
}
const appliedQuery = computed(() => String(route.query.q || ''))
const activeTypes = computed(() => String(route.query.type || '').split(',').filter(Boolean))
function changeFilters(q, types) {
  setQuery({q:q.trim(), type:types.join(','), page:undefined})
}
const currentPage = computed({
  get: () => Math.max(1, Number.parseInt(route.query.page) || 1),
  set: page => setQuery({ page: page > 1 ? String(page) : undefined }, true),
})
const pageItems = ref([]), totalRecords = ref(0), totalAll = ref(0)
const typeCounts = ref({}), totalTypeCounts = ref({})
const perPage = ref(PER_PAGE), loading = ref(true), error = ref('')

const totalPages = computed(() => Math.max(1, Math.ceil(totalRecords.value / perPage.value)))
const isFiltered = computed(() => parsedTerms(parseQuery(appliedQuery.value)).length > 0 || activeTypes.value.length > 0)

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

function goToPage(page) {
  currentPage.value = Math.max(1, Math.min(totalPages.value, Number(page) || 1))
}

/* Query state lives in the URL. Abort obsolete requests and ignore stale replies. */
let pageController, requestVersion = 0
async function fetchPage() {
  if (route.name !== 'Home') return
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
