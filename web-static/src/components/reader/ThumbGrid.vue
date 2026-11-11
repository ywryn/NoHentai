<!-- web-static/src/components/reader/ThumbGrid.vue -->
<template>
  <div class="tg-overlay" @click.self="$emit('close')">
    <div class="tg-panel" role="dialog" aria-modal="true" aria-label="页目录">
      <div class="tg-header">
        <span class="tg-title">{{ total }} 页</span>
        <form class="tg-jump" @submit.prevent="jump">
          <input ref="jumpInput" v-model="jumpPage" type="number" min="1" :max="total" inputmode="numeric" aria-label="跳转页码" @input="jumpInput?.setCustomValidity('')" />
          <button class="reader-btn" type="submit">跳转</button>
        </form>
        <button class="reader-btn" type="button" aria-label="关闭页目录" @click="$emit('close')">✕</button>
      </div>
      <div class="tg-grid" ref="gridEl">
        <button v-if="windowStart > 0" class="tg-more" type="button" @click="showPrevious">↑ 前 {{ Math.min(WINDOW_SIZE, windowStart) }} 页</button>
        <button
          v-for="pg in visiblePages"
          :key="pg.pageNum"
          class="tg-item"
          :class="{ 'tg-active': pg.pageNum === currentPage }"
          :aria-label="`第 ${pg.pageNum} 页`"
          :aria-current="pg.pageNum === currentPage ? 'page' : undefined"
          @click="onSelect(pg.pageNum)"
        >
          <div class="tg-sprite" :style="spriteStyle(pg)" />
          <span class="tg-num">{{ pg.pageNum }}</span>
        </button>
        <button v-if="windowStart + WINDOW_SIZE < pages.length" class="tg-more" type="button" @click="showNext">↓ 后 {{ Math.min(WINDOW_SIZE, pages.length - windowStart - WINDOW_SIZE) }} 页</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { inject, computed, nextTick, onMounted, ref } from 'vue'
import { READER_KEY } from '@/composables/useReader'
import type { PageInfo } from '@/composables/useReader'

const emit = defineEmits<{ close: [] }>()

const reader = inject(READER_KEY)!
const { pages, currentPage, total, goTo } = reader
const WINDOW_SIZE = 120
const windowStart = ref(Math.max(0, Math.floor((currentPage.value - 1) / WINDOW_SIZE) * WINDOW_SIZE))
const visiblePages = computed(() => pages.value.slice(windowStart.value, windowStart.value + WINDOW_SIZE))
const jumpPage = ref(String(currentPage.value))
const jumpInput = ref<HTMLInputElement | null>(null)
const gridEl = ref<HTMLElement | null>(null)

onMounted(() => {
  jumpInput.value?.focus()
  gridEl.value?.querySelector<HTMLElement>('.tg-active')?.scrollIntoView({ block: 'nearest' })
})

function jump() {
  const page = Number(jumpPage.value)
  if (!Number.isInteger(page) || page < 1 || page > total.value) {
    jumpInput.value?.setCustomValidity(`请输入 1 到 ${total.value} 之间的页码`)
    jumpInput.value?.reportValidity()
    return
  }
  onSelect(page)
}

function changeWindow(start: number) {
  windowStart.value = Math.max(0, Math.min(start, Math.max(0, pages.value.length - 1)))
  nextTick(() => { if (gridEl.value) gridEl.value.scrollTop = 0 })
}
function showPrevious() { changeWindow(windowStart.value - WINDOW_SIZE) }
function showNext() { changeWindow(windowStart.value + WINDOW_SIZE) }

function onSelect(pageNum: number) {
  goTo(pageNum)
  emit('close')
}

const spriteMetaMap = computed(() => {
  const map = new Map<string, { count: number, maxOffset: number }>()
  for (const pg of pages.value) {
    const prev = map.get(pg.thumbSprite) || { count: 0, maxOffset: 0 }
    map.set(pg.thumbSprite, {
      count: prev.count + 1,
      maxOffset: Math.max(prev.maxOffset, -pg.thumbX),
    })
  }
  return map
})

function spriteStyle(pg: PageInfo) {
  const url = pg.thumbSprite.replace(/['"]/g, '')
  const meta = spriteMetaMap.value.get(pg.thumbSprite) || { count: 1, maxOffset: 0 }
  const posX = meta.maxOffset > 0 ? (-pg.thumbX / meta.maxOffset) * 100 : 0
  const targetH = 120
  const w = Math.round((pg.thumbW || 85) * targetH / (pg.thumbH || targetH))
  return {
    backgroundImage: `url(${url})`,
    backgroundSize: `${meta.count * 100}% auto`,
    backgroundPosition: `${posX}% 0`,
    backgroundRepeat: 'no-repeat',
    width: `${w}px`,
    height: `${targetH}px`,
  }
}
</script>

<style scoped>
.tg-overlay {
  position: fixed;
  inset: 0;
  z-index: 300;
  background: var(--reader-overlay);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.tg-panel {
  width: 100%;
  max-height: 75vh;
  background: #111827;
  border-radius: 16px 16px 0 0;
  display: flex;
  flex-direction: column;
}
.tg-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px 8px;
  border-bottom: 1px solid var(--reader-border);
  flex-shrink: 0;
}
.tg-title { font-size: 14px; color: var(--reader-muted); }
.tg-jump { display: flex; align-items: center; gap: 4px; margin-left: auto; }
.tg-jump input { width: 72px; height: 36px; padding: 0 8px; border: 1px solid var(--reader-border); border-radius: 6px; background: var(--reader-surface); color: var(--reader-text); font: inherit; }
.tg-jump input:focus-visible, .tg-item:focus-visible, .tg-more:focus-visible { outline: 2px solid var(--reader-accent); outline-offset: 2px; }

.tg-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px;
  overflow-y: auto;
  justify-content: center;
}
.tg-item {
  border: 2px solid transparent;
  background: var(--reader-surface);
  border-radius: 6px;
  cursor: pointer;
  padding: 4px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  transition: border-color 0.15s;
}
.tg-item:hover { border-color: rgba(96,165,250,0.5); }
.tg-active { border-color: var(--reader-accent) !important; }
.tg-sprite { display: block; border-radius: 3px; }
.tg-num { font-size: 11px; color: var(--reader-muted); }
.tg-more { flex: 0 0 100%; min-height: 44px; border: 0; background: transparent; color: var(--reader-text); font: inherit; cursor: pointer; }
.tg-more:hover { background: var(--reader-surface); }
</style>
