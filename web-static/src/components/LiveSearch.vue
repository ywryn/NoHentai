<script setup lang="ts">
import GalleryFilters from './GalleryFilters.vue'
import GalleryList from './GalleryList.vue'
import { categoryMasks, exTypeClassMap } from '@/utils/galleryUtils'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { liveData, liveUrl } from '@/utils/live'
const route = useRoute(), router = useRouter()
const input = computed(() => String(route.query.q || ''))
const types = computed(() => String(route.query.type || '').split(',').filter(Boolean))
const excluded = computed(() => {
  const selected = categoryMasks.filter(([name]) => types.value.includes(String(name)))
  return selected.length ? 1023 ^ selected.reduce((mask, [,bit]) => mask | Number(bit), 0) : 0
})
const error = ref(''), busy = ref(false)
interface Item { gid: number; token: string; title: string; pages: number; thumb: string; category: string; tags?:string[]; posted?:string }
const items = ref<Item[]>([]), host = ref(''), next = ref(''), previous = ref('')
const detail = ref<{title:string;tags:string[];total:number}|null>(null)
const cards = computed(() => items.value.map(item => ({
  key:item.gid, title:item.title, badge:item.category, badgeClass:exTypeClassMap[item.category],
  pages:item.pages ? item.pages+'p' : '', tags:item.tags || [], date:item.posted,
  thumb:item.thumb ? liveUrl('image',{site:host.value,imageUrl:item.thumb}) : '',
  to:{name:'LiveDetail',params:{gid:item.gid},query:{...route.query,site:host.value,token:item.token}}
})))
let sequence = 0
let controller: AbortController | undefined
onBeforeUnmount(() => controller?.abort())
async function load() {
  const id = ++sequence
  if (!['LiveSearch', 'LiveDetail'].includes(String(route.name))) return
  controller?.abort()
  controller = new AbortController()
  busy.value = true; error.value = ''; detail.value = null; items.value = []; next.value = ''
  try {
    const gid = String(route.params.gid || '')
    const site = String(route.query.site || '')
    const data = gid ? await liveData('directory', {gid, token:String(route.query.token || ''), site}, controller.signal)
      : await liveData('search', {q: input.value, cursor:String(route.query.cursor || ''), prev:String(route.query.prev || ''), site, f_cats:String(excluded.value)}, controller.signal)
    if (id !== sequence) return
    host.value = data.site
    if (gid) detail.value = data
    else { items.value = data.items; next.value = data.next; previous.value = data.prev }
  } catch (e) { if (id === sequence) error.value = (e as Error).message }
  finally { if (id === sequence) busy.value = false }
}
watch(() => route.fullPath, load, {immediate:true})
function changeFilters(q:string, selected:string[]) {
  const query = {...route.query, q:q.trim() || undefined, type:selected.join(',') || undefined,
    prev:undefined, cursor:undefined}
  router.replace({path:'/live',query})
}
</script>
<template>
  <section class="container home-page"><div class="home-shell">
    <header class="home-header-card">
      <router-link v-if="route.params.gid" class="live-back" :to="{path:'/live',query:{q:route.query.q,type:route.query.type,cursor:route.query.cursor,prev:route.query.prev,site:route.query.site}}">‹ 返回实时搜索</router-link>
      <div class="home-header-main"><div class="home-copy">
        <h1 class="catalog-title">{{ detail?.title || (route.params.gid ? '画廊详情' : '实时搜索') }}</h1>
        <span class="catalog-count">{{ host || 'E / Ex' }}<template v-if="detail"> · {{ detail.total }} 页</template></span>
      </div></div>
      <GalleryFilters v-if="!route.params.gid" :query="input" :types="types" profile="live" :debounce="600"
        label="搜索上游画廊" @change="changeFilters" />
    </header>
    <div v-if="error" class="catalog-error" role="alert"><p>{{error}}</p><button @click="load">重试</button> <router-link to="/live">重新搜索</router-link></div>
    <div v-else-if="detail" class="home-header-card">
      <div class="live-tags"><span v-for="tag in detail.tags" :key="tag" class="gr-tag">{{tag}}</span></div>
      <router-link class="live-action" :to="{name:'LiveReader',params:route.params,query:route.query}">开始阅读</router-link>
    </div>
    <p v-else-if="route.params.gid" role="status">加载中…</p>
    <section v-else class="catalog-results home-content-panel" :aria-busy="busy">
      <GalleryList :items="cards" :loading="busy" empty-text="没有匹配的画廊" empty-hint="试试其他关键词或标签" />
      <nav v-if="!busy && (previous || next)" class="live-pagination" aria-label="实时结果翻页">
        <router-link v-if="previous" class="home-filter-btn" :to="{path:'/live',query:{q:route.query.q,type:route.query.type,site:host,prev:previous}}">上一批结果</router-link>
        <router-link v-if="next" class="home-filter-btn" :to="{path:'/live',query:{q:route.query.q,type:route.query.type,site:host,cursor:next}}">下一批结果</router-link>
      </nav>
    </section>
  </div></section>
</template>
<style scoped>
.live-back{color:var(--muted-color);font-size:.875rem;text-decoration:none}
.live-pagination,.live-tags{display:flex;flex-wrap:wrap;gap:8px}
.live-pagination{justify-content:center;margin:16px 0}
</style>
