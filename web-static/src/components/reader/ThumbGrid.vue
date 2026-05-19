<!-- web-static/src/components/reader/ThumbGrid.vue -->
<template>
  <div class="tg-overlay" @click.self="$emit('close')">
    <div class="tg-panel">
      <div class="tg-header">
        <span class="tg-title">{{ total }} pages</span>
        <button class="reader-btn" @click="$emit('close')">✕</button>
      </div>
      <div class="tg-grid">
        <button
          v-for="pg in pages"
          :key="pg.pageNum"
          class="tg-item"
          :class="{ 'tg-active': pg.pageNum === currentPage }"
          @click="onSelect(pg.pageNum)"
        >
          <div class="tg-sprite" :style="spriteStyle(pg)" />
          <span class="tg-num">{{ pg.pageNum }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { inject, computed } from 'vue'
import { READER_KEY } from '@/composables/useReader'
import type { PageInfo } from '@/composables/useReader'

const emit = defineEmits<{ close: [] }>()

const reader = inject(READER_KEY)!
const { pages, currentPage, total, goTo } = reader

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
</style>
