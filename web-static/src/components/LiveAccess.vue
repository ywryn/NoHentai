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
  <form v-else class="live-panel" @submit.prevent="verify()">
    <h1>实时搜索访问密码</h1>
    <label>与翻译工作台共用，验证后 72 小时内有效。<input v-model="password" required type="password" autocomplete="current-password"></label>
    <button :disabled="busy">验证密码</button><p role="status">{{ error }}</p>
  </form>
</template>
