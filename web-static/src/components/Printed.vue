<script setup>
import { ref, computed, onMounted } from 'vue'
import * as OpenCC from 'opencc-js'

// 将输入转为繁体，与原始输入一起作为查询词（字段不转换）
const toTraditional = OpenCC.Converter({ from: 'cn', to: 'tw' })

const items = ref([])
const galleryMap = ref({})
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const [digeRes, galRes] = await Promise.all([
      fetch('/data/future_digi.json'),
      fetch('/data/galleries.json'),
    ])
    if (!digeRes.ok) throw new Error('future_digi.json not found')
    const digeData = await digeRes.json()
    const galleries = await galRes.json()

    items.value = digeData.data
    galleryMap.value = Object.fromEntries(
      galleries.map((g) => [String(g.gid), g])
    )
  } catch (e) {
    error.value = '数据加载失败：' + e.message
  } finally {
    loading.value = false
  }
})

function getThumb(sid) {
  if (!sid && sid !== 0) return null
  return galleryMap.value[String(sid)]?.thumb ?? null
}

const matchedCount = computed(
  () => items.value.filter((item) => getThumb(item.sid)).length
)

const searchQuery = ref('')

const filteredItems = computed(() => {
  const raw = searchQuery.value.trim().toLowerCase()
  if (!raw) return items.value
  // 保留原始输入，同时生成繁体版本，两者都用于匹配
  const queries = [...new Set([raw, toTraditional(raw).toLowerCase()])]
  return items.value.filter((item) =>
    [item.ID, item['书名'], item['日文名'], item.sid].some((v) => {
      if (v == null) return false
      const field = String(v).toLowerCase()
      return queries.some((q) => field.includes(q))
    })
  )
})
</script>

<template>
  <div class="dige-container">
    <div class="dige-header">
      <h2 class="dige-title">Printed</h2>
      <div class="dige-stats" v-if="!loading && !error">
        <span>共 {{ items.length }} 部</span>
        <span class="dige-dot">·</span>
        <span>已关联封面 {{ matchedCount }} 部</span>
        <template v-if="searchQuery.trim()">
          <span class="dige-dot">·</span>
          <span>结果 {{ filteredItems.length }} 部</span>
        </template>
      </div>
    </div>

    <div class="dige-search" v-if="!loading && !error">
      <input
        v-model="searchQuery"
        class="dige-search-input"
        placeholder="搜索 ID / 书名 / 日文名 / sid"
        type="search"
      />
    </div>

    <div v-if="loading" class="dige-empty">Loading…</div>
    <div v-else-if="error" class="dige-empty dige-error">{{ error }}</div>

    <div v-else-if="!filteredItems.length" class="dige-empty">No results</div>

    <div v-else class="dige-grid">
      <article v-for="item in filteredItems" :key="item.ID" class="dige-card">
        <!-- 封面 -->
        <div class="dige-thumb">
          <img
            v-if="getThumb(item.sid)"
            :src="getThumb(item.sid)"
            :alt="item['书名']"
            loading="lazy"
          />
          <div v-else class="dige-no-cover">
            <span>{{ item.ID }}</span>
          </div>
        </div>

        <!-- 信息 -->
        <div class="dige-body">
          <span class="dige-id">{{ item.ID }}</span>
          <div class="dige-book-title">{{ item['书名'] }}</div>
          <div v-if="item['备注']" class="dige-remark">{{ item['备注'] }}</div>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped src="@/assets/Printed.css"></style>
