<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import LiveSearch from './LiveSearch.vue'
import GalleryReader from './reader/GalleryReader.vue'
const route = useRoute()
const ready = ref(false), busy = ref(true), error = ref(''), password = ref('')
function expired() { ready.value = false }
async function verify(probe = false) {
  busy.value = true
  error.value = ''
  try {
    const r = await fetch((import.meta.env.VITE_API_BASE ?? '') + '/api/trans-verify', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(probe ? {} : { password: password.value })
    })
    if (r.ok) { ready.value = true; password.value = '' }
    else if (!(probe && r.status === 401)) error.value = r.status === 401 ? '访问密码错误' : '验证失败，请稍后重试'
  } catch { error.value = '连接失败，请重试' }
  finally { busy.value = false }
}
onMounted(() => { window.addEventListener('cost-session-expired', expired); verify(true) })
onBeforeUnmount(() => window.removeEventListener('cost-session-expired', expired))
</script>
<template>
  <GalleryReader v-if="ready && route.name === 'LiveReader'" :key="String(route.params.gid)" />
  <LiveSearch v-else-if="ready" />
  <section v-else class="container home-page"><div class="home-shell">
    <form class="home-header-card live-gate" @submit.prevent="verify()">
      <h1 class="catalog-title">实时搜索</h1>
      <p class="live-note">使用翻译工作台密码，验证后 72 小时内可直接访问。</p>
      <label for="live-password">访问密码</label>
      <input id="live-password" v-model="password" required type="password" autocomplete="current-password">
      <button class="live-action" :disabled="busy">验证密码</button><p v-if="error" role="alert">{{ error }}</p>
    </form>
  </div></section>
</template>
<style src="../assets/Home.css"></style>
<style>
.live-gate {width:min(100%,30rem);margin:clamp(1rem,8vh,5rem) auto;padding:clamp(18px,4vw,32px);box-sizing:border-box}
.live-gate label{font-size:.875rem;font-weight:600}.live-note{margin:0 0 6px;color:var(--muted-color);line-height:1.6}
.live-gate input{min-height:44px;border:1px solid var(--border-color);border-radius:8px;background:var(--surface-color);color:var(--text-color);padding:0 12px;font:inherit}
.live-action{display:inline-flex;align-items:center;justify-content:center;align-self:flex-start;min-height:44px;padding:0 18px;border:1px solid var(--primary-soft-border);border-radius:8px;background:var(--primary-soft-bg);color:var(--primary-on-soft);font:inherit;font-weight:650;text-decoration:none;cursor:pointer}
</style>
