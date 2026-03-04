<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import * as OpenCC from 'opencc-js'

const router = useRouter()

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
const toast = ref('')
let toastTimer = null

function showToast(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 2500)
}

function clickCard(item) {
  const sid = item.sid
  if (sid != null && sid !== '' && galleryMap.value[String(sid)]) {
    router.push(`/gallery/${sid}/`)
  } else {
    showToast('未匹配元数据')
  }
}

// namespace 别名表（与 Home.vue 保持一致）
const namespaceAliases = {
  f: 'female', m: 'male', a: 'artist', p: 'parody',
  c: 'character', l: 'language', g: 'group', o: 'other',
  cos: 'cosplayer', x: 'mixed', r: 'reclass',
}

/**
 * 对单条 gallery tags 数组做单个 query 词匹配。
 * 支持：namespace:value（含别名）、tag$（精确）、纯文本（模糊）
 */
function matchTagsByQuery(tags, query) {
  if (!Array.isArray(tags) || !tags.length) return false

  if (query.includes(':')) {
    const colonIdx = query.indexOf(':')
    const nsRaw = query.slice(0, colonIdx)
    const ns = namespaceAliases[nsRaw] || nsRaw
    let val = query.slice(colonIdx + 1)
    if (!val) return false
    const exact = val.endsWith('$')
    if (exact) val = val.slice(0, -1)

    return tags.some((tag) => {
      if (!tag.includes(':')) return false
      const [tagNs, tagVal] = tag.toLowerCase().split(':', 2)
      if (tagNs !== ns) return false
      return exact ? tagVal === val : tagVal.includes(val)
    })
  }

  // 纯文本：匹配任意 tag 的值部分（忽略 namespace 前缀）
  const exact = query.endsWith('$')
  const val = exact ? query.slice(0, -1) : query
  return tags.some((tag) => {
    const lower = tag.toLowerCase()
    const tagVal = lower.includes(':') ? lower.split(':', 2)[1] : lower
    return exact ? tagVal === val : tagVal.includes(val)
  })
}

const filteredItems = computed(() => {
  const raw = searchQuery.value.trim().toLowerCase()
  if (!raw) return items.value
  // 保留原始输入，同时生成繁体版本，两者都用于匹配
  const queries = [...new Set([raw, toTraditional(raw).toLowerCase()])]

  return items.value.filter((item) => {
    // 1. 原有字段匹配（ID / 书名 / 日文名 / sid）
    const fieldMatch = [item.ID, item['书名'], item['日文名'], item.sid].some((v) => {
      if (v == null) return false
      const field = String(v).toLowerCase()
      return queries.some((q) => field.includes(q))
    })
    if (fieldMatch) return true

    // 2. 关联 gallery 的 tags 匹配
    const tags = galleryMap.value[String(item.sid)]?.tags
    return queries.some((q) => matchTagsByQuery(tags, q))
  })
})
</script>

<template>
  <div class="digi-container">
    <div class="digi-header">
      <h2 class="digi-title">Printed</h2>
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

    <div class="digi-search" v-if="!loading && !error">
      <input
        v-model="searchQuery"
        class="digi-search-input"
        placeholder="搜索 ID / 书名 / 日文名 / sid / tag（如 artist:xxx）"
        type="search"
      />
    </div>

    <div v-if="loading" class="digi-empty">Loading…</div>
    <div v-else-if="error" class="digi-empty digi-error">{{ error }}</div>
    <div v-else-if="!filteredItems.length" class="digi-empty">No results</div>
    <div v-else class="digi-grid">
      <article v-for="(item, index) in filteredItems" :key="index" class="digi-card" @click="clickCard(item)">
        <!-- 封面 -->
        <div class="digi-thumb">
          <img
            v-if="getThumb(item.sid)"
            :src="getThumb(item.sid)"
            :alt="item['书名']"
            loading="lazy"
          />
          <div v-else class="digi-no-cover">
            <span>{{ item.ID }}</span>
          </div>
        </div>

        <!-- 信息 -->
        <div class="digi-body">
          <span class="digi-id">{{ item.ID }}</span>
          <div class="digi-book-title">{{ item['书名'] }}</div>
          <div v-if="item['备注']" class="digi-remark">{{ item['备注'] }}</div>
        </div>
      </article>
    </div>

    <Transition name="digi-toast">
      <div v-if="toast" class="digi-toast">{{ toast }}</div>
    </Transition>
  </div>
</template>

<style scoped src="@/assets/Printed.css"></style>
