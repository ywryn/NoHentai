<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import ThemeToggle from '@/components/ThemeToggle.vue'

const API_BASE = import.meta.env.VITE_API_BASE || 'https://no-hentai.vercel.app'
const password = ref('')
const input = ref('')
const busy = ref(false)
const error = ref('')
const router = useRouter()
const tabs = [
  ['galleries', '画廊元数据'], ['printed', '实体书单'], ['daily', '每日筛选'],
  ['translate', '翻译配置'], ['tasks', '任务与发布'], ['system', '凭证与测活'],
]
async function unlock() {
  busy.value = true; error.value = ''
  try {
    const r = await fetch(`${API_BASE}/api/admin`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'verify', password: input.value }) })
    const data = await r.json()
    if (!r.ok) throw new Error(data.error || '登录失败')
    password.value = input.value; input.value = ''
  } catch (e) { error.value = e.message || '无法连接管理服务' }
  finally { busy.value = false }
}
async function lock() {
  // Navigate first so each editor's unsaved-change guard runs before credentials disappear.
  if (router.currentRoute.value.path === '/admin') { password.value = ''; return }
  const failure = await router.push('/admin')
  if (!failure) { password.value = ''; error.value = '' }
}
</script>

<template>
  <div class="admin-shell">
    <header class="admin-header">
      <div><span class="admin-eyebrow">NOHENTAI / ADMIN</span><h1>站点管理</h1></div>
      <div class="admin-toolbar"><RouterLink to="/">返回网站</RouterLink><ThemeToggle /><button v-if="password" @click="lock">退出管理</button></div>
    </header>
    <form v-if="!password" class="admin-login admin-card" @submit.prevent="unlock">
      <h2>登录管理后台</h2>
      <p>使用独立的管理密码。凭证仅保留在本页内存，刷新后需要重新登录。</p>
      <label for="admin-password">管理密码</label>
      <input id="admin-password" v-model="input" type="password" autocomplete="current-password" required :disabled="busy" />
      <button class="admin-primary" :disabled="busy">{{ busy ? '正在验证…' : '进入后台' }}</button>
      <p v-if="error" role="alert" class="admin-error">{{ error }}</p>
    </form>
    <template v-else>
      <nav class="admin-tabs" aria-label="管理功能"><RouterLink v-for="[path, label] in tabs" :key="path" :to="`/admin/${path}`">{{ label }}</RouterLink></nav>
      <p class="admin-intro">内容保存到 GitHub master。提交完成后，等待对应发布流程成功才会在线上生效。</p>
      <router-view v-slot="{ Component }"><component :is="Component" :key="$route.path" :admin-password="password" /></router-view>
      <section v-if="$route.path === '/admin'" class="admin-card"><h2>选择一项管理功能</h2><p>画廊与书单分开编辑，抓取任务不会覆盖人工维护的数据。任务与发布页面可查看最近提交是否已部署。</p></section>
    </template>
  </div>
</template>

<style>
.admin-shell { max-width:1280px; margin:0 auto; padding:32px 24px 80px; color:var(--text-color); }
.admin-header,.admin-toolbar,.admin-actions { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
.admin-header h1 { margin:6px 0 18px; font-size:30px; }
.admin-eyebrow { color:var(--muted-color); font-size:12px; letter-spacing:.14em; }
.admin-shell a { color:var(--primary-color); }
.admin-tabs { display:flex; gap:8px; overflow-x:auto; padding:12px 0; border-bottom:1px solid var(--row-border); }
.admin-tabs a { white-space:nowrap; padding:10px 16px; border-radius:8px; text-decoration:none; color:var(--muted-color); }
.admin-tabs a.router-link-active { background:var(--primary-soft-bg); color:var(--primary-color); }
.admin-intro,.admin-shell .muted { color:var(--muted-color); font-size:14px; line-height:1.7; }
.admin-card { background:var(--row-bg); border:1px solid var(--row-border); border-radius:12px; padding:24px; margin:18px 0; min-width:0; }
.admin-card h2 { margin-top:0; font-size:20px; }
.admin-shell button,.admin-shell input,.admin-shell select,.admin-shell textarea { font:inherit; border:1px solid var(--row-border); border-radius:7px; padding:10px 12px; background:var(--row-bg); color:var(--text-color); }
.admin-shell button { cursor:pointer; min-height:42px; }
.admin-shell button:disabled { opacity:.5; cursor:default; }
.admin-shell .admin-primary { background:var(--primary-color); color:#fff; border-color:transparent; }
.admin-shell input:not([type=checkbox]),.admin-shell select,.admin-shell textarea { width:100%; box-sizing:border-box; }
.admin-shell input[type=checkbox] { accent-color:var(--primary-color); }
.admin-shell label { display:grid; gap:7px; font-size:14px; }
.admin-shell textarea { min-height:260px; font-family:ui-monospace,monospace; line-height:1.65; resize:vertical; }
.admin-shell pre { white-space:pre-wrap; overflow-wrap:anywhere; font-size:12px; max-height:360px; overflow:auto; }
.admin-login { max-width:460px; margin:64px auto; display:grid; gap:16px; }
.admin-login p { margin:0; line-height:1.7; }
.admin-error { color:#d64848; overflow-wrap:anywhere; }
.admin-notice { padding:12px 16px; background:var(--primary-soft-bg); border-radius:8px; overflow-wrap:anywhere; }
.admin-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; }
.admin-fields { display:grid; gap:16px; }
.admin-table-wrap { overflow-x:auto; }
.admin-shell table { width:100%; border-collapse:collapse; font-size:14px; }
.admin-shell th,.admin-shell td { padding:12px; text-align:left; border-bottom:1px solid var(--row-border); overflow-wrap:anywhere; }
.admin-shell fieldset { border:0; padding:0; margin:0; min-width:0; }
.admin-shell :focus-visible { outline:2px solid var(--primary-color); outline-offset:3px; }
@media(max-width:700px) { .admin-shell { padding:22px 14px 50px; }.admin-card { padding:16px; }.admin-grid { grid-template-columns:1fr; }.admin-tabs a { padding:9px 10px; }.admin-header h1 { font-size:25px; } }
</style>
