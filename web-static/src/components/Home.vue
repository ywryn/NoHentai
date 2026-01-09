<template>
  <div class="container">
    <div class="control-panel">
      <!-- 类型筛选 -->
      <div class="button-group desktop-types">
        <Button
          v-for="type in currentTypeList"
          :key="type.name"
          :label="type.name"
          :class="['btn', type.color, 'type-btn', { active: activeType === type.name }]"
          @click="toggleType(type.name)"
          aria-label="Filter by type"
        />
      </div>
      <div class="type-scroller">
        <button
          class="type-pill"
          :class="{ active: !activeType }"
          @click="toggleType(null)"
          aria-label="Show all types"
        >
          All
        </button>
        <button
          v-for="type in currentTypeList"
          :key="type.name"
          class="type-pill"
          :class="[type.color, { active: activeType === type.name }]"
          @click="toggleType(type.name)"
          :aria-label="`Filter by ${type.name}`"
        >
          {{ type.name }}
        </button>
      </div>

      <!-- 搜索条 -->
      <div class="search-bar">
        <InputText
          v-model.trim="searchQuery"
          placeholder="Search Keywords"
          class="custom-input"
          @keyup.enter="performSearch"
          aria-label="Search keywords"
        />
        <Button
          label="Search"
          class="btn search-btn"
          @click="performSearch"
          severity="secondary"
          :loading="loading"
        />
        <Button
          label="Clear"
          class="btn clear-btn"
          @click="clearSearch"
          severity="secondary"
          :disabled="loading && !searchQuery && !activeType"
        />
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

    <!-- 表格展示 -->
    <div class="results-table">
      <div class="results-cards">
        <div v-if="!loading && results.length" class="card-grid">
          <article v-for="item in results" :key="item.gid" class="gallery-card" @click="navigateToGallery(item.id, item.gid)">
            <div class="card-thumb">
              <img :src="item.thumb || '/placeholder.png'" alt="thumb" />
            </div>
            <div class="card-body">
              <div class="card-title">{{ item.title_jpn || item.title }}</div>
              <div v-if="item.tags && item.tags.length" class="card-tags">
                {{ item.tags.map(t => t.tag_cn || t.tag).join(' · ') }}
              </div>
              <div class="card-meta">
                <span class="card-type">{{ item.category }}</span>
                <span class="card-pages" v-if="item.filecount">{{ item.filecount }} pages</span>
              </div>
              <div class="card-sub">
                <span class="card-uploader">{{ item.uploader }}</span>
                <span class="card-date">{{ item.favTime ? item.favTime.replace('T', ' ').slice(0, 16) : '' }}</span>
              </div>
            </div>
          </article>
        </div>
        <div v-else-if="loading" class="empty-state">Loading…</div>
        <div v-else class="empty-state">No data</div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Type</th>
            <th>Title</th>
            <th style="width: 150px;">Published</th>
            <th>Uploader</th>
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
              @click="navigateToGallery(item.id, item.gid)"
              @mouseenter="showPopover($event, item)"
              @mouseleave="hidePopover"
            >
              <div class="title-container">
                {{ item.title_jpn || item.title }}
              </div>
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
              <div class="cell-content" v-if="!item.__placeholder">
                <div>{{ item.published }}</div>
                <div v-if="item.rating != null">
                  <Rating :modelValue="item.rating" readonly />
                </div>
              </div>
            </td>
            <td v-if="!item.__placeholder">
              {{ item.uploader }}<br />
              {{ item.filecount }}
            </td>
            <td v-else></td>
          </tr>
        </tbody>

        <tbody v-else-if="loading">
          <tr>
            <td colspan="4" class="empty-state">Loading…</td>
          </tr>
        </tbody>

        <tbody v-else>
          <tr>
            <td colspan="4" class="empty-state">No data</td>
          </tr>
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
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Paginator from 'primevue/paginator'
import Tag from 'primevue/tag'
import Rating from 'primevue/rating'
import Popover from 'primevue/popover'

/** ========= 常量与状态 ========= */
const searchQuery = ref('')
const results = ref([])
const allGalleries = ref([])  // 存储所有画廊数据
const translationData = ref(null)  // 标签翻译数据
const currentPage = ref(1)
const perPage = ref(25)
const totalRecords = ref(0)
const activeType = ref(null)
const loading = ref(false)

const popover = ref()
const popoverData = ref(null)
const router = useRouter()

// EX 类型配置
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

// 预计算类型->颜色映射
const exTypeClassMap = Object.fromEntries(exTypeList.map(t => [t.name, t.color]))

// ExHentai专用类型列表和映射
const currentTypeList = computed(() => exTypeList)
const currentTypeClassMap = computed(() => exTypeClassMap)

/** ========= 工具计算 ========= */
const firstIndex = computed(() => (currentPage.value - 1) * perPage.value)

// 时间戳转换为 年-月-日 格式
function formatTimestamp(timestamp) {
  if (!timestamp) return ''
  
  // 处理字符串或数字时间戳
  const ts = typeof timestamp === 'string' ? parseInt(timestamp) : timestamp
  if (isNaN(ts)) return ''
  
  // 如果时间戳看起来像是秒级时间戳（10位数），则乘以1000转为毫秒
  const date = ts.toString().length === 10 ? new Date(ts * 1000) : new Date(ts)
  
  if (isNaN(date.getTime())) return ''
  
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).replace(/\//g, '-')
}

// ExHentai数据映射和填充逻辑
const paddedResults = computed(() => {
  const mapped = results.value.map(item => {
    return {
      type: item.category,
      typeClass: currentTypeClassMap.value[item.category] || 'default',
      title: item.title,
      title_jpn: item.title_jpn,
      published: item.favTime ? item.favTime.replace('T', ' ').slice(0, 16) : '',
      gid: item.gid,
      id: null,
      uploader: item.uploader,
      filecount: item.filecount ? `${item.filecount} pages` : '',
      tags: Array.isArray(item.tags) ? item.tags : [],
      rating: item.rating,
      thumb: item.thumb
    }
  })

  const fillCount = Math.max(0, perPage.value - mapped.length)
  if (fillCount === 0) return mapped

  const placeholders = Array.from({ length: fillCount }, (_, i) => ({
    __placeholder: true,
    __placeholderId: i
  }))

  return [...mapped, ...placeholders]
})

/** ========= 数据加载和处理 ========= */

// 加载静态 JSON 数据
async function loadGalleriesData() {
  try {
    const response = await fetch('/data/galleries.json')
    allGalleries.value = await response.json()
    console.log(`Loaded ${allGalleries.value.length} galleries from static data`)
  } catch (error) {
    console.error('Error loading galleries data:', error)
    allGalleries.value = []
  }
}

// 加载标签翻译数据
async function loadTranslationData() {
  try {
    const response = await fetch('/data/translations.json')
    translationData.value = await response.json()
    console.log('Loaded translation data')
  } catch (error) {
    console.error('Error loading translation data:', error)
    translationData.value = null
  }
}

// 标签翻译函数
function enrichTags(tags) {
  if (!translationData.value || !Array.isArray(tags)) return []
  
  const enrichedTags = []
  for (const tag of tags) {
    if (typeof tag !== 'string' || !tag.includes(':')) continue
    
    const [namespace, value] = tag.split(':', 2)
    try {
      const tagDetail = translationData.value.data
        .find(item => item.namespace === namespace)?.data?.[value]
      
      if (tagDetail) {
        enrichedTags.push({
          tag: tag,
          namespace: namespace,
          value: value,
          tag_cn: tagDetail.name || '',
          intro: tagDetail.intro || '',
          links: tagDetail.links || ''
        })
      } else {
        // 如果没有翻译，保留原标签
        enrichedTags.push({
          tag: tag,
          namespace: namespace,
          value: value,
          tag_cn: '',
          intro: '',
          links: ''
        })
      }
    } catch (error) {
      // 解析错误，跳过该标签
      continue
    }
  }
  return enrichedTags
}

// 数据过滤和分页函数
function filterAndPaginateData(page = 1, keyword = '', type = null) {
  loading.value = true
  
  let filtered = [...allGalleries.value]
  
  // 关键词搜索
  if (keyword) {
    const kw = keyword.toLowerCase()
    filtered = filtered.filter(item => 
      item.title?.toLowerCase().includes(kw) ||
      item.title_jpn?.toLowerCase().includes(kw) ||
      (Array.isArray(item.tags) && item.tags.some(tag => 
        typeof tag === 'string' && tag.toLowerCase().includes(kw)
      ))
    )
  }
  
  // 类型过滤
  if (type) {
    filtered = filtered.filter(item => item.category === type)
  }
  
  // 更新总数
  totalRecords.value = filtered.length
  
  // 分页
  const start = (page - 1) * perPage.value
  const end = start + perPage.value
  const pageData = filtered.slice(start, end)
  
  // 处理标签翻译
  const processedData = pageData.map(item => {
    const itemCopy = { ...item }
    if (Array.isArray(item.tags)) {
      itemCopy.tags = enrichTags(item.tags)
    }
    return itemCopy
  })
  
  results.value = processedData
  currentPage.value = page
  
  setTimeout(() => {
    loading.value = false
  }, 100) // 短暂延迟以显示loading状态
}

function performSearch () {
  filterAndPaginateData(1, searchQuery.value, activeType.value)
}

function clearSearch () {
  searchQuery.value = ''
  activeType.value = null
  filterAndPaginateData(1)
}

function onPageChange (e) {
  // PrimeVue onPage: { page, first, rows, pageCount }
  const page = Math.floor(e.first / e.rows) + 1
  filterAndPaginateData(page, searchQuery.value, activeType.value)
}

function toggleType (type) {
  activeType.value = activeType.value === type ? null : type
  filterAndPaginateData(1, searchQuery.value, activeType.value)
}


function navigateToGallery (id, gid) {
  if (gid) {
    router.push(`/gallery/${gid}/`)
  }
}

function showPopover (event, item) {
  if (!item?.title) return
  popoverData.value = item
  popover.value?.show(event)
}

function hidePopover () {
  popover.value?.hide()
}

onMounted(async () => {
  loading.value = true
  
  // 并行加载数据
  await Promise.all([
    loadGalleriesData(),
    loadTranslationData()
  ])
  
  // 初始化显示第一页数据
  filterAndPaginateData(1)
})

onBeforeUnmount(() => {
  // 清理资源
})
</script>

<style src="../assets/Home.css"></style>
