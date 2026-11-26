<script setup lang="ts">
import GalleryFilters from './GalleryFilters.vue'
import GalleryList from './GalleryList.vue'
import { categoryMasks, exTypeClassMap } from '@/utils/galleryUtils'
import { computed, onActivated, onDeactivated, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { liveData, liveUrl } from '@/utils/live'

const route = useRoute(), router = useRouter()
const input = ref(''), types = ref<string[]>([])
const error = ref(''), busy = ref(false), searched = ref(false)
interface Item { gid:number; token:string; title:string; pages:number; thumb:string; category:string; tagLabels?:string[]; tags?:string[]; posted?:string }
const items = ref<Item[]>([]), host = ref(''), next = ref(''), previous = ref('')
const applied = ref({q:'', types:[] as string[]})
let controller: AbortController | undefined
let lastUrl = ''
onActivated(() => {
  if (route.fullPath === lastUrl) return
  input.value = String(route.query.q || '')
  types.value = String(route.query.type || '').split(',').filter(Boolean)
})
onDeactivated(() => { controller?.abort(); busy.value = false })
const cards = computed(() => items.value.map(item => ({
  key:item.gid, title:item.title, badge:item.category, badgeClass:exTypeClassMap[item.category],
  pages:item.pages ? item.pages+'p' : '', tags:item.tagLabels || item.tags || [], date:item.posted,
  thumb:item.thumb ? liveUrl('image',{site:host.value,imageUrl:item.thumb}) : '',
  to:{name:'LiveDetail',params:{gid:item.gid},query:{...route.query,site:host.value,token:item.token}}
})))
function edit(q:string, selected:string[]) { input.value=q; types.value=selected }
async function search(q:string, selected:string[], cursor='', prev='') {
  if (busy.value) return
  const request = new AbortController()
  controller = request
  busy.value = true
  error.value = ''
  const included = categoryMasks.reduce((mask,[name,bit]) => selected.includes(String(name)) ? mask | Number(bit) : mask,0)
  try {
    const data = await liveData('search', {q:q.trim(),cursor,prev,site:cursor || prev ? host.value : '',
      f_cats:String(included ? 1023 ^ included : 0)}, request.signal)
    if (request.signal.aborted) return
    items.value=data.items; host.value=data.site; next.value=data.next; previous.value=data.prev
    searched.value=true
    applied.value={q:q.trim(),types:[...selected]}
    const target={path:'/search',query:{q:q.trim() || undefined,type:selected.join(',') || undefined,cursor:cursor || undefined,prev:prev || undefined}}
    lastUrl=router.resolve(target).fullPath
    await router.replace(target)
  } catch (e) {
    if (!request.signal.aborted) error.value=(e as Error).message
  } finally { if (controller === request) busy.value=false }
}
</script>
<template>
  <section class="container home-page"><div class="home-shell">
    <header class="home-header-card">
      <div class="home-header-main"><div class="home-copy">
        <h1 class="catalog-title">搜索</h1>
        <span v-if="host" class="catalog-count">{{host}}</span>
      </div></div>
      <GalleryFilters :query="input" :types="types" profile="live" :submitting="busy"
        label="搜索上游画廊" @change="edit" @clear="edit('', [])" @submit="search" />
    </header>
    <p v-if="error" class="catalog-error" role="alert">{{error}}</p>
    <section v-if="busy || searched" class="catalog-results home-content-panel" :aria-busy="busy">
      <GalleryList :items="cards" :loading="busy" empty-text="没有匹配的画廊" empty-hint="试试其他关键词或标签" />
      <nav v-if="!busy && (previous || next)" class="live-pagination" aria-label="搜索结果翻页">
        <button v-if="previous" class="home-filter-btn" @click="search(applied.q,applied.types,'',previous)">上一批结果</button>
        <button v-if="next" class="home-filter-btn" @click="search(applied.q,applied.types,next)">下一批结果</button>
      </nav>
    </section>
  </div></section>
</template>
<style scoped>
.live-pagination{display:flex;justify-content:center;gap:8px;margin:16px 0}
</style>
