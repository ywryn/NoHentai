<script setup>
import { ref, inject } from 'vue'
import { adminRequest, formatDate } from '@/utils/adminApi'
const emit = defineEmits(['restored'])
const confirm = inject('adminConfirm'), modal=ref(null), items=ref([]), error=ref(''), busy=ref(false)
const labels={title:'标题',title_jpn:'日文标题',tags:'标签',category:'分类',uploader:'上传者',hidden:'隐藏',name:'分组名称',keyword:'搜索表达式'}
const display = value => value === null || value === undefined ? '未设置' : typeof value==='object' ? JSON.stringify(value) : String(value)
async function open(kind,id) {
  error.value='';busy.value=true;items.value=[];modal.value.showModal()
  try { items.value=(await adminRequest('record-history',{kind,id})).items } catch(e){error.value=e.message} finally {busy.value=false}
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
<template><dialog ref="modal" class="a-modal v2-history"><div class="a-section-heading"><h2>修改历史与恢复</h2><button class="a-button" @click="modal.close()">关闭</button></div><p v-if="busy">正在处理…</p><p v-if="error" class="a-alert a-alert-error">{{error}}</p><p v-if="!busy&&!items.length" class="a-empty">尚无逐条修改记录。迁移前的资源历史仍保存在数据库中。</p><article v-for="entry in items" :key="entry.id" class="v2-history-entry"><div class="a-section-heading"><div><strong>{{entry.message}}</strong><small>{{formatDate(entry.date)}}</small></div><button class="a-button" :disabled="busy||entry.message==='调整顺序'" :title="entry.message==='调整顺序'?'顺序请使用上下移动调整':''" @click="restore(entry)">恢复此版本</button></div><dl><div v-for="(change,key) in entry.changes" :key="key"><dt>{{labels[key]||key}}</dt><dd><del>{{display(change.before)}}</del><span> → </span><ins>{{display(change.after)}}</ins></dd></div></dl></article></dialog></template>
