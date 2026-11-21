<template>
  <div class="theme-toggle">
    <button
      id="theme-btn"
      @click="toggleTheme"
      class="theme-btn toolbar-icon-button"
      :class="{ 'dark': isDark }"
      :aria-label="isDark ? '当前深色主题，点击切换为浅色' : '当前浅色主题，点击切换为深色'"
      title="切换明暗主题"
    >
      <AppIcon :name="isDark ? 'sun' : 'moon'" :size="20" />


      <slot :state="isDark ? '深色' : '浅色'" />
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

.moon-icon,
.sun-icon {
  width: 20px;
  height: 20px;
}

/* 已取消响应式设计 */
</style>
