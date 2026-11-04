<script setup>
import AdminMenuButton from './AdminMenuButton.vue'
import { ref, computed, inject, onMounted, onBeforeUnmount, nextTick } from 'vue'
import {useRoute} from 'vue-router'
import { onBeforeRouteLeave } from 'vue-router'
import {serviceChanges} from '@/utils/adminDrafts'
import { adminRequest, formatDate } from '@/utils/adminApi'
const route=useRoute()
const navigation=inject('adminOpenNavigation'), confirm=inject('adminConfirm')
const groups=ref([]),error=ref(''),notice=ref(''),busy=ref(false),loading=ref(true)
const sourceName={database:'后台配置',environment:'服务器启动配置',default:'系统默认'}
const choiceName=value=>({google:'Google Vision',paddle:'PaddleOCR',ocrspace:'OCR.Space',true:'开启',false:'关闭',null:'沿用环境默认'})[String(value)]||String(value)
function dirty(group) {return Object.keys(serviceChanges(group.values,JSON.parse(group.original))).length>0}
const anyDirty=computed(()=>groups.value.some(dirty))
async function load(replaceId=null){loading.value=true;try{const result=await adminRequest('services');const previous=groups.value;groups.value=result.groups.map(group=>{const draft=previous.find(item=>item.id===group.id);if(group.id!==replaceId&&draft&&dirty(draft))return draft;const values=Object.fromEntries(group.fields.map(f=>[f.key,f.effective]));return {...group,values,original:JSON.stringify(values)}})}catch(e){error.value=e.message}finally{loading.value=false}}
async function save(group){if(busy.value||!dirty(group))return;busy.value=true;error.value='';notice.value='';try{
 const values=serviceChanges(group.values,JSON.parse(group.original))
 const result=await adminRequest('service-save',{service:group.id,version:group.version,values});await load(group.id);notice.value=result.unchanged?'内容未发生变化，无需保存。':`${group.label}已保存，后续请求或新任务使用新配置。`
}catch(e){error.value=e.message}finally{busy.value=false}}
async function test(group){
 if(dirty(group)){error.value='请先保存配置，再测试已保存的服务。';return}
 const paid=group.id!=='favorites'
 if(paid&&!await confirm({title:`测试${group.label}？`,description:group.id==='translate'?'将发送一小段测试文字，会产生一次真实翻译请求。':'将发送服务器生成的测试图片，会产生一次真实 OCR 请求并计入用量。',confirmLabel:'发送测试请求'}))return
 busy.value=true;error.value='';notice.value='';try{const result=await adminRequest('service-test',{service:group.id});await load(group.id);if(result.ok)notice.value=result.message;else error.value=result.message}catch(e){error.value=e.message}finally{busy.value=false}
}
async function leave(){return !busy.value&&(!anyDirty.value||await confirm({title:'放弃未保存的服务配置？',description:'离开后将丢失当前未保存的修改。',confirmLabel:'放弃并离开',danger:true}))}
function beforeUnload(e){if(anyDirty.value||busy.value){e.preventDefault();e.returnValue=''}}
window.addEventListener('beforeunload',beforeUnload);onBeforeUnmount(()=>window.removeEventListener('beforeunload',beforeUnload));onBeforeRouteLeave(leave);onMounted(async()=>{await load();await nextTick();if(route.query.group)document.getElementById('service-group-'+route.query.group)?.scrollIntoView({block:'start',behavior:'smooth'})})
</script>
<template><div class="a-page" :aria-busy="loading||busy"><header class="a-page-heading"><div class="a-page-title"><AdminMenuButton /><div><h1>服务配置</h1><p>查看和编辑来源、翻译与识别服务的当前配置。</p></div></div><button class="a-button" :disabled="busy||anyDirty" @click="load">刷新状态</button></header><div v-if="error" class="a-alert a-alert-error" role="alert">{{error}}</div><div v-if="notice" class="a-alert a-alert-success" role="status">{{notice}}</div><p v-if="loading">正在加载服务配置…</p><div class="v2-service-grid"><section v-for="group in groups" :id="'service-group-'+group.id" :key="group.id" class="a-card v2-service"><div class="a-section-heading"><div><h2>{{group.label}}</h2><p>{{dirty(group)?'有未保存修改':'当前配置'}}</p></div><span v-if="group.check" class="a-badge" :class="group.check.ok?'a-badge-success':'a-badge-warning'">{{group.check.version===group.version?(group.check.ok?'验证通过':'验证未通过'):'配置已更改，需重新测试'}}</span><span v-else class="a-badge a-badge-neutral">尚未验证</span></div><fieldset :disabled="busy" class="a-form-stack"><div v-for="field in group.fields" :key="field.key" class="a-field"><label :for="'service-'+field.key">{{field.label}}</label><select v-if="field.type==='select'" :id="'service-'+field.key" v-model="group.values[field.key]"><option v-for="option in field.limits.filter(value=>value!==null)" :key="String(option)" :value="option">{{choiceName(option)}}</option></select><input v-else :id="'service-'+field.key" v-model="group.values[field.key]" :type="field.type==='number'?'number':field.type==='url'?'url':'text'" :min="field.type==='number'?field.limits[0]:undefined" :max="field.type==='number'?field.limits[1]:undefined" :step="field.key==='RETRY_DELAY_SECONDS'?0.5:1" autocomplete="off" spellcheck="false" @input="field.type==='number'&&(group.values[field.key]=$event.target.value===''?'':Number($event.target.value))" /><small>{{sourceName[field.source]}}</small></div></fieldset><p v-if="group.check" class="a-field-help">{{group.check.message}} · {{formatDate(group.check.checked_at)}}</p><div class="a-toolbar"><button class="a-button a-primary" :disabled="busy||!dirty(group)" @click="save(group)">保存{{group.label}}</button><button class="a-button" :disabled="busy||dirty(group)" @click="test(group)">{{group.id==='favorites'?'验证收藏访问':'发送测试请求'}}</button></div></section></div><p class="a-inline-note">输入框显示当前生效值，可直接修改；清空密钥并保存会清空该项配置。保存后可单独测试连接，正在运行的同步任务继续使用启动时的配置。</p></div></template>
