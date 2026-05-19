<!-- web-static/src/components/reader/ScrollView.vue -->
<template>
  <div
    ref="scrollEl"
    class="scroll-view"
    @click="onScrollClick"
  >
    <PageImage
      v-for="pg in pages"
      :key="pg.pageNum"
      :page-num="pg.pageNum"
      :lazy="true"
      class="scroll-page"
      :style="{
        marginBottom: '0px',
        maxWidth: `${settings.widthScale}%`,
      }"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, inject, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { READER_KEY } from '@/composables/useReader'
import PageImage from './PageImage.vue'


const reader = inject(READER_KEY)!
const { pages, currentPage, settings, total, goTo, preload } = reader

const scrollEl = ref<HTMLElement | null>(null)
let scrollObserver: IntersectionObserver | null = null

function setupScrollObserver() {
  scrollObserver?.disconnect()
  if (!scrollEl.value) return
  const pageEls = Array.from(scrollEl.value.querySelectorAll<HTMLElement>('.scroll-page'))

  const visibleRatios = new Map<number, number>()

  scrollObserver = new IntersectionObserver(
    entries => {
      // Update the persistent map with latest ratios
      for (const entry of entries) {
        const pageNum = parseInt((entry.target as HTMLElement).dataset.page ?? '0')
        if (pageNum <= 0) continue
        if (entry.isIntersecting) {
          visibleRatios.set(pageNum, entry.intersectionRatio)
        } else {
          visibleRatios.delete(pageNum)
        }
      }
      // Pick the page with highest ratio across ALL currently visible pages
      let bestPage = 0
      let bestRatio = 0
      for (const [pageNum, ratio] of visibleRatios) {
        if (ratio > bestRatio) { bestRatio = ratio; bestPage = pageNum }
      }
      if (bestPage > 0 && currentPage.value !== bestPage) {
        currentPage.value = bestPage
        preload(bestPage)
      }
    },
    { threshold: [0, 0.25, 0.5, 0.75, 1] }
  )

  pageEls.forEach((el, i) => {
    el.dataset.page = String(pages.value[i]?.pageNum ?? i + 1)
    scrollObserver!.observe(el)
  })
}

onMounted(async () => {
  await nextTick()
  setupScrollObserver()
})
onBeforeUnmount(() => { scrollObserver?.disconnect() })

async function onScrollClick(e: MouseEvent) {
  const ratio = e.clientX / window.innerWidth
  const target = ratio < 0.3
    ? Math.max(1, currentPage.value - 1)
    : ratio > 0.7
      ? Math.min(total.value, currentPage.value + 1)
      : 0
  if (!target) return
  goTo(target)
  await nextTick()
  const pageEls = scrollEl.value?.querySelectorAll<HTMLElement>('.scroll-page')
  if (!pageEls) return
  const idx = pages.value.findIndex(p => p.pageNum === target)
  const el = idx >= 0 ? pageEls[idx] : null
  el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>

<style scoped>
.scroll-view {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  align-items: center;
  background: var(--reader-bg);
  scrollbar-width: thin;
  scrollbar-color: rgba(148,163,184,0.3) transparent;
}
.scroll-page.page-image {
  width: 100%;
  height: auto;
  min-height: 200px;
}
.scroll-page :deep(.pi-img) {
  width: 100%;
  height: auto;
  max-width: 100%;
  max-height: none;
}
.scroll-page {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  min-height: 0;
}
</style>
