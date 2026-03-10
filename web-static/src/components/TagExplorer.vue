<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import ToggleSwitch from 'primevue/toggleswitch'

const baseUrl = import.meta.env.BASE_URL

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
  female:    { bg: '#f8c0d6', text: '#8b004a' },
  male:      { bg: '#bdd7f8', text: '#003b8e' },
  artist:    { bg: '#ffd9a0', text: '#7a3900' },
  group:     { bg: '#d9c4f8', text: '#3d0080' },
  parody:    { bg: '#b8f0d0', text: '#005c2e' },
  character: { bg: '#b8ecf5', text: '#004f63' },
  language:  { bg: '#dde3ea', text: '#3a4a5a' },
  cosplayer: { bg: '#f8c0b8', text: '#7a1500' },
  mixed:     { bg: '#fce4a8', text: '#6b4000' },
  other:     { bg: '#cfd8e0', text: '#37474f' },
}

const NS_DARK_COLOR = {
  female:    { bg: '#5a1a35', text: '#ffb3d1' },
  male:      { bg: '#0d2e5a', text: '#90c4ff' },
  artist:    { bg: '#4a2800', text: '#ffc07a' },
  group:     { bg: '#2a0050', text: '#cca8ff' },
  parody:    { bg: '#003d1e', text: '#7ef5b0' },
  character: { bg: '#003042', text: '#7de8ff' },
  language:  { bg: '#1e2630', text: '#aab8c8' },
  cosplayer: { bg: '#4a0d00', text: '#ffaa95' },
  mixed:     { bg: '#3d2600', text: '#ffd07a' },
  other:     { bg: '#1c2830', text: '#90aab8' },
}

function nsColor(ns) {
  const isDark = document.documentElement.classList.contains('my-app-dark')
  return (isDark ? NS_DARK_COLOR : NS_COLOR)[ns] || { bg: '#e0e0e0', text: '#333' }
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
          :title="[isChinese && tag.name ? tag.key : '', tag.intro, tag.freq ? `出现 ${tag.freq} 次` : ''].filter(Boolean).join('\n')"
        >
          {{ displayLabel(tag) }}
          <span v-if="tag.freq" class="tag-freq">{{ tag.freq }}</span>
        </span>
      </div>

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
