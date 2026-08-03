<template>
  <div class="top-bar-shell">
    <div class="top-bar">
      <button class="tb-icon-btn tb-back" type="button" title="返回" aria-label="返回" @click="$emit('back')">←</button>

      <span class="tb-counter">{{ pageCounter }}</span>

      <div class="tb-spacer" />

      <!-- 宽屏内联展开的设置项；窄屏收进下方面板 -->
      <div class="tb-controls" :class="{ 'is-open': settingsOpen }">
        <div class="tb-control">
          <span class="tb-label">阅读模式</span>
          <select class="tb-select" :value="settings.readingMode"
            @change="e => updateSetting('readingMode', (e.target as HTMLSelectElement).value as any)">
            <option value="book">书页</option>
            <option value="scroll">滚动</option>
          </select>
        </div>

        <template v-if="settings.readingMode === 'book'">
          <div class="tb-control">
            <span class="tb-label">同屏页数</span>
            <select class="tb-select" :value="settings.pagesPerScreen"
              @change="e => updateSetting('pagesPerScreen', parseInt((e.target as HTMLSelectElement).value) as any)">
              <option :value="1">1P</option>
              <option :value="2">2P</option>
            </select>
          </div>

          <div class="tb-control">
            <span class="tb-label">阅读方向</span>
            <select class="tb-select" :value="settings.bookDirection"
              @change="e => updateSetting('bookDirection', (e.target as HTMLSelectElement).value as any)">
              <option value="rtl">从右到左</option>
              <option value="ltr">从左到右</option>
            </select>
          </div>

          <div class="tb-control">
            <span class="tb-label">翻页动画</span>
            <select class="tb-select" :value="settings.pageTurnAnimation"
              @change="e => updateSetting('pageTurnAnimation', (e.target as HTMLSelectElement).value as any)">
              <option value="slide">滑动</option>
              <option value="flip">翻页</option>
              <option value="none">无</option>
            </select>
          </div>
        </template>

        <div class="tb-toggle-item">
          <span class="tb-label">缩略图栏</span>
          <button
            class="tb-toggle"
            type="button"
            role="switch"
            :aria-checked="showSidebar"
            aria-label="缩略图栏"
            :class="{ 'tb-toggle-on': showSidebar }"
            @click="$emit('toggleSidebar')"
          />
        </div>
      </div>

      <button
        class="tb-icon-btn tb-settings"
        type="button"
        :aria-expanded="settingsOpen"
        aria-label="阅读设置"
        title="阅读设置"
        @click="settingsOpen = !settingsOpen"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
          <path d="M19.4 13a7.8 7.8 0 0 0 0-2l2-1.6-2-3.4-2.4 1a7.6 7.6 0 0 0-1.7-1L15 3.3H11l-.3 2.6a7.6 7.6 0 0 0-1.7 1l-2.4-1-2 3.4L6.6 11a7.8 7.8 0 0 0 0 2l-2 1.6 2 3.4 2.4-1c.5.4 1.1.8 1.7 1l.3 2.6h4l.3-2.6c.6-.2 1.2-.6 1.7-1l2.4 1 2-3.4-2-1.6zM13 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7z" />
        </svg>
      </button>

      <button
        class="tb-icon-btn"
        type="button"
        :aria-pressed="showThumbGrid"
        aria-label="页目录"
        title="页目录（F）"
        @click="$emit('toggleThumbGrid')"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
          <path d="M3 3h8v8H3V3zm0 10h8v8H3v-8zm10-10h8v8h-8V3zm0 10h8v8h-8v-8z" />
        </svg>
      </button>

      <button class="tb-icon-btn" type="button" title="关闭" aria-label="关闭阅读器" @click="$emit('back')">✕</button>
    </div>

    <!-- 阅读进度：3998 页的画廊只有文字计数时缺少空间感 -->
    <div class="tb-progress" role="presentation">
      <div class="tb-progress-fill" :style="{ width: `${progress}%` }"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, inject } from 'vue'
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

/** 窄屏时设置项收进折叠面板，此前 4 个 select + 2 个开关挤在 40px 单行里
    靠隐藏滚动条的横向滚动容纳，移动端有内容在屏幕外且毫无提示 */
const settingsOpen = ref(false)

const pageCounter = computed(() => {
  const p = currentPage.value
  const t = total.value
  if (effectivePagesPerScreen.value === 2 && p < t) return `${p}–${p + 1} / ${t}`
  return `${p} / ${t}`
})

const progress = computed(() => (total.value ? (currentPage.value / total.value) * 100 : 0))
</script>

<style scoped>
.top-bar-shell {
  flex-shrink: 0;
  z-index: 10;
  background: rgba(15, 23, 42, 0.92);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--reader-border);
}

.top-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  min-height: 44px;
  padding: 0 6px;
  color: var(--reader-text);
}

.tb-counter {
  font-size: 12px;
  color: var(--reader-muted);
  white-space: nowrap;
  padding: 0 6px;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.tb-spacer { flex: 1; min-width: 4px; }

.tb-controls {
  display: flex;
  align-items: center;
  gap: 2px;
  min-width: 0;
}

.tb-control,
.tb-toggle-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 0 6px;
  flex-shrink: 0;
}

.tb-label {
  font-size: 12px;
  color: var(--reader-muted);
  white-space: nowrap;
}

.tb-select {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid var(--reader-border);
  border-radius: var(--radius-sm);
  color: var(--reader-text);
  font-size: 12px;
  padding: 3px 5px;
  cursor: pointer;
}
.tb-select option { background: #1f2937; color: #fff; }
.tb-select:focus-visible {
  outline: 2px solid var(--reader-accent);
  outline-offset: 1px;
}

.tb-toggle {
  position: relative;
  width: 34px;
  height: 18px;
  padding: 0;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.14);
  border: none;
  cursor: pointer;
  transition: background-color var(--dur-fast) var(--ease-out);
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
  background: rgba(255, 255, 255, 0.7);
  transition: transform var(--dur-fast) var(--ease-out);
}
.tb-toggle-on { background: var(--reader-accent); }
.tb-toggle-on::after { transform: translateX(16px); background: #fff; }
.tb-toggle:hover { background: rgba(255, 255, 255, 0.22); }
.tb-toggle-on:hover { background: var(--reader-accent); }

.tb-icon-btn {
  width: 36px;
  height: 36px;
  padding: 0;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--reader-text);
  font-size: 15px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}

.tb-icon-btn svg { width: 18px; height: 18px; }

.tb-icon-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  color: var(--reader-text);
}

.tb-back { font-size: 18px; }

/* 宽屏设置项常驻，齿轮按钮无用 */
.tb-settings { display: none; }

.tb-progress {
  height: 2px;
  background: rgba(255, 255, 255, 0.08);
}

.tb-progress-fill {
  height: 100%;
  background: var(--reader-accent);
  transition: width var(--dur-base) var(--ease-out);
}

/* ── 窄屏：设置收进折叠面板，触控目标放大到 44px ── */
@media (max-width: 767px) {
  .tb-settings { display: flex; }

  .tb-icon-btn {
    width: var(--tap-target);
    height: var(--tap-target);
  }

  .tb-controls {
    display: none;
    position: absolute;
    left: 0;
    right: 0;
    top: 100%;
    flex-direction: column;
    align-items: stretch;
    gap: 0;
    padding: 6px 10px;
    background: rgba(15, 23, 42, 0.97);
    border-bottom: 1px solid var(--reader-border);
  }

  .tb-controls.is-open { display: flex; }

  .tb-control,
  .tb-toggle-item {
    justify-content: space-between;
    min-height: var(--tap-target);
    padding: 0 2px;
  }

  .tb-select {
    font-size: 14px;
    padding: 8px 10px;
    min-width: 116px;
  }

  .top-bar { position: relative; }
}
</style>
