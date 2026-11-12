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
      <AppIcon :name="isDark ? 'sun' : 'moon'" :size="20" />


    </button>
  </div>
</template>

<script setup lang="ts">
import AppIcon from '@/components/ui/AppIcon.vue'
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
