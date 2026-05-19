<!-- Left vertical thumbnail sidebar -->
<template>
  <div class="thumb-sidebar" ref="sidebarEl">
    <button
      v-for="pg in pages"
      :key="pg.pageNum"
      class="ts-item"
      :class="{ 'ts-active': isActive(pg.pageNum) }"
      @click="goTo(pg.pageNum)"
    >
      <div class="ts-sprite" :style="spriteStyle(pg)" />
      <span class="ts-num">{{ pg.pageNum }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, inject } from 'vue'
import { READER_KEY } from '@/composables/useReader'
import type { PageInfo } from '@/composables/useReader'

const reader = inject(READER_KEY)!
const { pages, currentPage, effectivePagesPerScreen, goTo } = reader
const sidebarEl = ref<HTMLElement | null>(null)

function isActive(pageNum: number) {
  const cur = currentPage.value
  const step = effectivePagesPerScreen.value
  return pageNum >= cur && pageNum < cur + step
}

const SIDEBAR_W = 130

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
  const h = pg.thumbW > 0 ? Math.round(SIDEBAR_W * (pg.thumbH || pg.thumbW) / pg.thumbW) : SIDEBAR_W
  return {
    backgroundImage: url ? `url(${url})` : 'none',
    backgroundSize: `${meta.count * 100}% auto`,
    backgroundPosition: `${posX}% 0`,
    backgroundRepeat: 'no-repeat',
    width: `${SIDEBAR_W}px`,
    height: `${h}px`,
  }
}

watch(currentPage, async () => {
  await nextTick()
  sidebarEl.value?.querySelector<HTMLElement>('.ts-active')?.scrollIntoView({
    behavior: 'smooth',
    block: 'nearest',
  })
})
</script>

<style scoped>
.thumb-sidebar {
  width: 130px;
  flex-shrink: 0;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  background: #111827;
  scrollbar-width: thin;
  scrollbar-color: #374151 transparent;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 2px;
}
.thumb-sidebar::-webkit-scrollbar { width: 4px; }
.thumb-sidebar::-webkit-scrollbar-track { background: transparent; }
.thumb-sidebar::-webkit-scrollbar-thumb { background: #374151; border-radius: 2px; }

.ts-item {
  position: relative;
  border: 2px solid transparent;
  border-radius: 3px;
  background: transparent;
  padding: 0;
  cursor: pointer;
  flex-shrink: 0;
  overflow: hidden;
  transition: border-color 0.15s;
}
.ts-item:hover { border-color: rgba(96,165,250,0.5); }
.ts-active { border-color: #22c55e !important; }

.ts-sprite { display: block; }

.ts-num {
  position: absolute;
  bottom: 3px;
  right: 4px;
  font-size: 11px;
  color: #fff;
  background: rgba(0,0,0,0.55);
  border-radius: 2px;
  padding: 0 3px;
  line-height: 1.4;
  pointer-events: none;
}
</style>
