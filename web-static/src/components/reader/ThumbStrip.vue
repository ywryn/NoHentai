<!-- Left vertical thumbnail sidebar -->
<template>
  <aside id="reader-thumbnails" class="thumb-sidebar" aria-label="阅读缩略图栏">
    <form class="ts-jump" @submit.prevent="jump">
      <label for="reader-jump-page">跳转页码</label>
      <div class="ts-jump-controls">
        <input
          id="reader-jump-page"
          v-model.number="jumpPage"
          name="page"
          type="number"
          required
          min="1"
          :max="total"
          step="1"
          inputmode="numeric"
          enterkeyhint="go"
        />
        <button class="reader-btn" type="submit">跳转</button>
      </div>
    </form>
    <div class="ts-list visible-scrollbar" ref="listEl">
      <button
        v-for="pg in visiblePages"
        :key="pg.pageNum"
        class="ts-item"
        type="button"
        :class="{ 'ts-active': isActive(pg.pageNum) }"
        :aria-label="`第 ${pg.pageNum} 页`"
        :aria-current="pg.pageNum === currentPage ? 'page' : undefined"
        @click="goTo(pg.pageNum)"
      >
        <div class="ts-sprite" :style="spriteStyle(pg)" />
        <span class="ts-num">{{ pg.pageNum }}</span>
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, inject } from 'vue'
import { READER_KEY } from '@/composables/useReader'
import type { PageInfo } from '@/composables/useReader'
import { useReducedMotion } from '@/composables/useReducedMotion'

const reader = inject(READER_KEY)!
const { pages, currentPage, total, settings, effectivePagesPerScreen, goTo } = reader
const listEl = ref<HTMLElement | null>(null)
const jumpPage = ref<number | string>(currentPage.value)
const reducedMotion = useReducedMotion()
const visiblePages = computed(() => {
  const start = Math.max(0, Math.min(currentPage.value - 31, pages.value.length - 80))
  return pages.value.slice(start, start + 80)
})

watch(() => [visiblePages.value[0]?.pageNum, visiblePages.value.at(-1)?.pageNum], ([first, last]) => {
  if (first && last) void reader.loadThumbnails(first, last)
}, { immediate: true })

function isActive(pageNum: number) {
  const cur = currentPage.value
  const step = settings.readingMode === 'book' ? effectivePagesPerScreen.value : 1
  return pageNum >= cur && pageNum < cur + step
}

function jump() {
  const page = Number(jumpPage.value)
  if (Number.isInteger(page) && page >= 1 && page <= total.value) goTo(page)
}

const spriteMetaMap = computed(() => {
  const map = new Map<string, { count: number, maxOffset: number }>()
  for (const pg of pages.value) {
    if (!pg.thumbSprite) continue
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
  return {
    backgroundImage: url ? `url(${url})` : 'none',
    backgroundSize: `${meta.count * 100}% auto`,
    backgroundPosition: `${posX}% 0`,
    backgroundRepeat: 'no-repeat',
    aspectRatio: `${pg.thumbW || 100} / ${pg.thumbH || 142}`,
  }
}

watch(currentPage, async (page, previous) => {
  jumpPage.value = page
  await nextTick()
  listEl.value?.querySelector<HTMLElement>('[aria-current="page"]')?.scrollIntoView({
    behavior: previous === undefined || reducedMotion.value ? 'instant' : 'smooth',
    block: 'nearest',
  })
}, { immediate: true })
</script>

<style scoped>
.thumb-sidebar {
  width: 9rem;
  flex-shrink: 0;
  min-height: 0;
  box-sizing: border-box;
  background: var(--reader-bg);
  border-right: 1px solid var(--reader-border);
  color-scheme: dark;
  --scrollbar-track: var(--reader-bg);
  --scrollbar-thumb: var(--reader-muted);
  display: flex;
  flex-direction: column;
}

.ts-jump {
  padding: 6px;
  border-bottom: 1px solid var(--reader-border);
}

.ts-jump label {
  display: block;
  margin-bottom: 4px;
  color: var(--reader-muted);
  font-size: 12px;
}

.ts-jump-controls {
  display: flex;
  gap: 4px;
}

.ts-jump input, .ts-jump button {
  min-height: 32px;
  border: 1px solid var(--reader-border);
  border-radius: var(--radius-sm);
}

.ts-jump input {
  width: 100%;
  min-width: 0;
  padding: 3px 5px;
  background: var(--reader-surface);
  color: var(--reader-text);
  font: inherit;
  font-variant-numeric: tabular-nums;
}

.ts-jump button { padding-inline: 6px; }

@media (pointer: coarse) {
  .ts-jump input, .ts-jump button { min-height: 48px; }
  .ts-jump input { font-size: max(1rem, 1em); }
}

.ts-list {
  min-height: 0;
  overflow: auto;
  overscroll-behavior: contain;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 6px;
}

.ts-item {
  position: relative;
  border: 2px solid transparent;
  border-radius: var(--radius-sm);
  background: var(--reader-surface);
  padding: 0;
  cursor: pointer;
  flex-shrink: 0;
  overflow: hidden;
  transition: border-color 0.15s;
}
.ts-item:hover {
  border-color: var(--reader-accent);
  border-color: color-mix(in srgb, var(--reader-accent) 45%, transparent);
}
.ts-item.ts-active { border-color: var(--reader-accent); }
.thumb-sidebar :is(button, input):focus-visible {
  outline: 2px solid var(--reader-accent);
  outline-offset: 1px;
}

.ts-sprite { display: block; width: 100%; }

.ts-num {
  position: absolute;
  bottom: 3px;
  right: 4px;
  font-size: 11px;
  color: var(--reader-text);
  background: rgba(16, 19, 18, 0.78);
  font-variant-numeric: tabular-nums;
  border-radius: 2px;
  padding: 0 3px;
  line-height: 1.4;
  pointer-events: none;
}
.ts-active .ts-num { background: var(--reader-accent); color: var(--reader-bg); }
</style>
