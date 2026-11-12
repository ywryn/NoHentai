<script setup>
import AppIcon from '@/components/ui/AppIcon.vue'
defineProps({ name: String, size: { type: Number, default: 20 } })
</script>
<template><AppIcon :name="name" :size="size" /></template>
