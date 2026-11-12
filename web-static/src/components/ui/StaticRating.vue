<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ value: number }>()
const rating = computed(() => Math.min(5, Math.max(0, Number(props.value) || 0)))
</script>
<template>
  <span class="nh-rating" role="img" :aria-label="`评分 ${rating}，满分 5`">
    <svg v-for="star in 5" :key="star" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false"
      :class="{ 'is-filled': star <= rating }" stroke-linejoin="round" stroke-width="1.5">
      <path d="m12 2.5 2.9 6 6.6 1-4.8 4.6 1.1 6.5-5.8-3.1-5.8 3.1 1.1-6.5L2.5 9.5l6.6-1Z" />
    </svg>
  </span>
</template>
<style scoped>
.nh-rating { display: inline-flex; align-items: center; gap: 2px; vertical-align: middle; flex-shrink: 0; }
.nh-rating svg { display: block; fill: none; stroke: var(--p-rating-icon-color, var(--muted-color)); }
.nh-rating svg.is-filled { color: var(--p-rating-icon-active-color, var(--primary-color)); fill: currentColor; stroke: currentColor; }
</style>
