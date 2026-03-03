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
        placeholder="搜索 ID / 书名 / 日文名 / sid"
        type="search"
      />
    </div>

    <div v-if="loading" class="digi-empty">Loading…</div>
    <div v-else-if="error" class="digi-empty digi-error">{{ error }}</div>
    <div v-else-if="!filteredItems.length" class="digi-empty">No results</div>
    <div v-else class="digi-grid">
      <article v-for="item in filteredItems" :key="item.ID" class="digi-card" @click="clickCard(item)">
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
