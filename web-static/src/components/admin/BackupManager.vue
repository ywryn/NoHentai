<script setup>
import AdminMenuButton from './AdminMenuButton.vue'
import {ref,inject,onMounted} from 'vue'
import {adminRequest,formatDate} from '@/utils/adminApi'
const navigation=inject('adminOpenNavigation'),items=ref([]),error=ref(''),notice=ref(''),busy=ref(false)
const size=bytes=>(bytes/1024/1024).toFixed(1)+' MB'
async function load(){try{items.value=(await adminRequest('backups')).items}catch(e){error.value=e.message}}
async function create(){busy.value=true;error.value='';try{await adminRequest('backup-create');await load();notice.value='一致性备份已完成。'}catch(e){error.value=e.message}finally{busy.value=false}}
onMounted(load)
</script>
<template><div class="a-page"><header class="a-page-heading"><div class="a-page-title"><AdminMenuButton /><div><h1>备份与恢复</h1><p>保存数据库快照，下载并另行保管。</p></div></div><button class="a-button a-primary" :disabled="busy" @click="create">{{busy?'正在备份…':'立即备份'}}</button></header><p v-if="error" class="a-alert a-alert-error" role="alert">{{error}}</p><p v-if="notice" class="a-alert a-alert-success" role="status">{{notice}}</p><section class="a-card"><h2>最近备份</h2><article v-for="item in items" :key="item.name" class="v2-run"><strong>{{formatDate(item.modified*1000)}}</strong><small>{{size(item.size)}} · {{item.name}}</small><div class="a-toolbar"><a class="a-button" :href="'/api/admin/backups/'+encodeURIComponent(item.name)">下载数据库</a><a v-if="item.media" class="a-button" :href="'/api/admin/backups/'+encodeURIComponent(item.media)">下载上传封面</a></div></article><p v-if="!items.length">尚无备份。</p></section><section class="a-card a-form-stack"><h2>恢复方式</h2><p>日常误操作可在条目的“修改历史”中恢复内容。整库恢复会同时恢复内容、配置和会话，需在停写的维护流程中执行。</p><p>数据库保留最近七份备份；上传封面在有文件时生成同名媒体包。加密主密钥只在服务器环境文件中，需要单独备份。请把备份复制到服务器以外的位置。</p></section></div></template>
