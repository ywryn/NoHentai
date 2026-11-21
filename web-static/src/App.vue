<script setup lang="ts">
import BrandMark from '@/components/ui/BrandMark.vue'
import BrandWordmark from '@/components/ui/BrandWordmark.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import { onMounted, onBeforeUnmount, computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useMomMode } from '@/composables/useMomMode'
import ThemeToggle from '@/components/ThemeToggle.vue'
import MomModeToggle from '@/components/MomModeToggle.vue'
import ViewModeToggle from '@/components/ViewModeToggle.vue'

const { initMomMode } = useMomMode()
const route = useRoute()
function focusContent() { document.getElementById("main-content")?.focus() }

/** 阅读器与翻译工作台是沉浸式全屏页，不显示全局导航（由路由 meta 声明） */
const isImmersivePage = computed(() => Boolean(route.meta.immersive))

/** 视图模式切换只对列表页有意义，其它页面隐藏，避免出现无效控件 */
const showViewModeToggle = computed(() =>
  ['/', '/printed', '/daily', '/search'].includes(route.path)
)

const navItems = [
  {
    to: '/',
    label: '首页',
    title: 'Home',
    icon: 'home',
  },
  {
    to: '/data',
    label: '统计',
    title: 'Data Analys',
    icon: 'chart',
  },
  {
    to: '/printed',
    label: '书单',
    title: 'Printed',
    icon: 'book',
  },
  {
    to: '/daily',
    label: '每日',
    title: 'Daily Search',
    icon: 'calendar',
  },
  { to: '/search', label: '搜索', title: '搜索', icon: 'search' },
  {
    to: '/translate',
    label: '翻译',
    title: 'Translate',
    icon: 'translate',
  },
]

const mobile = window.matchMedia('(max-width: 767px)')
const narrow = ref(mobile.matches)
const menu = ref<HTMLElement>()
const trigger = ref<HTMLButtonElement>()
const open = ref(false)
const nativePopover = 'showPopover' in HTMLElement.prototype
function closeMenu() {
  if (nativePopover && menu.value?.matches(':popover-open')) menu.value.hidePopover()
  open.value = false
}
function toggleMenu() {
  if (!nativePopover) open.value = !open.value
}
function layout() { closeMenu(); narrow.value = mobile.matches }
function outside(event: Event) {
  if (open.value && !menu.value?.contains(event.target as Node) && !trigger.value?.contains(event.target as Node)) closeMenu()
}
function escape(event: KeyboardEvent) {
  if (open.value && event.key === 'Escape') { closeMenu(); trigger.value?.focus() }
}
watch(() => route.fullPath, closeMenu)
onMounted(() => {
  initMomMode()
  mobile.addEventListener('change', layout)
  if (!nativePopover) {
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
  }
})
onBeforeUnmount(() => {
  mobile.removeEventListener('change', layout)
  document.removeEventListener('pointerdown', outside)
  document.removeEventListener('keydown', escape)
})
</script>

<template>
  <div class="app-shell" :class="{'translate-entry': route.name === 'TranslateLookup'}">
    <a v-if="!isImmersivePage" class="skip-link" href="#main-content" @click.prevent="focusContent">跳至内容</a>
    <header class="navigation-bar" v-if="!isImmersivePage">
      <RouterLink class="brand-logo" to="/" aria-label="NoHentai 首页"><BrandMark :size="32" /><BrandWordmark /></RouterLink>

      <div class="nav-actions">
        <template v-if="!narrow">
        <span class="nav-view-mode"><ViewModeToggle v-if="showViewModeToggle" /></span>
        <MomModeToggle />
        <ThemeToggle />
        </template>
        <button v-if="narrow" ref="trigger" class="nav-trigger toolbar-icon-button" aria-label="页面导航" aria-controls="site-nav" :popovertarget="nativePopover ? 'site-nav' : undefined"
          :aria-expanded="open" @click="toggleMenu"><AppIcon :name="open ? 'close' : 'menu'" :size="20" /></button>
      </div>
      <nav ref="menu" id="site-nav" class="nav-menu" :class="{expanded:open}"
        :popover="narrow && nativePopover ? 'auto' : undefined" aria-label="主导航"
        @toggle="open = ($event as ToggleEvent).newState === 'open'">
        <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" @click="closeMenu">
          <AppIcon v-if="narrow" :name="item.icon" :size="20" />{{ item.label }}
        </RouterLink>
        <div v-if="narrow" class="menu-settings">
          <ThemeToggle v-slot="{state}">明暗主题<small>{{ state }}</small></ThemeToggle>
          <MomModeToggle v-slot="{state}">妈妈模式<small>{{ state }}</small></MomModeToggle>
          <ViewModeToggle v-if="showViewModeToggle" v-slot="{state}">浏览视图<small>{{ state }}</small></ViewModeToggle>
        </div>
      </nav>
    </header>

    <component :is="route.path.startsWith('/admin') ? 'div' : 'main'" id="main-content" class="route-shell" tabindex="-1">
      <router-view />
    </component>
  </div>
</template>

<style scoped>
.app-shell.translate-entry {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
}
.app-shell.translate-entry > .navigation-bar { flex-shrink: 0; }
.app-shell.translate-entry > .route-shell {
  flex: 1;
  display: flex;
  flex-direction: column;
}

/* ═══ 顶栏 ═══════════════════════════════════════════════ */

.navigation-bar {
  position: sticky;
  top: 0;
  z-index: var(--z-nav);
  width: 100%;
  padding: 8px max(var(--page-gutter), calc((100vw - 1240px) / 2));
  min-height: 53px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-sizing: border-box;
  background: color-mix(in srgb, var(--row-bg) 88%, transparent);
  backdrop-filter: saturate(180%) blur(12px);
  -webkit-backdrop-filter: saturate(180%) blur(12px);
  border-bottom: 1px solid var(--row-border);
}

/* 不支持 backdrop-filter 时退回实色，避免文字叠在内容上 */
@supports not (backdrop-filter: blur(12px)) {
  .navigation-bar { background: var(--row-bg); }
}

.brand-logo {
  width: auto;
  height: 44px;
  gap: 2px;
  padding: 0;
  /* G has 154px transparent inset on its 1254px canvas. Align its visible edge at 32px. */
  margin-inline-start: calc(-32px * 154 / 1254);
  border-radius: 10px;
  background: transparent;
  color: var(--logo-text);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 20px;
  text-decoration: none;
  flex-shrink: 0;
  border: 0;
  transition: color var(--dur-fast) var(--ease-out);
}

.brand-logo:hover { color: var(--logo-text-hover); }

:global(.my-app-dark) .brand-logo {
  --logo-bg: #3a2b3f;
  --logo-text: #f7a3c1;
  --logo-border: #5a3c63;
  --logo-text-hover: #f28fb3;
}

:global(.my-app-light) .brand-logo {
  --logo-bg: #fff3e6;
  --logo-text: #c4517d;
  --logo-border: #e9c9d8;
  --logo-text-hover: #a83c66;
}

/* ═══ 桌面文字菜单 ═══════════════════════════════════════ */

.nav-menu {
  display: flex;
  justify-content: center;
  flex: 1;
  gap: 4px;
  min-width: 0;
}

.nav-menu a {
  position: relative;
  color: var(--muted-color);
  text-decoration: none;
  font-weight: 700;
  font-size: 14px;
  padding: 8px 14px;
  border-radius: var(--radius-md);
  white-space: nowrap;
  transition:
    color var(--dur-fast) var(--ease-out),
    background-color var(--dur-fast) var(--ease-out);
}

.nav-menu a:hover {
  color: var(--text-color);
  background: var(--hover-bg);
}

/* 当前页高亮：颜色 + 下划指示条，不依赖单一颜色通道 */
.nav-menu a.router-link-exact-active {
  color: var(--primary-on-soft);
  background: var(--primary-soft-bg);
}

.nav-menu a.router-link-exact-active::after {
  content: '';
  position: absolute;
  left: 14px;
  right: 14px;
  bottom: 3px;
  height: 2px;
  border-radius: 2px;
  background: var(--primary-color);
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

/* Keep the action width stable when a route has no list view to switch. */
.nav-view-mode {
  display: flex;
  flex: 0 0 32px;
  block-size: 32px;
}


.nav-actions {order:2}
@media(max-width:767px){
  .navigation-bar {background:var(--row-bg);backdrop-filter:none;-webkit-backdrop-filter:none}
  .nav-actions {margin-inline-start:auto;gap:4px}
  .nav-view-mode {flex-basis:auto;height:auto}
  .nav-view-mode:empty {display:none}
  .nav-actions :deep(button){min-width:40px;min-height:44px}
  .brand-logo {min-width:0;flex-shrink:1}
  .nav-menu {display:none;position:fixed;inset:68px var(--page-gutter) auto auto;margin:0;width:min(228px,calc(100vw - 24px));max-height:calc(100dvh - 80px);overflow:auto;padding:8px;border:1px solid var(--row-border);border-radius:14px;background:var(--row-bg);color:var(--text-color);box-shadow:0 8px 28px #14203922}
  .nav-menu.expanded {display:grid;grid-template-columns:minmax(0,1fr)}
  .nav-menu a {display:flex;align-items:center;gap:10px;min-height:46px;box-sizing:border-box;border-radius:8px}
  .menu-settings{display:grid;gap:2px;margin-top:4px;padding-top:6px;border-top:1px solid var(--row-border)}
  .menu-settings :deep(button){display:flex;align-items:center;justify-content:flex-start;width:100%;height:46px;gap:10px;padding:8px 14px;border:0;border-radius:8px;background:transparent;color:var(--text-color);font:inherit;font-size:14px;font-weight:700}
  .menu-settings :deep(button:hover){background:var(--hover-bg);color:var(--text-color)}
  .menu-settings small{margin-inline-start:auto;color:var(--muted-color);font-weight:500}
  .nav-menu a.router-link-exact-active::after {display:none}
}
</style>
