<template>
  <div class="theme-toggle">
    <button
      id="theme-btn"
      @click="toggleTheme"
      class="theme-btn"
      :class="{ 'dark': isDark }"
      :aria-label="isDark ? '当前深色主题，点击切换为浅色' : '当前浅色主题，点击切换为深色'"
      title="切换明暗主题"
    >
      <svg 
        v-if="!isDark"
        xmlns="http://www.w3.org/2000/svg" 
        width="20" 
        height="20" 
        viewBox="0 0 24 24" 
        fill="none" 
        stroke="currentColor" 
        stroke-width="2" 
        stroke-linecap="round" 
        stroke-linejoin="round" 
        class="moon-icon"
      >
        <path d="M12 3c.132 0 .263 0 .393 0a7.5 7.5 0 0 0 7.92 12.446a9 9 0 1 1 -8.313 -12.454z" />
      </svg>
      
      <svg 
        v-if="isDark"
        xmlns="http://www.w3.org/2000/svg" 
        width="20" 
        height="20" 
        viewBox="0 0 24 24" 
        fill="none" 
        stroke="currentColor" 
        stroke-width="2" 
        stroke-linecap="round" 
        stroke-linejoin="round" 
        class="sun-icon"
      >
        <path d="M14.828 14.828a4 4 0 1 0 -5.656 -5.656a4 4 0 0 0 5.656 5.656z" />
        <path d="M6.343 17.657l-1.414 1.414" />
        <path d="M6.343 6.343l-1.414 -1.414" />
        <path d="M17.657 6.343l1.414 -1.414" />
        <path d="M17.657 17.657l1.414 1.414" />
        <path d="M4 12h-2" />
        <path d="M12 4v-2" />
        <path d="M20 12h2" />
        <path d="M12 20v2" />
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import { useTheme } from '@/composables/useTheme'

const { isDark, toggleTheme } = useTheme()
</script>

<style scoped>
.theme-toggle {
  display: inline-block;
}

.theme-btn {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 6px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--surface-color);
  color: var(--text-color);
  cursor: pointer;
  transition:
    background-color var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.theme-btn:hover {
  background: var(--bg-color);
  border-color: var(--primary-color);
}

.theme-btn:hover svg {
  color: var(--primary-color);
}

.moon-icon,
.sun-icon {
  width: 20px;
  height: 20px;
}

/* 已取消响应式设计 */
</style>