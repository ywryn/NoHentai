<script setup>
defineProps({
  result: { type: Object, required: true },
  busy: Boolean,
  label: { type: String, required: true },
})
const emit = defineEmits(['change'])
</script>

<template>
  <nav v-if="result.total" class="a-pagination" :aria-label="label">
    <button type="button" class="a-button" :disabled="busy || result.page <= 1" @click="emit('change', result.page - 1)">上一页</button>
    <span role="status">第 {{ result.page }} / {{ result.pages }} 页 · 共 {{ result.total }} 条</span>
    <button type="button" class="a-button" :disabled="busy || result.page >= result.pages" @click="emit('change', result.page + 1)">下一页</button>
  </nav>
</template>
