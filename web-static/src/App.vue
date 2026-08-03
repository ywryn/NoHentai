<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useMomMode } from '@/composables/useMomMode'
import ThemeToggle from '@/components/ThemeToggle.vue'
import MomModeToggle from '@/components/MomModeToggle.vue'
import ViewModeToggle from '@/components/ViewModeToggle.vue'

const { initMomMode } = useMomMode()
const route = useRoute()

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
    icon: 'M3 10.5l9-7 9 7V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1v-9.5z',
  },
  {
    to: '/data',
    label: '统计',
    title: 'Data Analys',
    icon: 'M4 19h16v2H4zM6 10h3v7H6zM11 6h3v11h-3zM16 12h3v5h-3z',
  },
  {
    to: '/printed',
    label: '书单',
    title: 'Printed',
    icon: 'M18 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2zM6 4h5v8l-2.5-1.5L6 12V4z',
  },
  {
    to: '/daily',
    label: '每日',
    title: 'Daily Search',
    icon: 'M7 2v2H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2V2h-2v2H9V2H7zm12 8v9H5v-9h14zm-8.5 1.5a3 3 0 1 0 1.79 5.41l1.65 1.65 1.06-1.06-1.65-1.65A3 3 0 0 0 10.5 11.5zm0 1.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3z',
  },
  {
    to: '/translate',
    label: '翻译',
    title: 'Translate',
    icon: 'M12.87 15.07l-2.54-2.51.03-.03A17.52 17.52 0 0 0 14.07 6H17V4h-7V2H8v2H1v2h11.17C11.5 7.92 10.44 9.75 9 11.35 8.07 10.32 7.3 9.19 6.69 8h-2c.73 1.63 1.73 3.17 2.98 4.56l-5.09 5.02L4 19l5-5 3.11 3.11.76-2.04zM18.5 10h-2L12 22h2l1.12-3h4.75L21 22h2l-4.5-12zm-2.62 7l1.62-4.33L19.12 17h-3.24z',
  },
]

onMounted(() => {
  initMomMode()
})
</script>

<template>
  <div class="app-shell" :class="{ 'has-tabbar': !isImmersivePage }">
    <header class="navigation-bar" v-if="!isImmersivePage">
      <RouterLink class="brand-logo" to="/" aria-label="NoHentai 首页">の</RouterLink>

      <nav class="nav-menu" aria-label="主导航">
        <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" :title="item.title">
          {{ item.title }}
        </RouterLink>
      </nav>

      <div class="nav-actions">
        <ViewModeToggle v-if="showViewModeToggle" />
        <MomModeToggle />
        <ThemeToggle />
      </div>
    </header>

    <main class="route-shell">
      <router-view v-slot="{ Component }">
        <Transition name="route-fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </router-view>
    </main>

    <!-- 移动端底部标签栏：常驻可达，触控目标 ≥ 44px -->
    <nav class="tab-bar" v-if="!isImmersivePage" aria-label="主导航">
      <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" class="tab-item">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path :d="item.icon" /></svg>
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>
  </div>
</template>

<style scoped>
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
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--logo-bg);
  color: var(--logo-text);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 20px;
  text-decoration: none;
  flex-shrink: 0;
  border: 1px solid var(--logo-border);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
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
    left: 0;
    right: 0;
    bottom: 0;
    z-index: var(--z-nav);
    display: flex;
    background: color-mix(in srgb, var(--row-bg) 92%, transparent);
    backdrop-filter: saturate(180%) blur(12px);
    -webkit-backdrop-filter: saturate(180%) blur(12px);
    border-top: 1px solid var(--row-border);
    padding-bottom: env(safe-area-inset-bottom, 0px);
  }

  @supports not (backdrop-filter: blur(12px)) {
    .tab-bar { background: var(--row-bg); }
  }

  .tab-item {
    flex: 1;
    min-height: var(--tap-target);
    padding: 7px 2px 6px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    text-decoration: none;
    color: var(--muted-color);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.02em;
    transition: color var(--dur-fast) var(--ease-out);
    -webkit-tap-highlight-color: transparent;
  }

  .tab-item svg {
    width: 21px;
    height: 21px;
    fill: currentColor;
  }

  .tab-item.router-link-exact-active { color: var(--primary-color); }

  /* 顶栏右侧图标按钮在移动端放大到触控标准 */
  .nav-actions :deep(button) {
    width: 40px;
    height: 40px;
  }

  /* 为底栏让出空间，避免最后一行内容被遮挡 */
  .app-shell.has-tabbar .route-shell {
    padding-bottom: calc(var(--tap-target) + 12px + env(safe-area-inset-bottom, 0px));
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
