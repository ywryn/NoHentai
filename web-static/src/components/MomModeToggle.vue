<template>
  <div class="mom-mode-toggle">
    <button
      @click="toggleMomMode"
      class="mom-mode-btn"
      :class="{ 'active': isMomMode }"
      :aria-pressed="isMomMode"
      :aria-label="`${getMomModeLabel()}（${isMomMode ? '已开启' : '已关闭'}）`"
      :title="isMomMode ? '妈妈模式已开启 · 悬停或长按可临时查看' : '开启妈妈模式（图片模糊遮蔽）'"
    >
      <!-- 关闭状态：眼睛图标 -->
      <svg 
        v-if="!isMomMode"
        xmlns="http://www.w3.org/2000/svg" 
        width="20" 
        height="20" 
        viewBox="0 0 24 24" 
        fill="none" 
        stroke="currentColor" 
        stroke-width="2" 
        stroke-linecap="round" 
        stroke-linejoin="round" 
        class="eye-icon"
      >
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
        <circle cx="12" cy="12" r="3"/>
      </svg>
      
      <!-- 开启状态：眼睛关闭图标 -->
      <svg 
        v-if="isMomMode"
        xmlns="http://www.w3.org/2000/svg" 
        width="20" 
        height="20" 
        viewBox="0 0 24 24" 
        fill="none" 
        stroke="currentColor" 
        stroke-width="2" 
        stroke-linecap="round" 
        stroke-linejoin="round" 
        class="eye-off-icon"
      >
        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
        <line x1="1" y1="1" x2="23" y2="23"/>
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import { useMomMode } from '@/composables/useMomMode'

const { isMomMode, toggleMomMode, getMomModeLabel } = useMomMode()
</script>

<style scoped>
.mom-mode-toggle {
  display: inline-block;
}

.mom-mode-btn {
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

.mom-mode-btn:hover {
  background: var(--bg-color);
  border-color: #ff6b9d;
  box-shadow: none;
}

.mom-mode-btn:hover svg {
  color: #ff6b9d;
}

/* 激活状态时的特殊样式 */
.mom-mode-btn.active {
  background: #4caf50;
  border-color: #4caf50;
  color: white;
  box-shadow: none;
}

.mom-mode-btn.active:hover {
  background: #45a049;
  border-color: #45a049;
  box-shadow: none;
}

.mom-mode-btn.active svg {
  color: white;
}

.eye-icon,
.eye-off-icon {
  width: 20px;
  height: 20px;
  transition: all 0.2s ease;
}

/* 已取消响应式设计 */
</style>