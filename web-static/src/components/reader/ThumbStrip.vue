<!-- web-static/src/components/reader/ThumbStrip.vue -->
<template>
  <div class="thumb-strip" :class="{ 'strip-hidden': !barVisible }" ref="stripEl">
    <button
      v-for="pg in pages"
      :key="pg.pageNum"
      class="thumb-item"
      :class="{ 'thumb-active': pg.pageNum === currentPage }"
      @click="goTo(pg.pageNum)"
    >
      <div class="thumb-sprite" :style="spriteStyle(pg)" />
      <span class="thumb-num">{{ pg.pageNum }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, inject } from 'vue'
import { READER_KEY } from '@/composables/useReader'
import type { PageInfo } from '@/composables/useReader'

defineProps<{ barVisible: boolean }>()

const reader = inject(READER_KEY)!
const { pages, currentPage, goTo } = reader
const stripEl = ref<HTMLElement | null>(null)

function spriteStyle(pg: PageInfo) {
  const url = pg.thumbSprite.replace(/['"]/g, '')
  const scale = 60 / (pg.thumbH || 60)
  return {
    backgroundImage: `url(${url})`,
    backgroundPosition: `${pg.thumbX * scale}px 0`,
    backgroundRepeat: 'no-repeat',
    backgroundSize: `auto 60px`,
    width:  `${(pg.thumbW || 42) * scale}px`,
    height: '60px',
    flexShrink: '0',
  }
}

watch(currentPage, async () => {
  await nextTick()
  stripEl.value?.querySelector<HTMLElement>('.thumb-active')?.scrollIntoView({
    behavior: 'smooth',
    block: 'nearest',
    inline: 'center',
  })
})
</script>

<style scoped>
.thumb-strip {
  display: flex;
  flex-direction: row;
  align-items: center;
  height: var(--reader-strip-h);
  background: linear-gradient(to top, rgba(0,0,0,0.85), transparent);
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
  flex-shrink: 0;
  transition: opacity 0.3s;
  gap: 4px;
  padding: 0 8px;
}
.thumb-strip::-webkit-scrollbar { display: none; }
.strip-hidden { opacity: 0; pointer-events: none; }

.thumb-item {
  border: none;
  background: transparent;
  padding: 2px;
  cursor: pointer;
  border-radius: 3px;
  border: 2px solid transparent;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  transition: border-color 0.15s;
}
.thumb-item:hover { border-color: rgba(96,165,250,0.5); }
.thumb-active { border-color: var(--reader-accent) !important; }

.thumb-sprite { display: block; }

.thumb-num {
  font-size: 10px;
  color: var(--reader-muted);
  line-height: 1;
}
</style>
