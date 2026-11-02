<script setup>
import {ref,watch} from 'vue'
import {exTypeDotColors,formatTimestamp} from '@/utils/galleryUtils'
import AdminIcon from './AdminIcon.vue'
const props=defineProps({gallery:Object,compact:Boolean})
const broken=ref(false)
watch(()=>props.gallery?.thumb,()=>broken.value=false)
</script>
<template><div class="ops-gallery-preview" :class="{'is-compact':compact}"><div class="ops-artwork"><img v-if="gallery?.thumb&&!broken" :src="gallery.thumb" alt="画廊封面" referrerpolicy="no-referrer" @error="broken=true"/><div v-else class="ops-artwork-empty"><AdminIcon name="gallery" :size="28"/><small>{{broken?'封面暂不可用':'暂无封面'}}</small></div></div><div v-if="gallery" class="ops-gallery-copy"><span class="ops-category" :style="{'--category':exTypeDotColors[gallery.category]||'#757575'}">{{gallery.category||'未分类'}}</span><h3>{{gallery.title_jpn||gallery.title}}</h3><p v-if="!compact&&gallery.title_jpn">{{gallery.title}}</p><div class="ops-gallery-meta"><span>#{{gallery.gid}}</span><span v-if="gallery.filecount">{{gallery.filecount}} 页</span><span v-if="gallery.rating">★ {{gallery.rating}}</span><span v-if="gallery.uploader">{{gallery.uploader}}</span><span v-if="!compact&&gallery.posted">{{formatTimestamp(gallery.posted)}}</span></div><slot/></div><div v-else class="ops-gallery-copy"><h3>尚未关联画廊</h3><p>通过下方搜索，核对封面后建立关联。</p></div></div></template>
