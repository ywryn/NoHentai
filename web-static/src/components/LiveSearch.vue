<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { liveData, liveUrl } from '@/utils/live'
const route = useRoute(), router = useRouter()
const input = ref(''), error = ref(''), busy = ref(false)
interface Item { gid: number; token: string; title: string; pages: number; thumb: string; category: string }
const items = ref<Item[]>([]), host = ref(''), next = ref(''), previous = ref('')
const detail = ref<{title:string;tags:string[];total:number}|null>(null)
let sequence = 0
async function load() {
  const id = ++sequence
  if (!['LiveSearch', 'LiveDetail'].includes(String(route.name))) return
  input.value = String(route.query.q || '')
  busy.value = true; error.value = ''; detail.value = null; items.value = []; next.value = ''
  try {
    const gid = String(route.params.gid || '')
    const site = String(route.query.site || '')
    const data = gid ? await liveData('directory', {gid, token:String(route.query.token || ''), site})
      : await liveData('search', {q: input.value, cursor:String(route.query.cursor || ''), prev:String(route.query.prev || ''), site})
    if (id !== sequence) return
    host.value = data.site
    if (gid) detail.value = data
    else { items.value = data.items; next.value = data.next; previous.value = data.prev }
  } catch (e) { if (id === sequence) error.value = (e as Error).message }
  finally { if (id === sequence) busy.value = false }
}
watch(() => route.fullPath, load, {immediate:true})
function submit() {
  const target = {path:'/live', query:{q:input.value.trim()}}
  if (router.resolve(target).fullPath === route.fullPath) load()
  else router.push(target)
}
</script>
<template>
  <section class="live-panel">
    <router-link v-if="route.params.gid" :to="{path:'/live',query:{q:route.query.q,cursor:route.query.cursor,prev:route.query.prev,site:route.query.site}}">返回实时搜索</router-link>
    <h1>{{ detail?.title || '实时搜索' }}</h1><small>{{ host }}</small>
    <form v-if="!route.params.gid" @submit.prevent="submit"><input v-model="input" aria-label="搜索上游画廊" placeholder="作品名、作者或标签"><button>搜索</button></form>
    <p v-if="busy" role="status">加载中…</p>
    <p v-else-if="error" role="alert">{{ error }} <button @click="load">重试</button> <router-link to="/live">重新搜索</router-link></p>
    <template v-else-if="detail"><p>{{ detail.total }} 页</p><p>{{ detail.tags.join(' · ') }}</p>
      <router-link :to="{name:'LiveReader',params:route.params,query:route.query}">开始阅读</router-link>
    </template>
    <template v-else>
      <router-link v-for="item in items" :key="item.gid" class="live-result" :to="{name:'LiveDetail',params:{gid:item.gid},query:{...route.query,site:host,token:item.token}}">
        <img v-if="item.thumb" loading="lazy" alt="" :src="liveUrl('image',{site:host,imageUrl:item.thumb})">
        <span>{{ item.title }}<small>{{ item.category }} · {{ item.pages }} 页</small></span>
      </router-link>
      <p v-if="!items.length">没有匹配的画廊</p>
      <router-link v-if="previous" :to="{path:'/live',query:{q:route.query.q,site:host,prev:previous}}">上一批结果</router-link>
      <router-link v-if="next" :to="{path:'/live',query:{q:route.query.q,site:host,cursor:next}}">下一批结果</router-link>
    </template>
  </section>
</template>
<style>
.live-panel{max-width:54rem;margin:2rem auto;padding:1rem;color:var(--text-color)}
.live-panel input,.live-panel button,.live-panel a{font:inherit}
.live-panel input,.live-panel button{padding:.65rem;margin:.35rem;border:1px solid currentColor;border-radius:.45rem;background:var(--card-bg);color:inherit}
.live-result{display:flex;align-items:center;gap:1rem;padding:.7rem 0;border-bottom:1px solid var(--border-color);color:inherit;text-decoration:none}
.live-result img{width:3.5rem;height:5rem;object-fit:cover}.mom-mode .live-result img{visibility:hidden}
.live-result small{display:block;margin-top:.35rem}
</style>
