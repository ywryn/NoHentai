<script setup lang="ts">
import { defineAsyncComponent, ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import AccessPassword from './AccessPassword.vue'
import GalleryDetail from './GalleryDetail.vue'
import LiveSearch from './LiveSearch.vue'
import GalleryReader from './reader/GalleryReader.vue'
const GalleryTranslate = defineAsyncComponent(() => import('./GalleryTranslate.vue'))
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
  <template v-if="ready">
    <KeepAlive><LiveSearch v-if="route.name === 'LiveSearch'" /></KeepAlive>
    <GalleryDetail v-if="route.name === 'LiveDetail'" live />
    <GalleryTranslate v-if="route.name === 'LiveTranslate'" :key="JSON.stringify([route.params.gid,route.query.site,route.query.token])" live />
    <GalleryReader v-if="route.name === 'LiveReader'" :key="String(route.params.gid)" />
  </template>
  <AccessPassword v-else prefix="search" label="搜索访问密码" v-model="password"
    :password-loading="busy" :password-error="error" @verify="verify()" @back="$router.options.history.state.back ? $router.back() : $router.replace('/')" />
</template>
<style src="../assets/Home.css"></style>
