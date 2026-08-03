<template>
  <div class="container home-page">
    <div class="home-shell">
      <div class="home-header-card">
        <div class="home-header-main">
          <div class="home-copy">
            <div class="home-eyebrow">
              NoHentai · 共 {{ totalRecords }} 部
              <span v-if="isFiltered" class="home-eyebrow-sub">（已筛选自 {{ allGalleries.length }} 部）</span>
            </div>
          </div>
        </div>

        <div class="home-filter-panel">
          <div class="home-search-row">
            <div class="home-search-wrap">
              <svg class="home-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
                <circle cx="11" cy="11" r="7.5" /><line x1="20" y1="20" x2="15.5" y2="15.5" />
              </svg>
              <input
                ref="searchInputRef"
                v-model="searchQuery"
                class="home-search-input"
                type="search"
                placeholder="搜索标题、作者、标签…"
                aria-label="搜索画廊"
                role="combobox"
                aria-autocomplete="list"
                :aria-expanded="suggestOpen"
                aria-controls="home-tag-suggest"
                :aria-activedescendant="suggestOpen && highlightIndex >= 0 ? `tag-opt-${highlightIndex}` : undefined"
                autocomplete="off"
                spellcheck="false"
                @keydown="onSearchKeydown"
                @blur="closeSuggestSoon"
                @focus="suggestDismissed = false"
              />
              <button
                v-if="searchQuery"
                class="home-search-clear"
                type="button"
                aria-label="清空搜索词"
                @click="clearQuery"
              >×</button>

              <ul
                v-if="suggestOpen"
                id="home-tag-suggest"
                class="home-tag-suggest"
                role="listbox"
                aria-label="标签建议"
              >
                <li
                  v-for="(item, i) in tagSuggestions"
                  :id="`tag-opt-${i}`"
                  :key="item.tag"
                  class="home-tag-suggest-item"
                  :class="{ 'is-active': i === highlightIndex }"
                  role="option"
                  :aria-selected="i === highlightIndex"
                  @mousedown.prevent="applyTagSuggestion(item)"
                  @mouseenter="highlightIndex = i"
                >
                  <span class="home-tag-suggest-main">{{ item.namespace }}:"{{ item.value }}$"</span>
                  <span class="home-tag-suggest-sub">{{ item.tag_cn || item.value }}</span>
                </li>
              </ul>
            </div>

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

            <button
              class="home-syntax-btn"
              type="button"
              aria-haspopup="dialog"
              title="查看高级搜索语法"
              @click="toggleSearchHelp"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
                <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm1 15h-2v-2h2v2zm1.07-7.75l-.9.92C12.45 10.9 12 11.5 12 13h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26A1.96 1.96 0 0 0 10 7a2 2 0 0 0-2 2H6a4 4 0 1 1 8 0c0 .88-.36 1.68-.93 2.25z" />
              </svg>
              语法
            </button>
          </div>

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
        <div class="toolbar" v-if="totalPages > 1">
          <Paginator :page="currentPage" :total="totalPages" @go="goToPage" />
        </div>

        <GalleryList
          :items="normalizedItems"
          :loading="loading"
          :skeleton-count="perPage"
          empty-text="没有匹配的画廊"
          empty-hint="试试放宽条件，或点搜索框右侧的「语法」查看高级用法"
        />

        <div class="home-pagination-footer" v-if="totalPages > 1">
          <Paginator :page="currentPage" :total="totalPages" @go="goToPage" />
        </div>
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

      <Popover ref="searchHelpPopover" class="search-help-popover">
        <div class="search-help-content">
          <div class="search-help-title">高级搜索语法</div>
          <p class="search-help-note">点击示例可直接填入搜索框</p>
          <div class="search-help-list">
            <button
              v-for="row in SEARCH_SYNTAX_HELP"
              :key="row.syntax"
              class="search-help-row"
              type="button"
              @click="applyExample(row.example)"
            >
              <code class="search-help-syntax">{{ row.syntax }}</code>
              <span class="search-help-desc">{{ row.desc }}</span>
              <code class="search-help-example">{{ row.example }}</code>
            </button>
          </div>
        </div>
      </Popover>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Popover from 'primevue/popover'
import GalleryList from '@/components/GalleryList.vue'
import Paginator from '@/components/Paginator.vue'
import { exTypeList, exTypeDotColors, exTypeClassMap, formatTimestamp, enrichTags } from '@/utils/galleryUtils'
import { loadGalleries, loadTranslations } from '@/composables/useGalleryData'
import {
  SEARCH_SYNTAX_HELP,
  parseQuery,
  parsedTerms,
  passesQuery,
  matchGalleryTerm,
  activeToken,
  applySuggestion,
  suggestTags,
} from '@/utils/gallerySearch'

const PER_PAGE = 30
const DEBOUNCE_MS = 220

const router = useRouter()
const route = useRoute()

const searchQuery = ref('')
/** 防抖后的查询词，真正参与过滤 */
const appliedQuery = ref('')
const allGalleries = ref([])
const translationData = ref(null)
const activeTypes = ref([])
const currentPage = ref(1)
const perPage = ref(PER_PAGE)
const loading = ref(true)

const searchInputRef = ref()
const searchHelpPopover = ref()
const categoryPopover = ref()
const categoryOpen = ref(false)
const highlightIndex = ref(-1)
const suggestDismissed = ref(false)

let debounceTimer = null
let blurTimer = null

/* ── 过滤（即时，与 Printed 页行为一致） ───────────────────────── */

const parsedQuery = computed(() => parseQuery(appliedQuery.value.trim()))
const activeTerms = computed(() => parsedTerms(parsedQuery.value))

/** 先只应用文本条件，分类计数基于这一层，方便用户预判点下去有多少结果 */
const queryFiltered = computed(() => {
  if (!appliedQuery.value.trim()) return allGalleries.value
  const parsed = parsedQuery.value
  return allGalleries.value.filter(item => passesQuery(item, parsed, matchGalleryTerm))
})

const typeCounts = computed(() => {
  const counts = {}
  for (const item of queryFiltered.value) {
    counts[item.category] = (counts[item.category] || 0) + 1
  }
  return counts
})

/* 全量计数只用于排序，保证列表顺序不随输入抖动 */
const totalTypeCounts = computed(() => {
  const counts = {}
  for (const item of allGalleries.value) {
    counts[item.category] = (counts[item.category] || 0) + 1
  }
  return counts
})

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

const filtered = computed(() => {
  if (!activeTypes.value.length) return queryFiltered.value
  const set = new Set(activeTypes.value)
  return queryFiltered.value.filter(item => set.has(item.category))
})

const totalRecords = computed(() => filtered.value.length)
const totalPages = computed(() => Math.max(1, Math.ceil(totalRecords.value / perPage.value)))
const isFiltered = computed(() => activeTerms.value.length > 0 || activeTypes.value.length > 0)

const pageItems = computed(() => {
  const start = (currentPage.value - 1) * perPage.value
  return filtered.value.slice(start, start + perPage.value)
})

const normalizedItems = computed(() =>
  pageItems.value.map(item => {
    const tags = Array.isArray(item.tags) ? enrichTags(item.tags, translationData.value) : []
    return {
      key: item.gid,
      gid: item.gid,
      to: item.gid ? `/gallery/${item.gid}/` : null,
      thumb: item.thumb,
      title: item.title_jpn || item.title,
      badge: item.category,
      badgeClass: exTypeClassMap[item.category] || 'default',
      tags: tags.slice(0, 8).map(t => t.tag_cn || t.value),
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

/* ── 标签联想 ─────────────────────────────────────────────────── */

const tagSuggestions = computed(() =>
  suggestTags(activeToken(searchQuery.value).text, translationData.value?.data)
)

const suggestOpen = computed(() => !suggestDismissed.value && tagSuggestions.value.length > 0)

watch(tagSuggestions, () => { highlightIndex.value = -1 })

function onSearchKeydown(e) {
  if (e.key === 'Escape') {
    suggestDismissed.value = true
    highlightIndex.value = -1
    return
  }
  if (!suggestOpen.value) {
    if (e.key === 'Enter') flushQuery()
    return
  }
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    highlightIndex.value = (highlightIndex.value + 1) % tagSuggestions.value.length
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    highlightIndex.value =
      (highlightIndex.value - 1 + tagSuggestions.value.length) % tagSuggestions.value.length
  } else if (e.key === 'Enter') {
    e.preventDefault()
    if (highlightIndex.value >= 0) applyTagSuggestion(tagSuggestions.value[highlightIndex.value])
    else flushQuery()
  } else if (e.key === 'Tab' && highlightIndex.value >= 0) {
    e.preventDefault()
    applyTagSuggestion(tagSuggestions.value[highlightIndex.value])
  }
}

function closeSuggestSoon() {
  clearTimeout(blurTimer)
  blurTimer = setTimeout(() => { suggestDismissed.value = true }, 120)
}

function applyTagSuggestion(item) {
  searchQuery.value = applySuggestion(searchQuery.value, item)
  highlightIndex.value = -1
  suggestDismissed.value = true
  searchInputRef.value?.focus()
}

/* ── 查询同步：输入防抖 → appliedQuery → URL ───────────────────── */

watch(searchQuery, () => {
  suggestDismissed.value = false
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => { appliedQuery.value = searchQuery.value }, DEBOUNCE_MS)
})

function flushQuery() {
  clearTimeout(debounceTimer)
  appliedQuery.value = searchQuery.value
  suggestDismissed.value = true
}

/* 条件变化后回到第 1 页，并把状态同步到 URL 以便后退恢复与分享 */
watch([appliedQuery, activeTypes], () => { currentPage.value = 1 })

watch([appliedQuery, activeTypes, currentPage], () => {
  const query = {}
  const q = appliedQuery.value.trim()
  if (q) query.q = q
  if (activeTypes.value.length) query.type = activeTypes.value.join(',')
  if (currentPage.value > 1) query.page = String(currentPage.value)
  router.replace({ query })
}, { deep: true })

function toggleType(type) {
  const i = activeTypes.value.indexOf(type)
  if (i >= 0) activeTypes.value.splice(i, 1)
  else activeTypes.value.push(type)
}

function removeTerm(term) {
  /* 按原始 token 从查询串里删掉这一段 */
  const next = searchQuery.value
    .split(/([ ,])/)
    .filter(part => part.trim() !== term.raw.trim())
    .join('')
    .replace(/\s{2,}/g, ' ')
    .trim()
  searchQuery.value = next
  flushQuery()
}

function clearQuery() {
  searchQuery.value = ''
  flushQuery()
  searchInputRef.value?.focus()
}

function clearAll() {
  searchQuery.value = ''
  activeTypes.value = []
  flushQuery()
}

function goToPage(page) {
  currentPage.value = Math.max(1, Math.min(totalPages.value, Number(page) || 1))
}

function toggleSearchHelp(event) {
  searchHelpPopover.value?.toggle(event)
}

function toggleCategoryPanel(event) {
  categoryOpen.value = !categoryOpen.value
  categoryPopover.value?.toggle(event)
}

function applyExample(example) {
  const current = searchQuery.value.trim()
  searchQuery.value = current ? `${current} ${example} ` : `${example} `
  flushQuery()
  searchHelpPopover.value?.hide()
  searchInputRef.value?.focus()
}

/* ── 初始化 ───────────────────────────────────────────────────── */

onMounted(async () => {
  const q = String(route.query.q || '')
  const type = String(route.query.type || '')
  searchQuery.value = q
  appliedQuery.value = q
  activeTypes.value = type ? type.split(',').filter(Boolean) : []

  allGalleries.value = await loadGalleries()
  currentPage.value = parseInt(route.query.page) || 1
  loading.value = false

  /* 翻译数据后到：只影响标签文案，不再重跑整个过滤与分页 */
  translationData.value = await loadTranslations()
})

onBeforeUnmount(() => {
  clearTimeout(debounceTimer)
  clearTimeout(blurTimer)
})
</script>

<style src="../assets/Home.css"></style>
