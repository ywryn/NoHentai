<script setup lang="ts">
withDefaults(defineProps<{ admin?: boolean; size?: number }>(), { admin: false, size: 40 })
</script>
<template>
  <img :src="admin ? '/brand/mark-b.png' : '/brand/mark-f.png'" :width="size" :height="size"
    class="nh-brand-mark" :class="{ 'nh-brand-mark-admin': admin }" alt="" aria-hidden="true" decoding="async" />
</template>
<style scoped>
.nh-brand-mark { display: block; object-fit: contain; flex: 0 0 auto; }
.nh-brand-mark-admin { border-radius: 5px; background: #edf2e9; }
</style>
