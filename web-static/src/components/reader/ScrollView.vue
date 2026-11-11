<!-- web-static/src/components/reader/ScrollView.vue -->
<template>
  <div
    ref="scrollEl"
    class="scroll-view"
    @pointerup="onTapEnd"
    @pointercancel="tapStart = null"
    @wheel.passive="releaseAnchor"
    @touchstart.passive="releaseAnchor"
    @pointerdown="onTapStart"
  >
    <button v-if="hasPrevious" class="scroll-segment-button" type="button" @click="moveSegment(-1)">← 第 {{ pages[segmentStart - SEGMENT_SIZE].pageNum }}–{{ pages[segmentStart - 1].pageNum }} 页</button>
    <PageImage
      v-for="pg in renderedPages"
      :key="pg.pageNum"
      :page-num="pg.pageNum"
      :lazy="true"
      class="scroll-page"
      :style="{
        marginBottom: `${settings.scrollPageMargin}px`,
        maxWidth: `${settings.widthScale}%`,
      }"
    />
    <button v-if="hasNext" class="scroll-segment-button" type="button" @click="moveSegment(1)">第 {{ pages[segmentStart + SEGMENT_SIZE].pageNum }}–{{ pages[Math.min(segmentStart + SEGMENT_SIZE * 2, pages.length) - 1].pageNum }} 页 →</button>
  </div>
</template>

<script setup lang="ts">
import { ref, inject, onMounted, onBeforeUnmount, nextTick, watch, computed } from 'vue'
import { READER_KEY } from '@/composables/useReader'
import PageImage from './PageImage.vue'


const emit = defineEmits(['surface-click'])
let tapStart: { x: number; y: number } | null = null
function onTapStart(event: PointerEvent) { releaseAnchor(); tapStart = { x: event.clientX, y: event.clientY } }
function onTapEnd(event: PointerEvent) {
  if (!tapStart) return
  const distance = Math.hypot(event.clientX - tapStart.x, event.clientY - tapStart.y)
  tapStart = null
  if (distance < 8 && !(event.target as HTMLElement).closest('button, a, input')) emit('surface-click', event)
}
const reader = inject(READER_KEY)!
const { pages, currentPage, settings, preload, navigation, goTo } = reader
const SEGMENT_SIZE = 120
const segmented = computed(() => pages.value.length > 200)
const segmentStart = ref(Math.floor((currentPage.value - 1) / SEGMENT_SIZE) * SEGMENT_SIZE)
const renderedPages = computed(() => segmented.value ? pages.value.slice(segmentStart.value, segmentStart.value + SEGMENT_SIZE) : pages.value)
const hasPrevious = computed(() => segmented.value && segmentStart.value > 0)
const hasNext = computed(() => segmented.value && segmentStart.value + SEGMENT_SIZE < pages.value.length)

function moveSegment(direction: -1 | 1) {
  const index = Math.max(0, Math.min(segmentStart.value + direction * SEGMENT_SIZE, pages.value.length - 1))
  goTo(pages.value[index].pageNum)
}

const scrollEl = ref<HTMLElement | null>(null)
let scrollObserver: IntersectionObserver | null = null
let resizeObserver: ResizeObserver | null = null
let anchorPage: number | null = currentPage.value
function releaseAnchor() { anchorPage = null }
function alignAnchor() {
  const root = scrollEl.value
  if (!root || anchorPage === null) return
  const target = root.querySelector<HTMLElement>(`[data-page="${anchorPage}"]`)
  if (!target) return
  const top = target.getBoundingClientRect().top - root.getBoundingClientRect().top + root.scrollTop
  if (Math.abs(root.scrollTop - top) > 1) root.scrollTop = top
}
watch(navigation, async request => {
  anchorPage = request.page
  const targetStart = Math.floor((request.page - 1) / SEGMENT_SIZE) * SEGMENT_SIZE
  const changed = segmented.value && segmentStart.value !== targetStart
  if (changed) segmentStart.value = targetStart
  await nextTick()
  if (changed) setupScrollObserver()
  alignAnchor()
})

function setupScrollObserver() {
  scrollObserver?.disconnect()
  resizeObserver?.disconnect()
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
      if (anchorPage === null && bestPage > 0 && currentPage.value !== bestPage) {
        currentPage.value = bestPage
        preload(bestPage)
      }
    },
    { root: scrollEl.value, threshold: [0, 0.25, 0.5, 0.75, 1] }
  )

  resizeObserver = new ResizeObserver(alignAnchor)
  pageEls.forEach((el, i) => {
    el.dataset.page = String(renderedPages.value[i]?.pageNum ?? i + 1)
    scrollObserver!.observe(el)
    resizeObserver!.observe(el)
  })
}

onMounted(async () => {
  await nextTick()
  setupScrollObserver()
  alignAnchor()
})
onBeforeUnmount(() => { scrollObserver?.disconnect(); resizeObserver?.disconnect() })

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
.scroll-segment-button{flex:0 0 auto;width:min(100%,680px);min-height:52px;margin:16px 0;border:1px solid var(--reader-border);border-radius:8px;background:var(--reader-surface);color:var(--reader-text);font:inherit;cursor:pointer}
.scroll-segment-button:hover{background:rgba(255,255,255,.12)}
.scroll-segment-button:focus-visible{outline:2px solid var(--reader-accent);outline-offset:2px}
</style>
