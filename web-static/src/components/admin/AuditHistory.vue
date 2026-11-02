<script setup>
import {ref,inject,onMounted} from 'vue'
import {adminRequest,formatDate} from '@/utils/adminApi'
import RecordHistory from './RecordHistory.vue'
const navigation=inject('adminOpenNavigation'),items=ref([]),events=ref([]),error=ref(''),history=ref(null)
const labels={gallery:'画廊',book:'书目',daily:'每日规则'}
async function load(){try{const [content,audit]=await Promise.all([adminRequest('record-history'),adminRequest('audit-events')]);items.value=content.items;events.value=audit.items}catch(e){error.value=e.message}}
onMounted(load)
</script>
<template><div class="a-page"><header class="a-page-heading"><div class="a-page-title"><button class="a-button a-mobile-menu" @click="navigation">菜单</button><div><h1>修改记录</h1><p>逐条查看内容变化，删除记录也可恢复。</p></div></div><button class="a-button" @click="load">刷新</button></header><p v-if="error" class="a-alert a-alert-error">{{error}}</p><section class="a-card"><article v-for="entry in items" :key="entry.id" class="v2-run"><div class="a-section-heading"><div><strong>{{labels[entry.kind]}} · {{entry.after?.['书名']||entry.before?.['书名']||entry.after?.name||entry.before?.name||entry.recordId}}</strong><small>{{formatDate(entry.date)}} · {{entry.message}}</small></div><button class="a-button" @click="history.open(entry.kind,entry.recordId)">查看差异与恢复</button></div><p>{{Object.keys(entry.changes).join('、')||'顺序调整'}}</p></article><p v-if="!items.length">尚无逐条修改记录。</p></section><section class="a-card"><h2>配置与账户操作</h2><article v-for="(event,index) in events" :key="index" class="v2-run"><strong>{{event.message}}</strong><small>{{formatDate(event.date)}}</small><p v-if="event.fields.length">{{event.fields.join('、')}}</p></article><p v-if="!events.length">尚无配置操作记录。</p></section><RecordHistory ref="history" @restored="load" /></div></template>
