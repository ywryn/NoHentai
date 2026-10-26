<script setup>
import { computed, ref, watch, provide } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTheme } from '@/composables/useTheme'
import AdminIcon from './AdminIcon.vue'
import AdminConfirm from './AdminConfirm.vue'
import '@/assets/admin.css'

const { isDark, toggleTheme } = useTheme()
const API_BASE = import.meta.env.VITE_API_BASE || 'https://no-hentai.vercel.app'
const password = ref(''), input = ref(''), busy = ref(false), error = ref(''), showPassword = ref(false)
const router = useRouter(), route = useRoute(), drawer = ref(null)
const confirmation = ref(null)
provide('adminConfirm', options => confirmation.value.ask(options))
const navigation = [
  { label: '工作空间', items: [['overview', '概览', 'grid'], ['galleries', '画廊', 'gallery'], ['printed', '实体书单', 'book']] },
  { label: '站点配置', items: [['daily', '每日筛选', 'filter'], ['translate', '翻译配置', 'translate']] },
  { label: '运行管理', items: [['tasks', '任务与发布', 'tasks'], ['health', '服务测活', 'pulse'], ['credentials', '凭证管理', 'key']] },
]
const current = computed(() => navigation.flatMap(g => g.items).find(i => route.path === `/admin/${i[0]}`) || ['overview', '概览', 'grid'])
watch(() => route.path, () => { drawer.value?.close(); window.scrollTo({ top: 0, behavior: 'instant' }) })
async function unlock() {
  busy.value = true; error.value = ''
  try {
    const r = await fetch(`${API_BASE}/api/admin`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'verify', password: input.value }) })
    const data = await r.json()
    if (!r.ok) throw new Error(data.error || '登录失败')
    password.value = input.value; input.value = ''
  } catch (e) { error.value = e.message || '无法连接管理服务，请稍后重试' }
  finally { busy.value = false }
}
async function lock() {
  // A nested editor must approve navigation before credentials are cleared.
  const failure = route.path === '/admin/overview' ? null : await router.push('/admin/overview')
  if (!failure) { password.value = ''; error.value = ''; drawer.value?.close() }
}
</script>

<template>
  <div class="admin-shell" :class="{ 'a-locked': !password }">
    <AdminConfirm ref="confirmation" />
    <template v-if="!password">
      <header class="a-login-header"><RouterLink to="/" class="a-brand"><span class="a-brand-symbol">の</span><span>NoHentai <small>Workspace</small></span></RouterLink><button class="a-button a-ghost" @click="toggleTheme">{{ isDark ? '浅色外观' : '深色外观' }}</button></header>
      <main class="a-login-layout">
        <div class="a-login-story"><span class="a-eyebrow">YOUR COLLECTION, WELL MANAGED</span><h1>内容有序，<br />管理从容。</h1><p>从画廊与实体书单，到每日规则和站点运行，<br class="a-desktop-only" />在一个清晰的工作空间里完成。</p><div class="a-login-feature"><AdminIcon name="shield" /><span>独立身份验证 · 版本记录 · 可控发布</span></div></div>
        <form class="a-login-form a-card" @submit.prevent="unlock">
          <span class="a-icon-tile"><AdminIcon name="key" :size="24" /></span><h2>登录管理后台</h2><p>欢迎回来，继续管理你的站点。</p>
          <div class="a-field"><label for="admin-password">管理密码</label><div class="a-password-input"><input id="admin-password" v-model="input" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" required :disabled="busy" placeholder="输入独立管理密码" /><button type="button" :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">{{ showPassword ? '隐藏' : '显示' }}</button></div></div>
          <div v-if="error" class="a-alert a-alert-error" role="alert"><AdminIcon name="info" />{{ error }}</div>
          <button class="a-button a-primary a-login-submit" :disabled="busy"><span v-if="busy" class="a-spinner" />{{ busy ? '正在验证…' : '进入工作空间' }}<AdminIcon v-if="!busy" name="arrow" :size="17" /></button>
          <p class="a-login-footnote"><AdminIcon name="shield" :size="14" />密码仅保留在本页，刷新后需要重新登录。</p>
        </form>
      </main><footer class="a-login-footer">NoHentai / Private workspace</footer>
    </template>
    <template v-else>
      <aside class="a-sidebar">
        <RouterLink to="/admin/overview" class="a-brand"><span class="a-brand-symbol">の</span><span>NoHentai<small>管理工作空间</small></span></RouterLink>
        <div class="a-workspace-switch"><span class="a-workspace-avatar">N</span><div><strong>个人站点</strong><span><i class="a-dot" />Production</span></div><AdminIcon name="shield" :size="17" /></div>
        <nav aria-label="管理功能"><div v-for="group in navigation" :key="group.label" class="a-nav-group"><p>{{ group.label }}</p><RouterLink v-for="[path, label, icon] in group.items" :key="path" :to="`/admin/${path}`"><AdminIcon :name="icon" :size="19" /><span>{{ label }}</span><span v-if="current[0] === path" class="a-nav-active-dot" /></RouterLink></div></nav>
        <div class="a-sidebar-footer"><RouterLink to="/"><AdminIcon name="arrow" :size="18" />查看网站</RouterLink><button @click="toggleTheme"><AdminIcon name="grid" :size="18" />{{ isDark ? '切换浅色外观' : '切换深色外观' }}</button><button @click="lock"><AdminIcon name="logout" :size="18" />退出管理</button><span>GITHUB + VERCEL</span></div>
      </aside>
      <div class="a-main">
        <header class="a-topbar"><div class="a-breadcrumb"><button class="a-button a-icon-button a-mobile-menu" aria-label="打开管理导航" @click="drawer.showModal()"><AdminIcon name="menu" /></button><span class="a-desktop-only">工作空间</span><AdminIcon class="a-desktop-only" name="chevron" :size="13" /><strong>{{ current[1] }}</strong></div><div class="a-topbar-right"><span class="a-environment"><i class="a-dot" />生产环境</span><span class="a-user-avatar" title="管理员">A</span></div></header>
        <main id="admin-content" class="a-content"><router-view v-slot="{ Component }"><component :is="Component" :key="$route.path" :admin-password="password" /></router-view></main>
      </div>
      <dialog ref="drawer" class="a-nav-drawer" aria-label="管理导航" @click="e => { if (e.target === drawer) drawer.close() }"><div class="a-drawer-header"><span class="a-brand"><span class="a-brand-symbol">の</span>NoHentai</span><button class="a-button a-icon-button" aria-label="关闭管理导航" @click="drawer.close()"><AdminIcon name="close" /></button></div><nav aria-label="手机管理功能"><div v-for="group in navigation" :key="group.label" class="a-nav-group"><p>{{ group.label }}</p><RouterLink v-for="[path,label,icon] in group.items" :key="path" :to="`/admin/${path}`" @click="route.path === `/admin/${path}` && drawer.close()"><AdminIcon :name="icon" /><span>{{ label }}</span></RouterLink></div></nav><div class="a-sidebar-footer"><RouterLink to="/"><AdminIcon name="arrow" />查看网站</RouterLink><button @click="toggleTheme">{{ isDark ? '切换浅色外观' : '切换深色外观' }}</button><button @click="lock"><AdminIcon name="logout" />退出管理</button></div></dialog>
    </template>
  </div>
</template>
