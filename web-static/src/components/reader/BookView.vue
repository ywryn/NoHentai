<!-- web-static/src/components/reader/BookView.vue -->
<template>
  <div
    class="book-view"
    @touchstart.passive="onTouchStart"
    @touchend.passive="onTouchEnd"
  >
    <Transition :name="transitionName">
      <div
        :key="currentPage"
        class="spread"
        :class="{
          'spread-double': effectivePagesPerScreen === 2,
          'spread-rtl': settings.bookDirection === 'rtl',
        }"
      >
        <div class="page-slot" :style="pageStyle">
          <PageImage :page-num="currentPage" />
        </div>
        <div
          v-if="effectivePagesPerScreen === 2 && currentPage < total"
          class="page-slot"
          :style="pageStyle"
        >
          <PageImage :page-num="currentPage + 1" />
        </div>
      </div>
    </Transition>

    <!-- Click zones -->
    <div class="click-zone click-zone-left"   @click="onClickLeft"  />
    <div class="click-zone click-zone-center" />
    <div class="click-zone click-zone-right"  @click="onClickRight" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, inject } from 'vue'
import { READER_KEY } from '@/composables/useReader'
import PageImage from './PageImage.vue'


const reader = inject(READER_KEY)!
const { currentPage, total, settings, effectivePagesPerScreen, prev, next } = reader

// Track flip direction to pick the right CSS transition
const flipDir = ref<'forward' | 'backward'>('forward')
let lastPage = currentPage.value

watch(currentPage, newVal => {
  flipDir.value = newVal > lastPage ? 'forward' : 'backward'
  lastPage = newVal
})

const transitionName = computed(() => {
  if (settings.pageTurnAnimation === 'none') return 'instant'
  // RTL + forward → visual LEFT;  RTL + backward → visual RIGHT
  // LTR + forward → visual RIGHT; LTR + backward → visual LEFT
  const rtl = settings.bookDirection === 'rtl'
  const fwd = flipDir.value === 'forward'
  const dir = (rtl ? fwd : !fwd) ? 'left' : 'right'
  return `${settings.pageTurnAnimation}-${dir}`
})

const pageStyle = computed(() => ({
  maxWidth: `calc(${settings.widthScale}% / ${effectivePagesPerScreen.value})`,
}))

// RTL: click LEFT = next (page numbers increase leftward)
// LTR: click LEFT = prev
function onClickLeft()  { settings.bookDirection === 'rtl' ? next() : prev() }
function onClickRight() { settings.bookDirection === 'rtl' ? prev() : next() }

// Touch swipe
let touchX = 0
function onTouchStart(e: TouchEvent) { touchX = e.touches[0].clientX }
function onTouchEnd(e: TouchEvent) {
  const dx = e.changedTouches[0].clientX - touchX
  if (Math.abs(dx) < 40) return
  dx < 0 ? onClickRight() : onClickLeft()
}
</script>

<style scoped>
.book-view {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: var(--reader-bg);
}

.spread {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  position: absolute;
  inset: 0;
}
.spread-rtl { flex-direction: row-reverse; }

.page-slot {
  flex: 1 1 0;
  min-width: 0;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.spread:not(.spread-double) .page-slot {
  flex: 0 0 auto;
  max-height: 100%;
}
/* LTR: first=left half → image at right seam; last=right half → image at left seam */
.spread-double:not(.spread-rtl) .page-slot:first-child { justify-content: flex-end; }
.spread-double:not(.spread-rtl) .page-slot:last-child  { justify-content: flex-start; }
/* RTL: row-reverse so first=right half → image at left seam; last=left half → image at right seam */
.spread-double.spread-rtl .page-slot:first-child { justify-content: flex-start; }
.spread-double.spread-rtl .page-slot:last-child  { justify-content: flex-end; }
/* In double-page mode, PageImage sizes itself to the image so spinner centers on the image area */
.spread-double .page-slot :deep(.page-image) {
  width: auto;
  height: 100%;
  min-width: 120px;
}
.spread-double .page-slot :deep(.pi-img) {
  height: 100%;
  width: auto;
  max-width: 100%;
}

/* Click zones */
.click-zone {
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 5;
  cursor: pointer;
}
.click-zone-left   { left: 0;   width: 30%; }
.click-zone-center { left: 30%; width: 40%; }
.click-zone-right  { right: 0;  width: 30%; }
</style>
