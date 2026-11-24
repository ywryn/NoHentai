<script setup>
import { ref, inject } from 'vue'
import { adminRequest, formatDate } from '@/utils/adminApi'
import HistoryPagination from './HistoryPagination.vue'
const emit = defineEmits(['restored'])
const confirm = inject('adminConfirm'), modal=ref(null), result=ref({items: []}), error=ref(''), busy=ref(false)
const labels={title:'标题',title_jpn:'日文标题',tags:'标签',category:'分类',uploader:'上传者',hidden:'隐藏',name:'分组名称',keyword:'搜索表达式'}
const display = value => value === null || value === undefined ? '未设置' : typeof value==='object' ? JSON.stringify(value) : String(value)
let record, latestRequest
async function load(page, focusId) {
  const request = Symbol()
  latestRequest = request
  error.value = ''
  busy.value = true
  try {
    const data = await adminRequest('record-history', { ...record, page, focusId })
    if (latestRequest === request) result.value = data
  } catch (e) {
    if (latestRequest === request) error.value = e.message
  } finally {
    if (latestRequest === request) busy.value = false
  }
}
function open(kind, id, focusId) {
  record = { kind, id }
  result.value = { items: [] }
  modal.value.showModal()
  return load(1, focusId)
}
async function restore(entry) {
  if (!await confirm({title:'恢复此版本？',description:'将使用历史内容创建一个新版本，当前条目的修改也会保留在历史中。已删除的书目将追加到末尾。',confirmLabel:'恢复版本'}))return
  busy.value=true;error.value=''
  try {
    let version='0'
    try { version=(await adminRequest('record',{kind:entry.kind,id:entry.recordId})).version } catch(e){if(e.status!==404)throw e}
    await adminRequest('record-restore',{historyId:entry.id,version});modal.value.close();emit('restored')
  }catch(e){error.value=e.message}finally{busy.value=false}
}
defineExpose({open})
</script>
<template><dialog ref="modal" class="a-modal v2-history touch-scroll-area"><div class="a-section-heading"><h2>修改历史与恢复</h2><button class="a-button" @click="modal.close()">关闭</button></div><p v-if="busy">正在处理…</p><p v-if="error" class="a-alert a-alert-error">{{error}}</p><p v-if="!busy&&!error&&!result.items.length" class="a-empty">尚无逐条修改记录。迁移前的资源历史仍保存在数据库中。</p><article v-for="entry in result.items" :key="entry.id" class="v2-history-entry"><div class="a-section-heading"><div><strong>{{entry.message}}</strong><small>{{formatDate(entry.date)}}</small></div><button class="a-button" :disabled="busy||entry.message==='调整顺序'" :title="entry.message==='调整顺序'?'顺序请使用上下移动调整':''" @click="restore(entry)">恢复此版本</button></div><dl><div v-for="(change,key) in entry.changes" :key="key"><dt>{{labels[key]||key}}</dt><dd><del>{{display(change.before)}}</del><span> → </span><ins>{{display(change.after)}}</ins></dd></div></dl></article><HistoryPagination :result="result" :busy="busy" label="条目修改历史分页" @change="load" /></dialog></template>
