<template>
  <button
    class="view-mode-btn"
    :title="viewMode === 'card' ? '切换为封面视图' : '切换为列表视图'"
    @click="toggleViewMode"
  >
    <!-- Grid icon — shown in card mode, click to switch to cover -->
    <svg v-if="viewMode === 'card'" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 3h8v8H3V3zm0 10h8v8H3v-8zm10-10h8v8h-8V3zm0 10h8v8h-8v-8z"/>
    </svg>
    <!-- List icon — shown in cover mode, click to switch to card -->
    <svg v-else viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 5h18v2H3V5zm0 6h18v2H3v-2zm0 6h18v2H3v-2z"/>
    </svg>
  </button>
</template>

<script setup lang="ts">
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
  transition: color 0.2s, border-color 0.2s;
}
.view-mode-btn:hover {
  color: var(--primary-color);
  border-color: var(--primary-color);
  background: var(--surface-color);
}
.view-mode-btn svg {
  width: 16px;
  height: 16px;
  fill: currentColor;
}
</style>
