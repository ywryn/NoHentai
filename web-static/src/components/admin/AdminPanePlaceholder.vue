<script setup>
defineProps({ loading: Boolean, variant: { type: String, default: 'form' }, label: { type: String, default: '正在加载内容…' } })
defineEmits(['retry'])
</script>
<template>
  <div v-if="loading" class="a-pane-placeholder" :class="`a-placeholder-${variant}`" role="status" aria-busy="true">
    <span class="a-sr-only">{{ label }}</span>
    <template v-if="variant === 'list'"><div v-for="n in 6" :key="n" class="a-placeholder-row" aria-hidden="true"><span class="a-placeholder-cover a-shimmer" /><div><span class="a-placeholder-line a-shimmer" /><span class="a-placeholder-line a-short a-shimmer" /></div></div></template>
    <template v-else><div class="a-placeholder-title a-shimmer" aria-hidden="true" /><div v-for="n in 4" :key="n" class="a-placeholder-field" aria-hidden="true"><span class="a-placeholder-label a-shimmer" /><span class="a-placeholder-input a-shimmer" /></div></template>
  </div>
  <div v-else class="a-empty a-pane-retry"><h3>内容暂时无法加载</h3><p>请重试连接，线上数据未受影响。</p><button class="a-button" @click="$emit('retry')">重新加载</button></div>
</template>
