<script setup>
import { computed, ref, watch, provide, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTheme } from '@/composables/useTheme'
import { currentAdmin, loginAdmin, adminRequest } from '@/utils/adminApi'
import { clearAdminLogin } from '@/utils/adminLogin'
import BrandMark from '@/components/ui/BrandMark.vue'
import AdminIcon from './AdminIcon.vue'
import AdminConfirm from './AdminConfirm.vue'
import AdminPrivacyToggle from './AdminPrivacyToggle.vue'
import '@/assets/admin.css'
import '@/assets/admin-v2.css'
const { isDark, toggleTheme } = useTheme()
const session=ref(null),input=ref(''),remember=ref(true),busy=ref(false),error=ref(''),showPassword=ref(false),restoring=ref(true)
const router=useRouter(),route=useRoute(),drawer=ref(null),confirmation=ref(null),navigationOpen=ref(false)
const boundedWorkspace=computed(()=>Boolean(session.value)&&['/admin/galleries','/admin/printed','/admin/daily'].includes(route.path))
watch(boundedWorkspace,fixed=>document.documentElement.classList.toggle('admin-workspace-fixed',fixed),{immediate:true})
provide('adminConfirm',options=>confirmation.value.ask(options))
provide('adminNavigationOpen',navigationOpen)
provide('adminOpenNavigation',()=>{drawer.value?.showModal();navigationOpen.value=Boolean(drawer.value?.open)})
const navigation=[
 {label:'内容管理',items:[['overview','概览','grid'],['galleries','画廊','gallery'],['printed','实体书单','book'],['daily','每日筛选','filter']]},
 {label:'运行与配置',items:[['services','服务配置','key'],['tasks','任务与调度','tasks'],['health','服务状态','pulse']]},
 {label:'维护',items:[['history','修改记录','clock'],['backups','备份与恢复','download'],['account','账户与会话','shield']]},
]
watch(()=>route.path,()=>{drawer.value?.close();window.scrollTo({top:0,behavior:'instant'})})
async function unlock(){busy.value=true;error.value='';try{session.value=await loginAdmin(input.value,remember.value);input.value=''}catch(e){error.value=e.message}finally{busy.value=false}}
async function lock(){
 const failure=route.path==='/admin/overview'?null:await router.push('/admin/overview')
 if(failure)return
 try{await adminRequest('logout');ended()}catch(e){error.value=e.message}
}
function ended(){session.value=null;input.value='';error.value='';drawer.value?.close();router.replace('/admin/overview')}
onMounted(async()=>{document.documentElement.classList.add('admin-active');clearAdminLogin();try{session.value=await currentAdmin()}catch(e){error.value=e.message}finally{restoring.value=false}})
window.addEventListener('admin-session-ended',ended)
onBeforeUnmount(()=>{document.documentElement.classList.remove('admin-active','admin-workspace-fixed');window.removeEventListener('admin-session-ended',ended)})
</script>

<template>
  <div class="admin-shell" :class="{ 'a-locked': !session, 'a-workspace-fixed': boundedWorkspace }">
    <AdminConfirm ref="confirmation" />
    <div v-if="restoring" class="a-restore-login" role="status"><span class="a-spinner" />正在恢复登录…</div>
    <template v-else-if="!session">
      <header class="a-login-header"><RouterLink to="/" class="a-brand"><BrandMark admin :size="36" /><span>NoHentai <small>站点管理</small></span></RouterLink><button class="a-button a-ghost" @click="toggleTheme"><AdminIcon :name="isDark ? 'sun' : 'moon'" :size="18" />{{ isDark ? '浅色外观' : '深色外观' }}</button></header>
      <main class="a-login-layout">
        <form class="a-login-form a-card" @submit.prevent="unlock">
          <span class="a-icon-tile"><AdminIcon name="key" :size="24" /></span><h2>登录管理后台</h2>
          <div class="a-field"><label for="admin-password">管理密码</label><div class="a-password-input"><input id="admin-password" v-model="input" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" required :disabled="busy" placeholder="输入独立管理密码" /><button type="button" :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">{{ showPassword ? '隐藏' : '显示' }}</button></div></div>
          <div v-if="error" class="a-alert a-alert-error" role="alert"><AdminIcon name="info" />{{ error }}</div>
          <label class="a-remember-login"><input v-model="remember" type="checkbox" :disabled="busy" />记住登录 30 天</label>
          <button class="a-button a-primary a-login-submit" :disabled="busy"><span v-if="busy" class="a-spinner" />{{ busy ? '正在验证…' : '登录' }}<AdminIcon v-if="!busy" name="arrow" :size="17" /></button>
        </form>
      </main><footer class="a-login-footer">NoHentai</footer>
    </template>
    <template v-else>
      <aside class="a-sidebar">
        <RouterLink to="/admin/overview" class="a-brand"><BrandMark admin :size="36" /><span>NoHentai<small>管理工作空间</small></span></RouterLink>
        <nav aria-label="管理功能"><div v-for="group in navigation" :key="group.label" class="a-nav-group"><p>{{ group.label }}</p><RouterLink v-for="[path, label, icon] in group.items" :key="path" :to="`/admin/${path}`"><AdminIcon :name="icon" :size="19" /><span>{{ label }}</span><span v-if="route.path === `/admin/${path}`" class="a-nav-active-dot" /></RouterLink></div></nav>
        <div class="a-sidebar-footer"><RouterLink to="/"><AdminIcon name="arrow" :size="18" />查看网站</RouterLink><AdminPrivacyToggle /><button @click="toggleTheme"><AdminIcon :name="isDark ? 'sun' : 'moon'" :size="18" />{{ isDark ? '切换浅色外观' : '切换深色外观' }}</button><button @click="lock"><AdminIcon name="logout" :size="18" />退出管理</button></div>
      </aside>
      <div class="a-main">
        <main id="admin-content" class="a-content"><div v-if="error" class="a-alert a-alert-error" role="alert">{{ error }}</div><router-view v-slot="{ Component }"><component :is="Component" :key="$route.path"  /></router-view></main>
      </div>
      <dialog id="admin-navigation" ref="drawer" class="a-nav-drawer" @close="navigationOpen=false" aria-label="管理导航" @click="e => { if (e.target === drawer) drawer.close() }"><div class="a-drawer-header"><span class="a-brand"><BrandMark admin :size="36" />NoHentai</span><button class="a-button a-icon-button" aria-label="关闭管理导航" @click="drawer.close()"><AdminIcon name="close" /></button></div><nav aria-label="手机管理功能"><div v-for="group in navigation" :key="group.label" class="a-nav-group"><p>{{ group.label }}</p><RouterLink v-for="[path,label,icon] in group.items" :key="path" :to="`/admin/${path}`" @click="route.path === `/admin/${path}` && drawer.close()"><AdminIcon :name="icon" /><span>{{ label }}</span></RouterLink></div></nav><div class="a-sidebar-footer"><RouterLink to="/"><AdminIcon name="arrow" />查看网站</RouterLink><AdminPrivacyToggle /><button @click="toggleTheme"><AdminIcon :name="isDark ? 'sun' : 'moon'" />{{ isDark ? '切换浅色外观' : '切换深色外观' }}</button><button @click="lock"><AdminIcon name="logout" />退出管理</button></div></dialog>
    </template>
  </div>
</template>
