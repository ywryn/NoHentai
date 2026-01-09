<script setup lang="ts">
import { onMounted, computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useMomMode } from '@/composables/useMomMode'
import ThemeToggle from '@/components/ThemeToggle.vue'
import MomModeToggle from '@/components/MomModeToggle.vue'

// 初始化主题和妈妈模式
const { initMomMode } = useMomMode()

// 路由相关
const route = useRoute()

// 移动端菜单状态
const isMobileMenuOpen = ref(false)

// 检测是否为阅读器页面
const isReaderPage = computed(() => {
  return route.path.startsWith('/reader/')
})

// 切换移动端菜单
const toggleMobileMenu = () => {
  isMobileMenuOpen.value = !isMobileMenuOpen.value
}

// 关闭移动端菜单
const closeMobileMenu = () => {
  isMobileMenuOpen.value = false
}

onMounted(() => {
  initMomMode()
})
</script>

<template>

  <!-- Navigation Bar (hidden on reader pages) -->
  <div class="navigation-bar" v-show="!isReaderPage">
    <!-- Desktop Navigation - 静态版本 -->
    <ul class="nav-menu desktop-menu">
      <li><a href="/" @click="closeMobileMenu">Front Page</a></li>
      <li><a href="/data" @click="closeMobileMenu">Data Analys</a></li>
      <li><a href="https://exhentai.org/" target="_blank">ExHentai</a></li>
    </ul>
    
    <!-- Mobile Menu Button -->
    <button class="mobile-menu-btn" @click="toggleMobileMenu">
      <span class="hamburger-line" :class="{ active: isMobileMenuOpen }"></span>
      <span class="hamburger-line" :class="{ active: isMobileMenuOpen }"></span>
      <span class="hamburger-line" :class="{ active: isMobileMenuOpen }"></span>
    </button>
    
    <!-- Theme Toggle (always visible) -->
    <div class="theme-toggle-nav">
      <MomModeToggle />
      <ThemeToggle />
    </div>
    
    <!-- Mobile Menu - 静态版本 -->
    <div class="mobile-menu" :class="{ open: isMobileMenuOpen }">
      <ul class="mobile-nav-menu">
        <li><a href="/" @click="closeMobileMenu">Front Page</a></li>
        <li><a href="/data" @click="closeMobileMenu">Data Analys</a></li>
        <li><a href="https://exhentai.org/" target="_blank" @click="closeMobileMenu">ExHentai</a></li>
      </ul>
    </div>
  </div>
  <router-view></router-view> <!-- 路由出口 -->
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
    max-width: 1300px;
    margin: 0 auto 10px auto;
    padding: 10px 15px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
    box-sizing: border-box;
    position: relative;
    background: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
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
    font-weight: 500;
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
  
  /* Mobile Menu Button */
  .mobile-menu-btn {
    display: none;
    flex-direction: column;
    background: none;
    border: none;
    cursor: pointer;
    padding: 8px;
    z-index: 1001;
  }
  
  .hamburger-line {
    width: 24px;
    height: 3px;
    background-color: var(--text-color);
    margin: 3px 0;
    transition: all 0.3s ease;
    border-radius: 2px;
  }
  
  .hamburger-line.active:nth-child(1) {
    transform: rotate(45deg) translate(6px, 6px);
  }
  
  .hamburger-line.active:nth-child(2) {
    opacity: 0;
  }
  
  .hamburger-line.active:nth-child(3) {
    transform: rotate(-45deg) translate(6px, -6px);
  }
  
  /* Mobile Menu */
  .mobile-menu {
    display: none;
    position: absolute;
    top: 100%;
    left: 0;
    width: 100%;
    height: auto;
    background: var(--surface-color);
    z-index: 1000;
    padding: 8px 0;
    transform: translateY(-8px);
    opacity: 0;
    pointer-events: none;
    transition: transform 0.2s ease, opacity 0.2s ease;
  }
  
  .mobile-menu.open {
    transform: translateY(0);
    opacity: 1;
    pointer-events: auto;
  }
  
  .mobile-nav-menu {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0;
  }
  
  .mobile-nav-menu li {
    border-bottom: 1px solid var(--border-color);
  }
  
  .mobile-nav-menu li:last-child {
    border-bottom: none;
  }
  
  .mobile-nav-menu a {
    color: var(--text-color);
    text-decoration: none;
    font-weight: 500;
    font-size: 18px;
    padding: 20px 24px;
    display: block;
    transition: all 0.3s ease;
  }
  
  .mobile-nav-menu a:hover {
    background: rgba(100, 108, 255, 0.1);
    color: var(--primary-color);
  }

  @media (max-width: 900px) {
    .nav-menu.desktop-menu {
      display: none;
    }

    .mobile-menu-btn {
      display: flex;
    }

    .mobile-menu {
      display: block;
    }

    .navigation-bar {
      gap: 10px;
    }
  }

  @media (max-width: 600px) {
    .navigation-bar {
      padding: 8px 10px;
      border-radius: 6px;
    }

    .mobile-nav-menu a {
      font-size: 16px;
      padding: 16px 18px;
    }
  }


</style>
