<script setup>
import { ref, onBeforeUnmount } from 'vue'
import AdminIcon from './AdminIcon.vue'
const modal = ref(null), options = ref({})
let resolvePending
function ask(value) {
  if (resolvePending) return Promise.resolve(false)
  options.value = value
  modal.value.returnValue = ''
  return new Promise(resolve => { resolvePending = resolve; modal.value.showModal() })
}
function closed() { resolvePending?.(modal.value.returnValue === 'confirm'); resolvePending = null }
onBeforeUnmount(() => resolvePending?.(false))
defineExpose({ ask })
</script>
<template><dialog ref="modal" class="a-confirm" aria-labelledby="admin-confirm-title" aria-describedby="admin-confirm-description" @close="closed"><form method="dialog"><span class="a-icon-tile" :class="{ 'a-danger-tile': options.danger }"><AdminIcon :name="options.danger ? 'trash' : 'info'" :size="24" /></span><h2 id="admin-confirm-title">{{ options.title }}</h2><p id="admin-confirm-description">{{ options.description }}</p><div class="a-confirm-actions"><button class="a-button" value="cancel" autofocus>取消</button><button class="a-button" :class="options.danger ? 'a-danger' : 'a-primary'" value="confirm">{{ options.confirmLabel || '确认' }}</button></div></form></dialog></template>
