<script setup lang="ts">
import { computed } from 'vue'
import { iconPaths, iconAliases, type IconName } from '@/icons/paths'
const props = withDefaults(defineProps<{ name: string; size?: number }>(), { size: 20 })
const paths = computed(() => iconPaths[(iconAliases[props.name] || props.name) as IconName] || iconPaths.info)
</script>

<template>
  <svg class="nh-icon" :data-icon="name" :width="size" :height="size" viewBox="0 0 24 24"
    style="fill: none; stroke: currentColor; stroke-width: 1.8; flex-shrink: 0; vertical-align: middle"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    <path v-for="(d, i) in paths" :key="i" :d="d" />
  </svg>
</template>
