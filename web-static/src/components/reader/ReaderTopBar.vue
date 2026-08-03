<template>
  <div class="top-bar">
    <button class="tb-back" @click="$emit('back')" title="Back">&#8592;</button>

    <!-- 阅读模式 -->
    <div class="tb-control">
      <span class="tb-label">阅读模式</span>
      <select class="tb-select" :value="settings.readingMode"
        @change="e => updateSetting('readingMode', (e.target as HTMLSelectElement).value as any)">
        <option value="book">书页</option>
        <option value="scroll">滚动</option>
      </select>
    </div>

    <!-- 同屏页数 (书页模式) -->
    <div class="tb-control" v-if="settings.readingMode === 'book'">
      <span class="tb-label">同屏页数</span>
      <select class="tb-select" :value="settings.pagesPerScreen"
        @change="e => updateSetting('pagesPerScreen', parseInt((e.target as HTMLSelectElement).value) as any)">
        <option :value="1">1P</option>
        <option :value="2">2P</option>
      </select>
    </div>

    <!-- 阅读方向 (书页模式) -->
    <div class="tb-control" v-if="settings.readingMode === 'book'">
      <span class="tb-label">阅读方向</span>
      <select class="tb-select" :value="settings.bookDirection"
        @change="e => updateSetting('bookDirection', (e.target as HTMLSelectElement).value as any)">
        <option value="rtl">RTL</option>
        <option value="ltr">LTR</option>
      </select>
    </div>

    <!-- 翻页动画 (书页模式) -->
    <div class="tb-control" v-if="settings.readingMode === 'book'">
      <span class="tb-label">翻页动画</span>
      <select class="tb-select" :value="settings.pageTurnAnimation"
        @change="e => updateSetting('pageTurnAnimation', (e.target as HTMLSelectElement).value as any)">
        <option value="slide">滑动</option>
        <option value="flip">翻页</option>
        <option value="none">无</option>
      </select>
    </div>

    <!-- 缩略图栏 toggle → 左侧缩略图侧边栏 -->
    <div class="tb-toggle-item">
      <span class="tb-label">缩略图栏</span>
      <button class="tb-toggle" :class="{ 'tb-toggle-on': showSidebar }" @click="$emit('toggleSidebar')" />
    </div>

    <!-- 页目录 toggle → 全屏缩略图网格 -->
    <div class="tb-toggle-item">
      <span class="tb-label">页目录</span>
      <button class="tb-toggle" :class="{ 'tb-toggle-on': showThumbGrid }" @click="$emit('toggleThumbGrid')" />
    </div>

    <div class="tb-spacer" />

    <!-- 页码 + 关闭 -->
    <span class="tb-counter">{{ pageCounter }}</span>
    <button class="tb-icon-btn" @click="$emit('back')" title="关闭">✕</button>
  </div>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { READER_KEY } from '@/composables/useReader'

defineProps<{
  showSidebar: boolean
  showThumbGrid: boolean
}>()
defineEmits<{
  back: []
  toggleSidebar: []
  toggleThumbGrid: []
}>()

const reader = inject(READER_KEY)!
const { settings, updateSetting, currentPage, total, effectivePagesPerScreen } = reader

const pageCounter = computed(() => {
  const p = currentPage.value
  const t = total.value
  const step = effectivePagesPerScreen.value
  if (step === 2 && p < t) return `${p}–${p + 1} / ${t}`
  return `${p} / ${t}`
})
</script>

<style scoped>
.top-bar {
  display: flex;
  align-items: center;
  gap: 2px;
  height: 40px;
  padding: 0 8px;
  background: #3a7d44;
  flex-shrink: 0;
  z-index: 10;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
}
.top-bar::-webkit-scrollbar { display: none; }

.tb-back {
  background: none;
  border: none;
  color: #fff;
  font-size: 18px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  flex-shrink: 0;
  line-height: 1;
}
.tb-back:hover { background: rgba(255,255,255,0.15); }

.tb-control {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 6px;
  flex-shrink: 0;
}

.tb-label {
  font-size: 12px;
  color: rgba(255,255,255,0.85);
  white-space: nowrap;
}

.tb-select {
  background: rgba(0,0,0,0.25);
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 3px;
  color: #fff;
  font-size: 12px;
  padding: 2px 4px;
  cursor: pointer;
}
.tb-select:focus-visible {
  outline: 2px solid #fff;
  outline-offset: 1px;
}
.tb-select option { background: #1f2937; color: #fff; }

.tb-toggle-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 0 6px;
  flex-shrink: 0;
}

.tb-toggle {
  position: relative;
  width: 34px;
  height: 18px;
  border-radius: 9px;
  background: rgba(0,0,0,0.35);
  border: none;
  cursor: pointer;
  transition: background 0.2s;
  flex-shrink: 0;
}
.tb-toggle::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: rgba(255,255,255,0.6);
  transition: transform 0.2s, background 0.2s;
}
.tb-toggle-on {
  background: #22c55e;
}
.tb-toggle-on::after {
  transform: translateX(16px);
  background: #fff;
}

.tb-spacer { flex: 1; min-width: 8px; }

.tb-counter {
  font-size: 12px;
  color: rgba(255,255,255,0.85);
  white-space: nowrap;
  padding: 0 8px;
  flex-shrink: 0;
}

.tb-icon-btn {
  background: rgba(0,0,0,0.25);
  border: none;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  flex-shrink: 0;
  line-height: 1;
}
.tb-icon-btn:hover { background: rgba(0,0,0,0.45); }
</style>
