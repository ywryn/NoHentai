<template>
  <div class="container">
    <!-- 页面头部：标题 + 左右切换 + 筛选条件说明 -->
    <div class="daily-header">
      <div class="daily-title-row">
        <div class="daily-nav">
          <button
            class="daily-nav-btn"
            :disabled="currentGroupIndex === 0"
            @click="switchGroup(currentGroupIndex - 1)"
            aria-label="Previous filter group"
          >&#8592;</button>
          <h2 class="daily-title">Group {{ currentGroupIndex + 1 }}</h2>
          <button
            class="daily-nav-btn"
            :disabled="currentGroupIndex === groups.length - 1"
            @click="switchGroup(currentGroupIndex + 1)"
            aria-label="Next filter group"
          >&#8594;</button>
          <span class="daily-group-index" v-if="groups.length > 1">
            {{ currentGroupIndex + 1 }} / {{ groups.length }}
          </span>
        </div>
        <div class="daily-meta" v-if="currentGroup?.generatedAt">
          <span>Updated: {{ formatDate(currentGroup.generatedAt) }}</span>
          <span class="daily-meta-sep">·</span>
          <span>Since: {{ currentGroup.cutoffDate }}</span>
          <span class="daily-meta-sep">·</span>
          <span>{{ totalRecords }} galleries</span>
        </div>
      </div>
      <div class="daily-filters" v-if="currentGroup?.filters?.length">
        <span
          v-for="chip in currentGroup.filters"
          :key="chip"
          class="filter-chip"
          :class="{ 'filter-chip-exclude': chip.startsWith('-') }"
        >{{ chip }}</span>
      </div>
    </div>

    <!-- 顶部分页器 -->
    <Paginator
      :template="'CurrentPageReport FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink JumpToPageDropdown'"
      :rows="perPage"
      :totalRecords="totalRecords"
      :first="firstIndex"
      :pageLinkSize="3"
      @page="onPageChange"
    />

    <!-- 结果展示 -->
    <div class="results-table">
      <!-- 卡片视图（移动端） -->
      <div class="results-cards">
        <div v-if="!loading && results.length" class="card-grid">
          <article
            v-for="item in results"
            :key="item.gid"
            class="gallery-card"
            @click="navigateToGallery(item.gid)"
          >
            <div class="card-thumb">
              <img :src="item.thumb || '/placeholder.png'" alt="thumb" loading="lazy" />
            </div>
            <div class="card-body">
              <div class="card-title">{{ item.title_jpn || item.title }}</div>
              <div v-if="item.tags && item.tags.length" class="card-tags">
                {{ item.tags.map(t => t.tag_cn || t.tag).join(' · ') }}
              </div>
              <div class="card-meta">
                <span class="card-type">{{ item.category }}</span>
                <span v-if="item.filecount">{{ item.filecount }} pages</span>
              </div>
              <div class="card-sub">
                <span>{{ item.published }}</span>
              </div>
            </div>
          </article>
        </div>
        <div v-else-if="loading" class="empty-state">Loading…</div>
        <div v-else class="empty-state">No data</div>
      </div>

      <!-- 表格视图（桌面端） -->
      <table>
        <thead>
          <tr>
            <th>Type</th>
            <th>Title</th>
            <th style="width: 100px;">Pages</th>
            <th style="width: 160px;">Published</th>
          </tr>
        </thead>

        <tbody v-if="!loading && paddedResults.length">
          <tr
            v-for="item in paddedResults"
            :key="item.gid ?? 'placeholder-' + item.__placeholderId"
            :class="{ 'is-placeholder': item.__placeholder }"
          >
            <td>
              <span v-if="!item.__placeholder" :class="'badge ' + item.typeClass">{{ item.type }}</span>
            </td>
            <td
              v-if="!item.__placeholder"
              class="title-cell"
              @click="navigateToGallery(item.gid)"
              @mouseenter="showPopover($event, item)"
              @mouseleave="hidePopover"
            >
              <div class="title-container">{{ item.title_jpn || item.title }}</div>
              <div class="tags-container" v-if="item.tags && item.tags.length">
                <Tag
                  v-for="(tag, tIdx) in item.tags"
                  :key="tIdx"
                  :value="tag.tag_cn || tag.tag"
                  class="tag"
                  severity="secondary"
                />
              </div>
            </td>
            <td v-else class="title-cell"></td>
            <td>
              <div v-if="!item.__placeholder">{{ item.filecount }}</div>
            </td>
            <td>
              <div class="cell-content" v-if="!item.__placeholder">
                <div>{{ item.published }}</div>
                <div v-if="item.rating != null">
                  <Rating :modelValue="item.rating" readonly />
                </div>
              </div>
            </td>
          </tr>
        </tbody>

        <tbody v-else-if="loading">
          <tr><td colspan="4" class="empty-state">Loading…</td></tr>
        </tbody>
        <tbody v-else>
          <tr><td colspan="4" class="empty-state">No data</td></tr>
        </tbody>
      </table>

      <Popover ref="popover" class="image-popover">
        <img v-if="popoverData?.thumb" :src="popoverData.thumb" alt="thumbnail" />
        <div v-else>No Image Available</div>
      </Popover>
    </div>

    <!-- 底部分页器 -->
    <Paginator
      :template="'CurrentPageReport FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink JumpToPageDropdown'"
      :rows="perPage"
      :totalRecords="totalRecords"
      :first="firstIndex"
      :pageLinkSize="3"
      @page="onPageChange"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Paginator from 'primevue/paginator'
import Tag from 'primevue/tag'
import Rating from 'primevue/rating'
import Popover from 'primevue/popover'

const router = useRouter()
const baseUrl = import.meta.env.BASE_URL

/** ── 状态 ── */
const groups = ref([])                // 全部筛选组数据
const currentGroupIndex = ref(0)      // 当前展示的组索引
const translationData = ref(null)
const loading = ref(false)
const currentPage = ref(1)
const perPage = ref(25)
const totalRecords = ref(0)
const results = ref([])

const popover = ref()
const popoverData = ref(null)

/** ── 当前组 ── */
const currentGroup = computed(() => groups.value[currentGroupIndex.value] ?? null)
const currentGalleries = computed(() => currentGroup.value?.galleries ?? [])

/** ── 类型配置 ── */
const typeClassMap = {
  'Doujinshi': 'red', 'Manga': 'orange', 'Artist CG': 'yellow',
  'Game CG': 'green', 'Western': 'gold', 'Non-H': 'lightblue',
  'Image Set': 'blue', 'Cosplay': 'purple', 'Asian Porn': 'pink', 'Misc': 'gray',
}

/** ── 工具函数 ── */
const firstIndex = computed(() => (currentPage.value - 1) * perPage.value)

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

/** ── 计算属性：placeholder 填充 ── */
const paddedResults = computed(() => {
  const fillCount = Math.max(0, perPage.value - results.value.length)
  if (fillCount === 0) return results.value
  return [
    ...results.value,
    ...Array.from({ length: fillCount }, (_, i) => ({ __placeholder: true, __placeholderId: i })),
  ]
})

/** ── 分页 ── */
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
    category: item.category,
  }))
  currentPage.value = page
}

function onPageChange(e) {
  paginate(Math.floor(e.first / e.rows) + 1)
}

function switchGroup(index) {
  if (index < 0 || index >= groups.value.length) return
  currentGroupIndex.value = index
  paginate(1)
}

/** ── 数据加载 ── */
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

function navigateToGallery(gid) {
  if (gid) router.push(`/gallery/${gid}/?source=daily`)
}

function showPopover(event, item) {
  if (!item?.title) return
  popoverData.value = item
  popover.value?.show(event)
}

function hidePopover() {
  popover.value?.hide()
}

onMounted(async () => {
  loading.value = true
  await loadData()
  paginate(1)
  loading.value = false
})
</script>

<style src="../assets/Home.css"></style>

<style>
/* ── DailySearch 页面专属样式 ── */
.daily-header {
  max-width: 900px;
  margin: 0 auto 12px auto;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.daily-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.daily-nav {
  display: flex;
  align-items: center;
  gap: 10px;
}

.daily-nav-btn {
  appearance: none;
  background: var(--hover-bg);
  border: 1px solid var(--border-color);
  color: var(--text-color);
  border-radius: 6px;
  width: 28px;
  height: 28px;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.daily-nav-btn:hover:not(:disabled) {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: #fff;
}

.daily-nav-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.daily-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-color);
  white-space: nowrap;
}

.daily-group-index {
  font-size: 12px;
  color: var(--text-color);
  opacity: 0.5;
  white-space: nowrap;
}

.daily-meta {
  font-size: 12px;
  color: var(--text-color);
  opacity: 0.7;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.daily-meta-sep {
  opacity: 0.4;
}

.daily-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.filter-chip {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  background: rgba(76, 163, 221, 0.15);
  border: 1px solid rgba(76, 163, 221, 0.4);
  color: #4ca3dd;
}

.filter-chip-exclude {
  background: rgba(220, 80, 80, 0.12);
  border-color: rgba(220, 80, 80, 0.35);
  color: #d45555;
  text-decoration: line-through;
  text-decoration-color: currentColor;
  opacity: 0.8;
}
</style>
