<template>
  <button
    class="view-mode-btn"
    :aria-label="viewMode === 'card' ? '切换为封面视图' : '切换为列表视图'"
    :title="viewMode === 'card' ? '切换为封面视图' : '切换为列表视图'"
    @click="toggleViewMode"
  >
    <AppIcon :name="viewMode === 'card' ? 'grid' : 'list'" :size="20" />

  </button>
</template>

<script setup lang="ts">
import AppIcon from '@/components/ui/AppIcon.vue'
import { useViewMode } from '@/composables/useViewMode'
const { viewMode, toggleViewMode } = useViewMode()
</script>

<style scoped>
.view-mode-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--surface-color);
  color: var(--text-color);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: color var(--dur-fast) var(--ease-out), border-color var(--dur-fast) var(--ease-out);
}
.view-mode-btn:hover {
  color: var(--primary-color);
  border-color: var(--primary-color);
  background: var(--surface-color);
}
.view-mode-btn svg {
  width: 16px;
  height: 16px;
  fill: none;
}
</style>
