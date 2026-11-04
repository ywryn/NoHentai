<script setup>
import { ref, computed, onMounted, watch, onBeforeUnmount, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import * as OpenCC from 'opencc-js'
import { watchPublicRevision } from '@/composables/useGalleryData'
import { useViewMode } from '@/composables/useViewMode'
import GalleryList from '@/components/GalleryList.vue'
import Paginator from '@/components/Paginator.vue'
import GallerySearchInput from '@/components/GallerySearchInput.vue'
import { exTypeClassMap } from '@/utils/galleryUtils'
import {
  parseQuery,
  BOOK_FIELDS,
  matchBookTerm,
  passesQuery,
} from '@/utils/gallerySearch'

const PER_PAGE = 30
/** Printed 专有字段，叠加在通用画廊字段之上 */
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
const searchQuery = computed({
  get: () => String(route.query.q || ''),
  set: value => {
    const query = { ...route.query, q: value || undefined, page: undefined }
    for (const key of Object.keys(query)) if (query[key] === undefined) delete query[key]
    router.replace({ query })
  },
})
const currentPage = ref(1)
const perPage = ref(PER_PAGE)
const toast = ref('')

let toastTimer = null

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
  if (item?.cover) return /^[a-f0-9]{32}\.webp$/.test(item.cover) ? `/media/${item.cover}` : `/printed-cover/${encodeURIComponent(item.cover)}`
  const sid = item?.sid
  if (!sid && sid !== 0) return null
  return galleryMap.value[String(sid)]?.thumb ?? null
}

/* ── 搜索（与首页共用同一套解析/匹配实现） ─────────────────────── */

function matchTerm(item, term) {
  return matchBookTerm(item, getGallery(item.sid), term, toTraditional)
}

const filteredItems = computed(() => {
  const raw = searchQuery.value.trim()
  if (!raw) return items.value
  const parsed = parseQuery(raw, BOOK_FIELDS)
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
      badge: gallery?.category || '未关联',
      badgeClass: gallery ? (exTypeClassMap[gallery.category] || 'default') : 'default',
      tags: gallery ? getTagValues(gallery.tags) : [],
      pages: gallery?.filecount ? `${gallery.filecount}p` : null,
      date: null,
      rating: gallery?.rating ?? null,
      fav: null,
      refId: `#${item.ID}`,
      noMeta: !gallery,
      noMetaText: '未关联画廊 · 点击去 E-Hentai 搜索',
      /* 未关联画廊时给一条出路，而不是弹个提示了事 */
      searchUrl: gallery ? null : `https://e-hentai.org/?f_search=${encodeURIComponent(bookName)}`,
    }
  })
)

function showToast(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 2500)
}

function handleGalleryClick(item) {
  if (!item.searchUrl) return
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

let stopRevision
async function loadBooks() {
  const previousPage = parseInt(route.query.page) || currentPage.value
  try {
    const response = await fetch('/api/books')
    if (!response.ok) throw new Error('书单接口暂时不可用')
    const result = await response.json()
    items.value = result.items.map(item => item.book)
    galleryMap.value = Object.fromEntries(result.items.filter(item=>item.gallery).map(item=>[String(item.gallery.gid),item.gallery]))
    translationData.value = result.translations
    await nextTick()
    currentPage.value = Math.max(1, Math.min(previousPage, Math.ceil(filteredItems.value.length/perPage.value)||1))
    error.value = ''
  } catch (e) {
    error.value = '数据加载失败：' + e.message
  } finally {
    loading.value = false
  }
}
onMounted(() => { loadBooks(); stopRevision=watchPublicRevision(loadBooks) })

onBeforeUnmount(() => {
  stopRevision?.()
  clearTimeout(toastTimer)
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

    <GallerySearchInput v-if="!loading && !error" v-model="searchQuery" profile="book" label="搜索书单" placeholder="搜索编号、书名、日文名或标签…" />

    <div v-if="error" class="digi-empty digi-error">{{ error }}</div>

    <template v-else>
      <Paginator v-if="totalPages > 1" :page="currentPage" :total="totalPages" @go="goToPage" />

      <GalleryList
        :items="normalizedItems"
        :loading="loading"
        :skeleton-count="12"
        empty-text="没有匹配的书目"
        empty-hint="可以按 ID、书名、日文名搜索，也支持 a: / f: 等标签字段"
        @click="handleGalleryClick"
      />

      <Paginator v-if="totalPages > 1" :page="currentPage" :total="totalPages" @go="goToPage" />
    </template>

    <Transition name="digi-toast">
      <div v-if="toast" class="digi-toast" role="status">{{ toast }}</div>
    </Transition>
  </div>
</template>

<style scoped src="@/assets/Printed.css"></style>
