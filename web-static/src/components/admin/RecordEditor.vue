<script setup>
import { ref, computed, watch, inject, onMounted, onBeforeUnmount } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { adminRequest, downloadDraft, coverUrl } from '@/utils/adminApi'
import { invalidateGalleryData } from '@/composables/useGalleryData'
import { CATEGORIES } from '../../../../shared/adminData.js'
import AdminIcon from './AdminIcon.vue'
import RecordHistory from './RecordHistory.vue'
const props = defineProps({ kind: { type: String, required: true } })
const confirm = inject('adminConfirm'), navigation = inject('adminOpenNavigation')
const titles = { gallery: '画廊', book: '实体书单', daily: '每日筛选' }
const list = ref([]), total = ref(0), page = ref(1), pages = ref(1), query = ref('')
const selected = ref(null), data = ref(null), original = ref(''), loading = ref(true), busy = ref(false), error = ref(''), errorStatus = ref(0), notice = ref(''), detailOpen = ref(false)
const history = ref(null), matchQuery = ref(''), matches = ref([]), matching = ref(false), linked = ref(null)
const dirty = computed(() => data.value !== null && JSON.stringify(data.value) !== original.value)
const effective = computed(() => ({ ...(selected.value?.source || {}), ...(data.value || {}) }))
const labels = [['title','展示标题'], ['title_jpn','日文标题'], ['category','分类'], ['uploader','上传者'], ['tags','标签']]
const categoryMask = [['Misc',1],['Doujinshi',2],['Manga',4],['Artist CG',8],['Game CG',16],['Image Set',32],['Cosplay',64],['Asian Porn',128],['Non-H',256],['Western',512]]
let searchTimer, matchTimer, sequence = 0, matchSequence = 0
const clone = value => JSON.parse(JSON.stringify(value))
function name(item) { return props.kind === 'gallery' ? item.effective.title_jpn || item.effective.title || `#${item.id}` : props.kind === 'book' ? item.data['书名'] || item.data['日文名'] || '新书目' : item.data.name }
function apply(item) {
  selected.value = clone(item); data.value = clone(item.data); original.value = JSON.stringify(data.value)
  notice.value = ''; error.value = ''; matches.value = []; linked.value = null
  if (props.kind === 'book' && data.value.sid) findLinked(data.value.sid)
}
async function findLinked(gid) {
  try { const result = await adminRequest('record', { kind: 'gallery', id: gid }); if (data.value?.sid === gid) linked.value = result.effective } catch { /* Existing external references remain editable. */ }
}
async function load(target = page.value) {
  const ticket = ++sequence
  loading.value = true
  try {
    const result = await adminRequest('records', { kind: props.kind, query: query.value, page: target })
    if (ticket !== sequence) return
    list.value = result.items; total.value = result.total; page.value = result.page; pages.value = result.pages
    if (!selected.value && result.items.length) apply(result.items[0])
    else if (selected.value) {
      const fresh = result.items.find(item => item.id === selected.value.id)
      if (fresh && fresh.version !== selected.value.version) {
        if (dirty.value) error.value = '服务器中的当前条目已更新，草稿保持不变；请导出后重新加载并合并。'
        else apply(fresh)
      }
    }
  } catch (e) { error.value = e.message; errorStatus.value = e.status }
  finally { if (ticket === sequence) loading.value = false }
}
async function guard() {
  if (busy.value) return false
  return !dirty.value || await confirm({ title: '放弃当前条目的未保存修改？', description: '可以取消并先保存当前条目，也可以导出草稿留存。', confirmLabel: '放弃并继续', danger: true })
}
async function choose(item) { if (await guard()) { apply(item); detailOpen.value = true } }
async function add() {
  if (!await guard()) return
  const value = props.kind === 'book' ? Object.fromEntries(['ID','书名','日文名','收价','原价','sid','备注','cover'].map(k=>[k,'']))
    : { name: '新筛选组', filters: [], keyword: '', categories: 6, minPages: null, maxPages: null, minRating: null, cutoffDays: 10 }
  apply({ id: null, version: '0', data: value }); detailOpen.value = true
}
async function perform(fn) {
  if (busy.value) return false
  busy.value = true; error.value = ''; notice.value = ''; errorStatus.value = 0
  try { await fn(); return true } catch (e) { error.value = e.message; errorStatus.value = e.status; return false } finally { busy.value = false }
}
async function save() {
  if (!dirty.value || !data.value) return false
  return perform(async () => {
    const snapshot = clone(data.value)
    const result = await adminRequest('record-save', { kind: props.kind, id: selected.value.id, version: selected.value.version, data: snapshot })
    selected.value = { ...selected.value, id: result.id, version: result.version, data: snapshot }
    original.value = JSON.stringify(snapshot); invalidateGalleryData()
    await load()
    notice.value = (props.kind === 'daily' ? '规则已保存。执行同步后会更新公开结果。' : '当前条目已保存，后续访问立即生效。') + (result.warnings?.length ? ' '+result.warnings.join('；') : '')
  })
}
async function remove() {
  if (!selected.value?.id) { selected.value = null; data.value = null; return }
  if (!await confirm({ title: props.kind === 'gallery' ? '恢复全部来源值？' : '删除当前条目？', description: '此操作会立即生效，并记录到修改历史。', confirmLabel: props.kind === 'gallery' ? '恢复来源' : '删除', danger: true })) return
  await perform(async () => {
    await adminRequest('record-delete', { kind: props.kind, id: selected.value.id, version: selected.value.version })
    selected.value = null; data.value = null; original.value = ''; invalidateGalleryData(); await load()
    notice.value = '操作已完成，可从修改历史恢复。'
  })
}
async function reload() { if (await guard()) { selected.value = null; data.value = null; original.value = ''; await load() } }
async function runRule() {
  if (dirty.value) { error.value = '请先保存当前规则，再执行同步。'; return }
  await perform(async () => {
    const result = await adminRequest('dispatch', { workflow: 'daily', ruleId: selected.value.id })
    notice.value = `任务 #${result.id} 已加入队列，使用当前保存的规则。`
  })
}
async function move(direction) {
  if (!await guard() || !selected.value?.id) return
  await perform(async () => {
    await adminRequest('record-reorder', { kind: props.kind, id: selected.value.id, direction, version: selected.value.version })
    const fresh = await adminRequest('record', { kind: props.kind, id: selected.value.id }); apply(fresh); await load()
  })
}
async function upload(event) {
  const file = event.target.files[0]
  if (!file) return
  if (file.size > 8*1024*1024) { error.value = '封面最大 8MB'; return }
  await perform(async () => {
    const encoded = await new Promise((resolve,reject) => { const reader = new FileReader(); reader.onload=()=>resolve(String(reader.result).split(',')[1]); reader.onerror=reject; reader.readAsDataURL(file) })
    const result = await adminRequest('media-upload', { imageBase64: encoded }); data.value.cover = result.filename
    notice.value = '封面已上传，请保存当前书目以应用。'
  })
  event.target.value = ''
}
function exportDraft() { downloadDraft(`${props.kind}-draft.json`, { id:selected.value?.id, version:selected.value?.version, data:data.value }) }
function beforeUnload(event) { if (dirty.value || busy.value) { event.preventDefault(); event.returnValue='' } }
function shortcut(event) { if ((event.ctrlKey||event.metaKey) && event.key.toLowerCase()==='s') { event.preventDefault(); save() } }
watch(query, () => { clearTimeout(searchTimer); searchTimer=setTimeout(()=>load(1),250) })
watch(matchQuery, value => {
  clearTimeout(matchTimer); const ticket=++matchSequence
  if (!value.trim()) { matches.value=[]; return }
  matchTimer=setTimeout(async()=>{
    matching.value=true
    try { const result=await adminRequest('records',{kind:'gallery',query:value,page:1}); if(ticket===matchSequence) matches.value=result.items.map(r=>r.effective) }
    catch(e){ error.value=e.message } finally { if(ticket===matchSequence)matching.value=false }
  },250)
})
async function refreshFocused(){
 if(busy.value||!selected.value?.id)return
 const id=selected.value.id
 try{const fresh=await adminRequest('record',{kind:props.kind,id});if(selected.value?.id!==id)return
  if(fresh.version!==selected.value.version){if(dirty.value)error.value='当前条目已在其他设备更新，草稿保持不变；请导出后重新加载并合并。';else apply(fresh)}
  else if(props.kind==='gallery'&&JSON.stringify(fresh.source)!==JSON.stringify(selected.value.source)){selected.value.source=fresh.source;notice.value='来源数据已更新，人工覆盖保持不变。'}
 }catch(e){if(e.status===404)error.value='此条目已在其他设备删除，当前草稿仍保留。'}
}
window.addEventListener('focus',refreshFocused)
onMounted(()=>load(1))
onBeforeRouteLeave(guard)
window.addEventListener('beforeunload',beforeUnload); window.addEventListener('keydown',shortcut)
onBeforeUnmount(()=>{ clearTimeout(searchTimer);clearTimeout(matchTimer);window.removeEventListener('beforeunload',beforeUnload);window.removeEventListener('keydown',shortcut);window.removeEventListener('focus',refreshFocused) })
</script>
<template>
  <div class="a-page" :aria-busy="loading || busy">
    <header class="a-page-heading"><div class="a-page-title"><button class="a-button a-icon-button a-mobile-menu" aria-label="打开管理导航" @click="navigation"><AdminIcon name="menu" /></button><div><h1>{{ titles[kind] }}</h1><p role="status">{{ busy ? '正在处理…' : dirty ? '当前条目有未保存修改' : '按条保存 · 独立版本 · 修改可追溯' }}</p></div></div><div class="a-heading-actions"><button class="a-button" :disabled="busy" @click="reload">刷新列表</button><button v-if="kind!=='gallery'" class="a-button" :disabled="busy" @click="add">{{ kind==='book' ? '新增书目' : '新增分组' }}</button><button class="a-button a-primary" :disabled="busy || !dirty" @click="save">保存当前条目</button></div></header>
    <div v-if="error" class="a-alert a-alert-error" role="alert">{{ error }} <a v-if="errorStatus===401" href="#/admin" target="_blank">新标签页登录</a><button v-if="data" class="a-text-button" @click="exportDraft">导出草稿</button></div>
    <div v-if="notice" class="a-alert a-alert-success" role="status">{{ notice }} <RouterLink v-if="kind==='daily'" to="/admin/tasks">查看任务</RouterLink></div>
    <div class="a-master-detail a-gallery-layout" :class="{'a-detail-open':detailOpen}">
      <aside class="a-card a-master-list"><div class="a-search-row"><input v-model="query" class="v2-input" aria-label="查找条目" :placeholder="kind==='gallery' ? '标题、画廊 ID、链接或标签语法' : '搜索名称、编号或备注'" /></div><div class="a-list-caption">共 {{ total }} 条 <span v-if="loading">正在加载…</span></div><div class="a-gallery-list"><button v-for="item in list" :key="item.id" class="a-gallery-row" :class="{'is-selected':selected?.id===item.id}" @click="choose(item)"><span class="a-gallery-copy"><strong>{{ name(item) }}</strong><span>{{ kind==='gallery' ? '#'+item.id : kind==='book' ? item.data.ID : item.data.filters?.join(' · ') }}</span><span v-if="kind==='gallery' && Object.keys(item.data).length" class="a-badge a-badge-accent">人工覆盖</span></span><AdminIcon name="chevron" /></button><p v-if="!loading&&!list.length" class="a-empty">没有匹配的条目</p></div><footer class="a-pagination"><button class="a-button" :disabled="page<=1||loading" @click="load(page-1)">上一页</button><span>{{page}} / {{pages}}</span><button class="a-button" :disabled="page>=pages||loading" @click="load(page+1)">下一页</button></footer></aside>
      <section class="a-card a-detail-pane"><template v-if="data"><button class="a-button a-mobile-back" @click="detailOpen=false">返回列表</button><div class="a-section-heading"><h2>{{ kind==='gallery' ? '编辑画廊展示信息' : kind==='book' ? '书目信息' : '搜索规则' }}</h2><button class="a-button" @click="exportDraft">导出草稿</button></div>
        <fieldset :disabled="busy" class="a-form-stack">
          <template v-if="kind==='gallery'">
            <div v-for="[field,label] in labels" :key="field" class="a-field-block"><label :for="'record-'+field" class="a-field-label">{{label}}</label><textarea v-if="field==='tags'" :id="'record-'+field" rows="4" :value="effective.tags?.join('\n')" @input="data.tags=$event.target.value.split('\n').map(t=>t.trim()).filter(Boolean)" /><select v-else-if="field==='category'" :id="'record-'+field" :value="effective.category" @change="data.category=$event.target.value"><option v-for="category in [...new Set([...CATEGORIES,selected.source.category].filter(Boolean))]" :key="category">{{category}}</option></select><input v-else :id="'record-'+field" :value="effective[field]||''" @input="data[field]=$event.target.value" /><div class="a-field-foot"><span>{{Object.hasOwn(data,field)?'人工值':'跟随来源'}} · 来源：{{Array.isArray(selected.source[field])?selected.source[field].join('、'):selected.source[field]||'未提供'}}</span><button v-if="Object.hasOwn(data,field)" type="button" class="a-text-button" @click="delete data[field]">恢复来源值</button></div></div>
            <label class="a-switch-row"><span>在公开列表中显示</span><input type="checkbox" :checked="!effective.hidden" @change="data.hidden=!$event.target.checked" /></label><button type="button" class="a-button" @click="remove">恢复全部来源值</button>
          </template>
          <template v-else-if="kind==='book'">
            <div class="a-form-grid"><label v-for="[key,label] in [['书名','中文书名'],['日文名','日文书名'],['ID','书目编号（允许重复）'],['收价','收价'],['原价','原价']]" :key="key" class="a-field">{{label}}<input v-model="data[key]" maxlength="5000" /></label><label class="a-field a-wide">备注<textarea v-model="data['备注']" rows="3" /></label></div>
            <div class="v2-cover"><img v-if="data.cover" :src="coverUrl(data.cover)" alt="当前封面" /><label class="a-field">上传封面<input type="file" accept="image/jpeg,image/png,image/webp" @change="upload" /><small>最大 8MB，自动生成 WebP；保存书目后应用。</small></label><button v-if="data.cover" class="a-button" @click="data.cover=''">移除自定义封面</button></div>
            <label class="a-field">关联画廊 ID<input v-model="data.sid" inputmode="numeric" /></label><p v-if="linked" class="a-inline-note">当前关联：{{linked.title_jpn||linked.title}}</p><label class="a-field">查找关联画廊<input v-model="matchQuery" placeholder="画廊 ID、链接、书名、作者或标签" /></label><p v-if="matching">正在搜索…</p><div class="a-matches"><article v-for="gallery in matches" :key="gallery.gid"><div><strong>{{gallery.title_jpn||gallery.title}}</strong><small>#{{gallery.gid}} · {{gallery.category}}</small></div><button class="a-button" @click="data.sid=String(gallery.gid);linked=gallery">关联</button></article></div>
          </template>
          <template v-else>
            <label class="a-field">分组名称<input v-model="data.name" maxlength="120" /></label><label class="a-field">搜索表达式<textarea v-model="data.keyword" rows="3" /></label><label class="a-field">展示标签（每行一个）<textarea :value="data.filters.join('\n')" @input="data.filters=$event.target.value.split('\n').map(t=>t.trim()).filter(Boolean)" /></label><div class="v2-check-grid"><label v-for="[name,mask] in categoryMask" :key="mask"><input type="checkbox" :checked="Boolean(data.categories & mask)" @change="data.categories=$event.target.checked?data.categories|mask:data.categories&~mask" />{{name}}</label></div><div class="a-form-grid"><label v-for="[key,label,min,max] in [['minPages','最少页数',1,100000],['maxPages','最多页数',1,100000],['minRating','最低评分',2,5],['cutoffDays','回溯天数',1,365]]" :key="key" class="a-field">{{label}}<input type="number" :value="data[key]" :min="min" :max="max" @input="data[key]=$event.target.value===''?null:Number($event.target.value)" /></label></div><button class="a-button a-primary" :disabled="dirty||!selected.id" @click="runRule">立即同步此分组</button><p class="a-field-help">保存只更新规则；同步成功后才更新公开结果。调度时间在任务页设置。</p>
          </template>
        </fieldset>
        <div class="v2-record-actions"><button v-if="kind!=='gallery'" class="a-button" :disabled="busy||dirty||!selected.id" @click="move(-1)">上移</button><button v-if="kind!=='gallery'" class="a-button" :disabled="busy||dirty||!selected.id" @click="move(1)">下移</button><button class="a-button" :disabled="busy||dirty||!selected.id" title="保存或放弃当前草稿后查看与恢复历史" @click="history.open(kind,selected.id)">修改历史</button><button v-if="dirty" class="a-button" @click="data=clone(JSON.parse(original))">放弃修改</button><button v-if="kind!=='gallery'" class="a-button a-danger-text" :disabled="busy" @click="remove">删除条目</button></div>
      </template><div v-else class="a-empty">选择一个条目，或从上方新增。</div></section>
    </div><RecordHistory ref="history" @restored="reload" />
  </div>
</template>
