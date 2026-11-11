<script setup>
import {nextTick} from 'vue'
import AdminIcon from './AdminIcon.vue'
const props=defineProps({modelValue:String,items:Array,label:String,prefix:{default:'tasks-tabs'}})
const emit=defineEmits(['update:modelValue'])
async function navigate(event,index){
 const directions={ArrowRight:1,ArrowLeft:-1}
 let target
 if(event.key in directions)target=(index+directions[event.key]+props.items.length)%props.items.length
 else if(event.key==='Home')target=0
 else if(event.key==='End')target=props.items.length-1
 else return
 event.preventDefault();const container=event.currentTarget.parentElement
 emit('update:modelValue',props.items[target].id)
 await nextTick();container.querySelectorAll('[role=tab]')[target]?.focus()
}
</script>
<template><div class="a-view-switch" role="tablist" :aria-label="label"><button v-for="(item,index) in items" :id="prefix+'-'+item.id" :key="item.id" type="button" role="tab" :aria-selected="modelValue===item.id" :aria-controls="prefix+'-panel-'+item.id" :tabindex="modelValue===item.id?0:-1" @click="emit('update:modelValue',item.id)" @keydown="navigate($event,index)"><AdminIcon :name="item.icon" :size="16"/><span>{{item.label}}</span><small v-if="item.count!==undefined">{{item.count}}</small></button></div></template>
<style scoped>
.a-view-switch{display:inline-flex;justify-self:start;max-width:100%;gap:4px;padding:5px;border:1px solid var(--a-border);border-radius:13px;background:color-mix(in srgb,var(--a-border) 30%,var(--a-bg))}
.a-view-switch button{display:flex;align-items:center;justify-content:center;gap:9px;min-height:38px;padding:8px 16px;border:1px solid transparent;border-radius:9px;background:transparent;color:var(--a-muted);font-size:12px;font-weight:500;white-space:nowrap;cursor:pointer;transition:background .18s,color .18s,box-shadow .18s}
.a-view-switch button:hover{background:color-mix(in srgb,var(--a-panel) 55%,transparent);color:var(--a-text);box-shadow:none}
.a-view-switch button[aria-selected=true]{background:var(--a-panel);color:var(--a-text);border-color:var(--a-border);box-shadow:0 2px 4px #18284d08;font-weight:600}
.a-view-switch button[aria-selected=true] svg{color:var(--a-accent)}
.a-view-switch small{padding:2px 6px;border-radius:5px;background:color-mix(in srgb,var(--a-border) 30%,transparent);color:var(--a-faint);font-size:10px;font-variant-numeric:tabular-nums}
.a-view-switch button[aria-selected=true] small{background:var(--a-soft);color:var(--a-accent)}
.a-view-switch button:focus-visible{outline:2px solid var(--a-accent);outline-offset:1px}
@media(max-width:640px){.a-view-switch{width:100%;box-sizing:border-box}.a-view-switch button{flex:1;padding:8px 10px;min-height:42px;gap:7px}}
@media(prefers-reduced-motion:reduce){.a-view-switch button{transition:none}}
</style>
