<script setup>
import {inject,ref} from 'vue'
import AdminIcon from './AdminIcon.vue'
const open=inject('adminOpenNavigation',()=>{})
const expanded=inject('adminNavigationOpen',ref(false))
</script>
<template><button type="button" class="a-mobile-menu a-menu-trigger" aria-label="打开管理导航" aria-haspopup="dialog" aria-controls="admin-navigation" :aria-expanded="expanded" @click="open"><AdminIcon name="menu" :size="20"/></button></template>
<style scoped>
.a-menu-trigger{display:none;align-items:center;justify-content:center;flex-shrink:0;width:42px;min-height:42px;padding:0;border:1px solid var(--a-border);border-radius:12px;background:var(--a-panel);color:var(--a-text);box-shadow:0 2px 4px #18284d04;cursor:pointer;transition:background .18s,border-color .18s,color .18s}
.a-menu-trigger:hover,.a-menu-trigger[aria-expanded=true]{color:var(--a-accent);background:var(--a-soft);border-color:color-mix(in srgb,var(--a-accent) 25%,var(--a-border))}
.a-menu-trigger:focus-visible{outline:3px solid var(--a-soft);outline-offset:3px}
@media(max-width:900px){.a-menu-trigger{display:inline-flex}}
</style>
