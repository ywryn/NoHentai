<script setup>
import {ref,watch,onBeforeUnmount} from 'vue'
import {activeToken,applySuggestion,SEARCH_SYNTAX_HELP} from '@/utils/gallerySearch'
import {loadTagSuggestions} from '@/composables/useGalleryData'
import AdminIcon from './AdminIcon.vue'
const props=defineProps({modelValue:String,label:{default:'查找条目'},placeholder:{default:'标题、ID、画廊链接或标签…'},help:{type:Boolean,default:true}})
const emit=defineEmits(['update:modelValue','submit'])
const input=ref(null),items=ref([]),open=ref(false),highlight=ref(-1),failure=ref('')
const id='search-'+Math.random().toString(36).slice(2)
let timer,controller,blurTimer
watch(()=>props.modelValue,value=>{
 clearTimeout(timer);controller?.abort();items.value=[];highlight.value=-1;failure.value=''
 const token=activeToken(value||'').text
 if(token.length<2)return
 controller=new AbortController();const request=controller
 timer=setTimeout(async()=>{try{const result=await loadTagSuggestions(token,request.signal);if(controller!==request)return;items.value=result.items;open.value=true}catch(e){if(e.name!=='AbortError')failure.value='补全暂不可用，仍可直接搜索'}},160)
})
function closeSoon(){clearTimeout(blurTimer);blurTimer=setTimeout(()=>open.value=false,150)}
function choose(item){emit('update:modelValue',applySuggestion(props.modelValue||'',item));items.value=[];open.value=false;input.value?.focus()}
function key(event){
 if(event.key==='Escape'){open.value=false;return}
 if(open.value&&items.value.length&&['ArrowDown','ArrowUp'].includes(event.key)){event.preventDefault();highlight.value=(highlight.value+(event.key==='ArrowDown'?1:-1)+items.value.length)%items.value.length}
 else if((event.key==='Enter'||event.key==='Tab')&&open.value&&highlight.value>=0){event.preventDefault();choose(items.value[highlight.value])}
 else if(event.key==='Enter'){open.value=false;emit('submit')}
}
onBeforeUnmount(()=>{clearTimeout(timer);clearTimeout(blurTimer);controller?.abort()})
</script>
<template><div class="ops-search"><div class="ops-search-box"><AdminIcon name="search" :size="17"/><input ref="input" :value="modelValue" :aria-label="label" :placeholder="placeholder" role="combobox" aria-autocomplete="list" :aria-controls="id" :aria-expanded="open&&items.length>0" :aria-activedescendant="highlight>=0?`${id}-${highlight}`:undefined" @input="emit('update:modelValue',$event.target.value)" @keydown="key" @focus="open=true" @blur="closeSoon"/><button v-if="modelValue" type="button" class="ops-icon" aria-label="清空搜索" @click="emit('update:modelValue','')"><AdminIcon name="close" :size="15"/></button></div><div v-if="open&&items.length" :id="id" role="listbox" class="ops-suggestions"><button v-for="(item,index) in items" :id="`${id}-${index}`" :key="item.tag" type="button" role="option" :aria-selected="highlight===index" @mousedown.prevent="choose(item)"><strong>{{item.tag_cn||item.value}}</strong><small>{{item.namespace}}:{{item.value}}</small></button></div><small v-if="failure">{{failure}}</small><details v-if="help" class="ops-search-help"><summary>高级搜索 <span>支持中文标签、排除与组合条件</span></summary><button v-for="item in SEARCH_SYNTAX_HELP" :key="item.syntax" type="button" @click="emit('update:modelValue',item.example)"><code>{{item.syntax}}</code><span>{{item.desc}}</span></button></details></div></template>
