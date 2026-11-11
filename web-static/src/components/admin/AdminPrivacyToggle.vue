<script setup>
import { useMomMode } from '@/composables/useMomMode'
import AdminIcon from './AdminIcon.vue'
const { isMomMode, toggleMomMode } = useMomMode()
</script>

<template>
  <button
    type="button"
    class="a-privacy-toggle"
    aria-label="马赛克模式"
    :aria-pressed="isMomMode"
    :title="isMomMode ? '关闭马赛克模式（与主页同步）' : '开启马赛克模式（与主页同步）'"
    @click="toggleMomMode"
  >
    <AdminIcon :name="isMomMode ? 'eye-off' : 'eye'" :size="18" />
    <span>马赛克模式</span>
    <span class="a-privacy-state">{{ isMomMode ? '已开启' : '已关闭' }}</span>
  </button>
</template>

<style scoped>
.a-privacy-toggle[aria-pressed='true'] {
  color: var(--a-accent);
  background: var(--a-soft);
}
.a-privacy-state {
  margin-left: auto;
  font-size: 10px;
  opacity: .75;
}
</style>
