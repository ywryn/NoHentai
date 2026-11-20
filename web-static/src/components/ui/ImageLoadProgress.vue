<template>
  <div class="image-load-progress" :class="stage">
    <span class="image-load-ring" aria-hidden="true" />
    <span role="status">{{ labels[stage] }}</span>
  </div>
</template>

<script setup lang="ts">
defineProps<{ stage: 'list' | 'address' | 'image' }>()

const labels = {
  list: '正在获取页面列表…',
  address: '正在获取图片地址…',
  image: '正在载入图片…',
}
</script>

<style scoped>
.image-load-progress {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  pointer-events: none;
}
.image-load-progress.address { --ring-color: #3b82f6; }
.image-load-progress.list { --ring-color: #8b5cf6; }
.image-load-progress.image { --ring-color: #14b8a6; }
.image-load-ring {
  inline-size: 28px;
  block-size: 28px;
  box-sizing: border-box;
  border: 3px solid color-mix(in srgb, currentColor 25%, transparent);
  border-block-start-color: var(--ring-color);
  border-radius: 50%;
}
@media (prefers-reduced-motion: no-preference) {
  .image-load-ring { animation: image-load-spin 0.8s linear infinite; }
}
@media (forced-colors: active) {
  .image-load-ring {
    forced-color-adjust: none;
    border-color: GrayText;
    border-block-start-color: CanvasText;
  }
}
@keyframes image-load-spin {
  to { transform: rotate(1turn); }
}
</style>
