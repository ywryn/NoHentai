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
            type="button"
            :aria-pressed="index === currentGroupIndex"
            @click="switchGroup(index)"
          >
            <span class="daily-group-pill-label">{{ group.name || `筛选组 ${index + 1}` }}</span>
            <span class="daily-group-pill-count">{{ (group.galleries || []).length }}</span>
          </button>
        </div>

        <div class="daily-meta" v-if="currentGroup?.generatedAt">
          <span>更新于 {{ formatDate(currentGroup.generatedAt) }}</span>
          <span class="daily-meta-sep">·</span>
          <span>收录自 {{ currentGroup.cutoffDate }}</span>
          <span class="daily-meta-sep">·</span>
          <span>{{ totalRecords }} 部</span>
        </div>

        <!-- 这些是生成这批数据时用的条件，只作说明、不可交互，
             因此刻意做成低对比的标签而非按钮外观 -->
        <div class="daily-filter-chips" v-if="currentGroup?.filters?.length">
          <span class="daily-filter-label">抓取条件</span>
          <span v-for="chip in includeFilters" :key="`i-${chip}`" class="filter-chip">{{ chip }}</span>
          <span v-for="chip in excludeFilters" :key="`e-${chip}`" class="filter-chip filter-chip-exclude">
            <span class="filter-chip-sign" aria-hidden="true">−</span>{{ chip.replace(/^-/, '') }}
          </span>
        </div>
      </div>

      <div class="toolbar" v-if="totalPages > 1">
        <Paginator :page="currentPage" :total="totalPages" @go="goToPage" />
      </div>

      <GalleryList
        :items="normalizedItems"
        :loading="loading"
        :skeleton-count="perPage"
        empty-text="该筛选组暂无结果"
      />

      <div v-if="totalPages > 1" class="toolbar">
        <Paginator :page="currentPage" :total="totalPages" @go="goToPage" />
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useViewMode } from '@/composables/useViewMode'
import GalleryList from '@/components/GalleryList.vue'
import Paginator from '@/components/Paginator.vue'
import { exTypeClassMap, formatTimestamp, enrichTags } from '@/utils/galleryUtils'
import { loadTranslations } from '@/composables/useGalleryData'

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


const totalPages = computed(() => Math.max(1, Math.ceil(totalRecords.value / perPage.value)))

function formatDate(isoStr) {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  if (isNaN(d.getTime())) return isoStr
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/\//g, '-')
}

function paginate(page = 1) {
  const galleries = currentGalleries.value
  totalRecords.value = galleries.length
  const start = (page - 1) * perPage.value
  results.value = galleries.slice(start, start + perPage.value).map(item => ({
    gid: item.gid,
    type: item.category,
    typeClass: exTypeClassMap[item.category] || 'default',
    title: item.title,
    title_jpn: item.title_jpn,
    thumb: item.thumb,
    published: formatTimestamp(item.posted),
    filecount: item.filecount,
    rating: parseFloat(item.rating) || null,
    tags: enrichTags(item.tags || [], translationData.value),
  }))
  currentPage.value = page
}

function goToPage(page) {
  const p = Math.max(1, Math.min(totalPages.value, Number(page)))
  if (p !== currentPage.value) paginate(p)
}

function switchGroup(index) {
  if (index < 0 || index >= groups.value.length) return
  currentGroupIndex.value = index
  paginate(1)
}

/* 组与页码都写进 URL：刷新后不再跳回第一组，也便于分享 */
watch([currentPage, currentGroupIndex], () => {
  const query = {}
  if (currentGroupIndex.value > 0) query.group = String(currentGroupIndex.value + 1)
  if (currentPage.value > 1) query.page = String(currentPage.value)
  router.replace({ query })
})

watch(viewMode, () => { paginate(1) })

async function loadData() {
  try {
    const [dailyRes, translations] = await Promise.all([
      fetch(`${baseUrl}data/daily_search.json`),
      loadTranslations(),
    ])
    if (dailyRes.ok) {
      const data = await dailyRes.json()
      groups.value = Array.isArray(data) ? data : []
    }
    translationData.value = translations
  } catch (e) {
    console.error('Error loading daily_search data:', e)
  }
}

const normalizedItems = computed(() => results.value.map(item => ({
  key: item.gid,
  gid: item.gid,
  to: item.gid ? `/gallery/${item.gid}/?source=daily` : null,
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


onMounted(async () => {
  loading.value = true
  await loadData()
  const groupFromUrl = parseInt(route.query.group) || 1
  if (groupFromUrl > 1 && groupFromUrl <= groups.value.length) {
    currentGroupIndex.value = groupFromUrl - 1
  }
  paginate(parseInt(route.query.page) || 1)
  loading.value = false
})
</script>

<style src="../assets/Home.css"></style>

<style scoped>
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
  transition:
    background-color var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.daily-group-pill:hover {
  background: var(--hover-bg);
  border-color: var(--primary-color);
}

.daily-group-pill.active {
  background: var(--primary-soft-bg);
  border-color: var(--primary-soft-border);
  color: var(--primary-on-soft);
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
  background: var(--primary-soft-bg);
  border-color: var(--primary-soft-border);
  color: var(--primary-on-soft);
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

.daily-filter-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--muted-color);
  margin-right: 2px;
}

/* 纯说明性标签：无边框、低对比，避免被误认为可点击的筛选控件 */
.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  height: 22px;
  padding: 0 8px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  background: var(--tag-bg);
  border: 1px solid var(--tag-border);
  color: var(--tag-color);
  cursor: default;
}

.filter-chip-exclude {
  color: var(--muted-color);
  text-decoration: line-through;
  text-decoration-thickness: 1px;
  opacity: 0.85;
}

.filter-chip-sign {
  font-weight: 700;
  text-decoration: none;
}

@media (max-width: 560px) {
  .daily-page {
    padding: 10px;
  }
}
</style>
