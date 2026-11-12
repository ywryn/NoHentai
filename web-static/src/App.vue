<script setup lang="ts">
import BrandMark from '@/components/ui/BrandMark.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import { onMounted, computed } from 'vue'
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
  ['/', '/printed', '/daily'].includes(route.path)
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
  {
    to: '/translate',
    label: '翻译',
    title: 'Translate',
    icon: 'translate',
  },
]

onMounted(() => {
  initMomMode()
})
</script>

<template>
  <div class="app-shell" :class="{ 'has-tabbar': !isImmersivePage }">
    <a v-if="!isImmersivePage" class="skip-link" href="#main-content" @click.prevent="focusContent">跳至内容</a>
    <header class="navigation-bar" v-if="!isImmersivePage">
      <RouterLink class="brand-logo" to="/" aria-label="NoHentai 首页"><BrandMark :size="40" /><span class="brand-name">NoHentai</span></RouterLink>

      <nav class="nav-menu" aria-label="主导航">
        <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" :title="item.title">
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="nav-actions">
        <ViewModeToggle v-if="showViewModeToggle" />
        <MomModeToggle />
        <ThemeToggle />
      </div>
    </header>

    <main id="main-content" class="route-shell" tabindex="-1">
      <router-view v-slot="{ Component }">
        <Transition name="route-fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </router-view>
    </main>

    <!-- 移动端底部标签栏：常驻可达，触控目标 ≥ 44px -->
    <nav class="tab-bar" v-if="!isImmersivePage" aria-label="主导航">
      <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" class="tab-item">
        <span class="tab-icon"><AppIcon :name="item.icon" :size="21" /></span>
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>
  </div>
</template>

<style scoped>
 .brand-name { font-size: 16px; letter-spacing: -.04em; color: var(--text-color); }
.navigation-bar { padding-inline: max(20px, calc((100vw - 1280px) / 2)) !important; }
/* ═══ 顶栏 ═══════════════════════════════════════════════ */

.navigation-bar {
  position: sticky;
  top: 0;
  z-index: var(--z-nav);
  width: 100%;
  padding: 8px 16px;
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
  gap: 10px;
  padding: 0 10px;
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

/* ═══ 移动端底部标签栏 ═══════════════════════════════════ */

.tab-bar { display: none; }

@media (max-width: 767px) {
  .nav-menu { display: none; }

  .navigation-bar {
    padding: 8px 12px;
    justify-content: space-between;
  }

  .tab-bar {
    position: fixed;
    left: 50%;
    bottom: calc(10px + env(safe-area-inset-bottom, 0px));
    transform: translateX(-50%);
    width: calc(100% - 24px);
    max-width: 460px;
    box-sizing: border-box;
    z-index: var(--z-nav);
    display: flex;
    gap: 4px;
    padding: 5px;
    background: color-mix(in srgb, var(--row-bg) 96%, transparent);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--row-border);
    border-radius: 20px;
    box-shadow: 0 6px 28px #14203912, 0 1px 3px #14203906;
  }
  @supports not (backdrop-filter: blur(16px)) {
    .tab-bar { background: var(--row-bg); }
  }
  .tab-item {
    flex: 1;
    min-width: 0;
    min-height: 54px;
    padding: 4px 2px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    border-radius: 14px;
    text-decoration: none;
    color: var(--muted-color);
    font-size: 10px;
    font-weight: 500;
    transition: color .18s, background .18s;
    -webkit-tap-highlight-color: transparent;
  }
  .tab-icon { display: grid; place-items: center; width: 34px; height: 27px; border-radius: 9px; }
  .tab-item svg { width: 21px; height: 21px; fill: none; stroke: currentColor; stroke-width: 1.65; stroke-linecap: round; stroke-linejoin: round; }
  .tab-item.router-link-exact-active { color: var(--primary-color); background: var(--primary-soft-bg); font-weight: 650; }
  .tab-item:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 1px; }
  /* 顶栏右侧图标按钮在移动端放大到触控标准 */
  .nav-actions :deep(button) {
    width: 40px;
    height: 40px;
  }

  /* 为底栏让出空间，避免最后一行内容被遮挡 */
  .app-shell.has-tabbar .route-shell {
    padding-bottom: calc(92px + env(safe-area-inset-bottom, 0px));
  }
}

/* ═══ 路由过渡 ═══════════════════════════════════════════ */

.route-fade-enter-active,
.route-fade-leave-active {
  transition: opacity var(--dur-base) var(--ease-out);
}

.route-fade-enter-from,
.route-fade-leave-to {
  opacity: 0;
}
</style>
