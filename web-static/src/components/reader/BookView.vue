<!-- web-static/src/components/reader/BookView.vue -->
<template>
  <div
    class="book-view"
    @touchstart.passive="onTouchStart"
    @touchend.passive="onTouchEnd"
  >
    <Transition
      v-for="spread in cachedSpreads"
      :key="spread.startPage"
      :name="transitionName"
    >
      <div
        v-show="spread.startPage === currentPage"
        class="spread"
        :class="{
          'spread-double': effectivePagesPerScreen === 2,
          'spread-rtl': settings.bookDirection === 'rtl',
        }"
      >
        <div class="page-slot" :style="pageStyle">
          <PageImage :page-num="spread.startPage" :active="spread.startPage === currentPage" />
        </div>
        <div
          v-if="spread.endPage !== null"
          class="page-slot"
          :style="pageStyle"
        >
          <PageImage :page-num="spread.endPage" :active="spread.startPage === currentPage" />
        </div>
      </div>
    </Transition>

    <div class="click-zone click-zone-left" @click="onClickLeft" />
    <div class="click-zone click-zone-center" />
    <div class="click-zone click-zone-right" @click="onClickRight" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, inject } from 'vue'
import { READER_KEY } from '@/composables/useReader'
import PageImage from './PageImage.vue'

interface Spread {
  startPage: number
  endPage: number | null
}

const reader = inject(READER_KEY)!
const { currentPage, total, settings, effectivePagesPerScreen, prev, next } = reader

const flipDir = ref<'forward' | 'backward'>('forward')
let lastPage = currentPage.value

watch(currentPage, newVal => {
  flipDir.value = newVal > lastPage ? 'forward' : 'backward'
  lastPage = newVal
})

const transitionName = computed(() => {
  if (settings.pageTurnAnimation === 'none') return 'instant'
  const rtl = settings.bookDirection === 'rtl'
  const fwd = flipDir.value === 'forward'
  const dir = (rtl ? fwd : !fwd) ? 'left' : 'right'
  return `${settings.pageTurnAnimation}-${dir}`
})

const pageStyle = computed(() => ({
  maxWidth: `calc(${settings.widthScale}% / ${effectivePagesPerScreen.value})`,
}))

const cachedSpreads = computed<Spread[]>(() => {
  const step = effectivePagesPerScreen.value
  const spreads: Spread[] = []
  const maxDistance = 3

  for (let off = -maxDistance; off <= maxDistance; off++) {
    const startPage = currentPage.value + off * step
    if (startPage < 1 || startPage > total.value) continue
    spreads.push({
      startPage,
      endPage: step === 2 && startPage < total.value ? startPage + 1 : null,
    })
  }

  return spreads
})

function onClickLeft() { settings.bookDirection === 'rtl' ? next() : prev() }
function onClickRight() { settings.bookDirection === 'rtl' ? prev() : next() }

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
  background: var(--reader-bg);
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
.spread-double:not(.spread-rtl) .page-slot:first-child { justify-content: flex-end; }
.spread-double:not(.spread-rtl) .page-slot:last-child  { justify-content: flex-start; }
.spread-double.spread-rtl .page-slot:first-child { justify-content: flex-start; }
.spread-double.spread-rtl .page-slot:last-child  { justify-content: flex-end; }
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

.click-zone {
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 5;
  cursor: pointer;
}
.click-zone-left   { left: 0; width: 30%; }
.click-zone-center { left: 30%; width: 40%; }
.click-zone-right  { right: 0; width: 30%; }
</style>
