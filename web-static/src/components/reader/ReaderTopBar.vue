<template>
  <div
    class="top-bar"
    :class="{ 'top-bar-hidden': !barVisible }"
    @mouseover="$emit('mouseover')"
  >
    <button class="reader-btn top-bar-back" @click="$emit('back')">← Back</button>
    <span class="top-bar-title">{{ galleryTitle }}</span>
    <span class="top-bar-counter">{{ pageCounter }}</span>
    <button
      class="reader-btn"
      :class="{ 'btn-active': showThumbGrid }"
      title="Thumbnails (F)"
      @click="$emit('toggleThumbGrid')"
    >⊞</button>
    <button
      class="reader-btn"
      :class="{ 'btn-active': showSettings }"
      title="Settings (S)"
      @click="$emit('toggleSettings')"
    >⚙</button>
  </div>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { READER_KEY } from '@/composables/useReader'

defineProps<{
  barVisible: boolean
  showThumbGrid: boolean
  showSettings: boolean
}>()
defineEmits<{
  back: []
  toggleThumbGrid: []
  toggleSettings: []
  mouseover: []
}>()

const reader = inject(READER_KEY)!
const { galleryTitle, currentPage, total, effectivePagesPerScreen } = reader

const pageCounter = computed(() => {
  const p = currentPage.value
  const t = total.value
  const step = effectivePagesPerScreen.value
  if (step === 2 && p < t) return `${p}–${p + 1} / ${t}`
  return `${p} / ${t}`
})
</script>

<style scoped>
.top-bar {
  position: relative;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px;
  height: var(--reader-bar-h);
  background: linear-gradient(to bottom, rgba(0,0,0,0.85), transparent);
  transition: opacity 0.3s;
  flex-shrink: 0;
}
.top-bar-hidden { opacity: 0; pointer-events: none; }
.top-bar-back { flex-shrink: 0; }
.top-bar-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  color: var(--reader-muted);
  min-width: 0;
}
.top-bar-counter {
  font-size: 13px;
  color: var(--reader-muted);
  flex-shrink: 0;
}
.btn-active { background: rgba(96,165,250,0.2); color: var(--reader-accent); }
</style>
