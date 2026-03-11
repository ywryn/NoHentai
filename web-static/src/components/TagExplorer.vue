<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import ToggleSwitch from 'primevue/toggleswitch'
import { useTheme } from '@/composables/useTheme'

const baseUrl = import.meta.env.BASE_URL
const { isDark } = useTheme()

// ── 数据 ──────────────────────────────────────────────
const namespaces = ref([])
const freqMap = ref({})
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const [transRes, galRes] = await Promise.all([
      fetch(`${baseUrl}data/translations.json`),
      fetch(`${baseUrl}data/galleries.json`),
    ])
    if (!transRes.ok) throw new Error('translations.json not found')

    const transJson = await transRes.json()
    const skip = new Set(['rows', 'reclass'])
    namespaces.value = transJson.data.filter(n => !skip.has(n.namespace))

    if (galRes.ok) {
      const galleries = await galRes.json()
      const freq = {}
      for (const g of galleries) {
        for (const tag of (g.tags || [])) {
          freq[tag] = (freq[tag] || 0) + 1
        }
      }
      freqMap.value = freq
    }
  } catch (e) {
    error.value = '数据加载失败：' + e.message
  } finally {
    loading.value = false
  }
})

// ── 状态 ──────────────────────────────────────────────
const isChinese = ref(true)
const searchQuery = ref('')
const activeNs = ref('all')
const PAGE_SIZE = 200
const currentPage = ref(1)

watch(activeNs, () => { currentPage.value = 1; searchQuery.value = '' })
watch(searchQuery, () => { currentPage.value = 1 })

// ── 颜色映射 ──────────────────────────────────────────
const NS_COLOR = {
  female:    { bg: '#f48fb1', text: '#880e4f' },  // 330° 玫瑰粉
  cosplayer: { bg: '#ef9a9a', text: '#b71c1c' },  //   0° 红
  artist:    { bg: '#ffcc80', text: '#e65100' },  //  30° 橙
  mixed:     { bg: '#fff176', text: '#f57f17' },  //  55° 黄
  parody:    { bg: '#c5e1a5', text: '#33691e' },  // 120° 绿
  location:  { bg: '#80cbc4', text: '#00695c' },  // 175° 青绿
  character: { bg: '#81d4fa', text: '#0277bd' },  // 195° 天蓝
  male:      { bg: '#90caf9', text: '#1565c0' },  // 220° 蓝
  group:     { bg: '#ce93d8', text: '#6a1b9a' },  // 270° 紫
  language:  { bg: '#b0bec5', text: '#37474f' },  // neutral 蓝灰
  other:     { bg: '#e0e0e0', text: '#424242' },  // neutral 灰
}

const NS_DARK_COLOR = {
  female:    { bg: '#4a1428', text: '#f48fb1' },
  cosplayer: { bg: '#4a0f0f', text: '#ef9a9a' },
  artist:    { bg: '#4a2800', text: '#ffcc80' },
  mixed:     { bg: '#3d3000', text: '#fff176' },
  parody:    { bg: '#1a3d0d', text: '#c5e1a5' },
  location:  { bg: '#003330', text: '#80cbc4' },
  character: { bg: '#003355', text: '#81d4fa' },
  male:      { bg: '#0a2a55', text: '#90caf9' },
  group:     { bg: '#30004a', text: '#ce93d8' },
  language:  { bg: '#1c2530', text: '#b0bec5' },
  other:     { bg: '#252525', text: '#e0e0e0' },
}

function nsColor(ns) {
  return (isDark.value ? NS_DARK_COLOR : NS_COLOR)[ns] || { bg: '#e0e0e0', text: '#333' }
}

// ── 计算 ──────────────────────────────────────────────
const nsList = computed(() => namespaces.value.map(n => n.namespace))

const allTags = computed(() => {
  const result = []
  for (const ns of namespaces.value) {
    for (const [key, val] of Object.entries(ns.data)) {
      result.push({
        ns: ns.namespace,
        key,
        name: val.name || '',
        intro: val.intro || '',
        freq: freqMap.value[`${ns.namespace}:${key}`] || 0,
      })
    }
  }
  return result
})

const nsTags = computed(() => {
  if (activeNs.value === 'all') return allTags.value
  return allTags.value.filter(t => t.ns === activeNs.value)
})

const filtered = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  const base = q
    ? nsTags.value.filter(t => t.key.toLowerCase().includes(q) || t.name.toLowerCase().includes(q))
    : nsTags.value
  return [...base].sort((a, b) => b.freq - a.freq || a.key.localeCompare(b.key))
})

const totalCount = computed(() => filtered.value.length)
const totalPages = computed(() => Math.ceil(totalCount.value / PAGE_SIZE))

const paginated = computed(() => {
  const start = (currentPage.value - 1) * PAGE_SIZE
  return filtered.value.slice(start, start + PAGE_SIZE)
})

const nsCount = computed(() => {
  const map = { all: allTags.value.length }
  for (const ns of namespaces.value) {
    map[ns.namespace] = Object.keys(ns.data).length
  }
  return map
})

function prevPage() { if (currentPage.value > 1) currentPage.value-- }
function nextPage() { if (currentPage.value < totalPages.value) currentPage.value++ }

function displayLabel(tag) {
  return isChinese.value && tag.name ? tag.name : tag.key
}

// ── Tooltip ──────────────────────────────────────────
const tooltip = ref({ visible: false, text: '', x: 0, y: 0 })
const tooltipEl = ref(null)

function showTooltip(event, tag) {
  const text = [
    `${tag.ns}:${tag.key}`,
    tag.intro,
    tag.freq ? `出现 ${tag.freq} 次` : '',
  ].filter(Boolean).join('\n')
  if (!text) return

  tooltip.value = { visible: true, text, x: 0, y: 0 }

  nextTick(() => {
    const rect = event.currentTarget.getBoundingClientRect()
    const el = tooltipEl.value
    if (!el) return
    const tipW = el.offsetWidth
    const margin = 8
    let x = rect.left + rect.width / 2 - tipW / 2
    // 防止超出左右视口
    x = Math.max(margin, Math.min(x, window.innerWidth - tipW - margin))
    const y = rect.top + window.scrollY - el.offsetHeight - 6
    tooltip.value = { visible: true, text, x, y }
  })
}

function hideTooltip() {
  tooltip.value.visible = false
}
</script>

<template>
  <div class="tag-explorer-wrapper">
    <div v-if="loading" class="loading">Loading...</div>
    <div v-else-if="error" class="error">{{ error }}</div>

    <template v-else>
      <!-- 顶栏：搜索 + 语言切换 -->
      <div class="toolbar">
        <input
          v-model="searchQuery"
          class="search-input"
          type="text"
          placeholder="搜索 Tag（英文 key 或 中文名）"
        />
        <div class="lang-toggle">
          <span class="lang-label">EN</span>
          <ToggleSwitch v-model="isChinese" />
          <span class="lang-label">中文</span>
        </div>
      </div>

      <!-- Namespace 过滤栏 -->
      <div class="ns-bar">
        <button
          :class="['ns-btn', { active: activeNs === 'all' }]"
          @click="activeNs = 'all'"
        >
          All <span class="ns-count">{{ nsCount.all }}</span>
        </button>
        <button
          v-for="ns in nsList"
          :key="ns"
          :class="['ns-btn', { active: activeNs === ns }]"
          :style="activeNs === ns ? { backgroundColor: nsColor(ns).bg, color: nsColor(ns).text, borderColor: nsColor(ns).text + '66' } : {}"
          @click="activeNs = ns"
        >
          {{ ns }} <span class="ns-count">{{ nsCount[ns] }}</span>
        </button>
      </div>

      <!-- 结果统计 + 分页 -->
      <div class="result-bar">
        <span class="result-count">共 {{ totalCount }} 个 Tag</span>
        <div v-if="totalPages > 1" class="pagination">
          <button class="page-btn" :disabled="currentPage === 1" @click="prevPage">‹</button>
          <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
          <button class="page-btn" :disabled="currentPage === totalPages" @click="nextPage">›</button>
        </div>
      </div>

      <!-- Tag 网格 -->
      <div class="tag-grid">
        <span
          v-for="tag in paginated"
          :key="tag.ns + ':' + tag.key"
          class="tag-chip"
          :style="{ backgroundColor: nsColor(tag.ns).bg, color: nsColor(tag.ns).text }"
          @mouseenter="showTooltip($event, tag)"
          @mouseleave="hideTooltip"
        >
          {{ displayLabel(tag) }}
          <span v-if="tag.freq" class="tag-freq">{{ tag.freq }}</span>
        </span>
      </div>

      <!-- 全局 Tooltip -->
      <div
        v-show="tooltip.visible"
        ref="tooltipEl"
        class="tag-tooltip"
        :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }"
      >{{ tooltip.text }}</div>

      <!-- 底部分页 -->
      <div v-if="totalPages > 1" class="result-bar bottom-bar">
        <div class="pagination">
          <button class="page-btn" :disabled="currentPage === 1" @click="prevPage">‹</button>
          <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
          <button class="page-btn" :disabled="currentPage === totalPages" @click="nextPage">›</button>
        </div>
      </div>
    </template>
  </div>
</template>

<style src="../assets/TagExplorer.css"></style>
