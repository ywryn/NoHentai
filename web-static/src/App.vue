<script setup lang="ts">
import { onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useMomMode } from '@/composables/useMomMode'
import ThemeToggle from '@/components/ThemeToggle.vue'
import MomModeToggle from '@/components/MomModeToggle.vue'
import ViewModeToggle from '@/components/ViewModeToggle.vue'

// 初始化主题和妈妈模式
const { initMomMode } = useMomMode()

// 路由相关
const route = useRoute()

// 检测是否为阅读器页面
const isReaderPage = computed(() => {
  return route.path.startsWith('/reader/') || route.path.endsWith('/read') || route.path.endsWith('/translate')
})

const shouldLockPageScroll = computed(() => false)

function applyPageScrollLock(locked: boolean) {
  const root = document.documentElement
  const body = document.body
  root.classList.toggle('home-scroll-locked', locked)
  body.classList.toggle('home-scroll-locked', locked)
}

watch(shouldLockPageScroll, (locked) => {
  applyPageScrollLock(locked)
}, { immediate: true })

onMounted(() => {
  initMomMode()
})

onBeforeUnmount(() => {
  applyPageScrollLock(false)
})
</script>

<template>

  <div class="app-shell">
    <!-- Navigation Bar (hidden on reader pages) -->
    <div class="navigation-bar" v-show="!isReaderPage">
      <div class="nav-left">
        <RouterLink class="brand-logo" to="/" aria-label="NoHentai">
          の
        </RouterLink>
        <ul class="icon-nav">
          <li>
            <RouterLink to="/" aria-label="Ex Home" title="Ex Home">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M3 10.5l9-7 9 7V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1v-9.5z" />
              </svg>
            </RouterLink>
          </li>
          <li>
            <RouterLink to="/data" aria-label="Data Analys" title="Data Analys">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 19h16v2H4zM6 10h3v7H6zM11 6h3v11h-3zM16 12h3v5h-3z" />
              </svg>
            </RouterLink>
          </li>
          <li>
            <RouterLink to="/printed" aria-label="Printed" title="Printed">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M18 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2zM6 4h5v8l-2.5-1.5L6 12V4z" />
              </svg>
            </RouterLink>
          </li>
          <li>
            <RouterLink to="/daily" aria-label="Daily Search" title="Daily Search">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm1 14.93V15a1 1 0 0 0-2 0v2.93A8 8 0 0 1 4.07 11H6a1 1 0 0 0 0-2H4.07A8 8 0 0 1 11 4.07V6a1 1 0 0 0 2 0V4.07A8 8 0 0 1 19.93 11H18a1 1 0 0 0 0 2h1.93A8 8 0 0 1 13 16.93zM12 10a2 2 0 1 0 2 2 2 2 0 0 0-2-2z"/>
              </svg>
            </RouterLink>
          </li>
          <!-- Telegram 暂时关闭
          <li>
            <RouterLink to="/telegram" aria-label="Telegram Feed" title="Telegram Feed">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8-1.7 8.02c-.12.57-.46.71-.93.44l-2.58-1.9-1.24 1.19c-.14.14-.26.26-.52.26l.19-2.64 4.83-4.36c.21-.19-.05-.29-.32-.1L7.9 14.46l-2.55-.8c-.55-.17-.56-.55.12-.82l9.96-3.84c.46-.17.86.11.71.8z"/>
              </svg>
            </RouterLink>
          </li>
          -->
        </ul>
      </div>
      <!-- Desktop Navigation - 静态版本 -->
      <ul class="nav-menu desktop-menu">
        <li><RouterLink to="/">Ex Home</RouterLink></li>
        <li><RouterLink to="/data">Data Analys</RouterLink></li>
        <li><RouterLink to="/printed">Printed</RouterLink></li>
        <li><RouterLink to="/daily">Daily</RouterLink></li>
        <!-- <li><RouterLink to="/telegram">Telegram</RouterLink></li> -->
      </ul>
      
      <!-- Theme Toggle (always visible) -->
      <div class="theme-toggle-nav">
        <ViewModeToggle />
        <MomModeToggle />
        <ThemeToggle />
      </div>
    </div>
    <div class="route-shell">
      <router-view></router-view> <!-- 路由出口 -->
    </div>
  </div>
</template>

<style scoped>
.logo {
  height: 6em;
  padding: 1.5em;
  will-change: filter;
  transition: filter 300ms;
}
.logo:hover {
  filter: drop-shadow(0 0 2em #646cffaa);
}
.logo.vue:hover {
  filter: drop-shadow(0 0 2em #42b883aa);
}


  /* Navigation Bar Styles */
  .navigation-bar {
    width: 100%;
    margin: 0;
    padding: 8px 16px;
    min-height: var(--app-nav-height, 53px);
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-sizing: border-box;
    position: relative;
    background: var(--row-bg, #131f2e);
    border-bottom: 1px solid var(--row-border, #1e293b);
    gap: 10px;
  }

  .nav-left {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
  }

  .icon-nav {
    list-style: none;
    margin: 0;
    padding: 0;
    display: none;
    align-items: center;
    gap: 10px;
  }

  .icon-nav a {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: var(--text-color);
    background: var(--surface-color);
    transition: all 0.2s ease;
  }

  .icon-nav a:hover {
    color: var(--primary-color);
    border-color: var(--primary-color);
  }

  .icon-nav svg {
    width: 18px;
    height: 18px;
    fill: currentColor;
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
  }

  .brand-logo:hover {
    color: var(--logo-text-hover);
  }

  :global(.my-app-dark) .brand-logo {
    --logo-bg: #3a2b3f;
    --logo-text: #f7a3c1;
    --logo-border: #5a3c63;
    --logo-text-hover: #f28fb3;
  }

  :global(.my-app-light) .brand-logo {
    --logo-bg: #fff3e6;
    --logo-text: #e57aa7;
    --logo-border: #e9c9d8;
    --logo-text-hover: #d86a97;
  }

  .nav-menu {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    justify-content: center;
    flex: 1;
    gap: 10px;
  }
  
  .theme-toggle-nav {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }
  
  .nav-menu li {
    margin: 0;
    white-space: nowrap;
  }
  
  .nav-menu a {
    color: var(--text-color);
    text-decoration: none;
    font-weight: 900;
    font-size: 14px;
    transition: all 0.3s ease;
    padding: 8px 16px;
    border-radius: 8px;
    display: block;
    position: relative;
  }
  
  .nav-menu a:hover {
    color: var(--primary-color);
    background: rgba(100, 108, 255, 0.1);
    transform: translateY(-1px);
    text-decoration: none;
  }
  
  /* 添加分割线，除了最后一个按钮 */
  .nav-menu li:not(:last-child) a::after {
    content: '';
    position: absolute;
    right: -5px;
    top: 50%;
    transform: translateY(-50%);
    width: 1px;
    height: 60%;
    background: var(--border-color);
  }

  @media (max-width: 900px) {
    .nav-menu.desktop-menu {
      display: none;
    }

    .icon-nav {
      display: flex;
    }

    .navigation-bar {
      gap: 10px;
    }
  }

  @media (max-width: 600px) {
    .navigation-bar {
      padding: 8px 10px;
    }

    .icon-nav a {
      width: 30px;
      height: 30px;
    }
  }


</style>
