<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { validateOverrides, validateDaily, validateTranslate, CATEGORIES } from '../../../../shared/adminData.js'

const props = defineProps({ adminPassword: { type: String, required: true }, section: { type: String, required: true } })
const API_BASE = import.meta.env.VITE_API_BASE || 'https://no-hentai.vercel.app'
const resource = computed(() => props.section === 'galleries' ? 'overrides' : props.section)
const isEditor = computed(() => ['galleries', 'daily', 'translate'].includes(props.section))
const data = ref(null), sha = ref(''), original = ref(''), busy = ref(false), error = ref(''), notice = ref(''), lastCommit = ref('')
const dirty = computed(() => data.value !== null && JSON.stringify(data.value) !== original.value || patchDirty.value)
const history = ref([])
const query = ref(''), page = ref(1), total = ref(0), items = ref([]), selected = ref(null), patch = ref('{}'), patchOriginal = ref('{}')
const patchDirty = computed(() => patch.value !== patchOriginal.value)
const patchValue = computed(() => { try { return JSON.parse(patch.value) } catch { return {} } })
const galleryFields = [['title', '展示标题'], ['title_jpn', '日文标题'], ['tags', '标签'], ['category', '分类'], ['uploader', '上传者'], ['hidden', '隐藏画廊']]
const categoryOptions = [['Misc', 1], ['Doujinshi', 2], ['Manga', 4], ['Artist CG', 8], ['Game CG', 16], ['Image Set', 32], ['Cosplay', 64], ['Asian Porn', 128], ['Non-H', 256], ['Western', 512]]
const runs = ref([]), release = ref(null), platforms = ref(null), health = ref(null), backendDeployment = ref(null)
const secretPlatform = ref('github'), secretName = ref(''), secretValue = ref('')
const secretOptions = computed(() => platforms.value?.[secretPlatform.value]?.secrets || [])
const titles = { galleries: '画廊元数据', daily: '每日筛选规则', translate: '翻译配置', tasks: '任务与发布', system: '凭证与测活' }
const workflows = [['deploy.yml', '发布前端'], ['sync.yml', '全量同步并发布'], ['sync-ex.yml', '同步收藏并发布'], ['sync-translations.yml', '同步标签翻译并发布']]
const statuses = { queued: '排队中', in_progress: '运行中', completed: '已完成', waiting: '等待中', success: '成功', failure: '失败', cancelled: '已取消', timed_out: '超时', action_required: '需要处理', skipped: '已跳过' }
async function request(action, body = {}) {
  const r = await fetch(`${API_BASE}/api/admin`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: props.adminPassword, action, ...body }) })
  const result = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(result.error || `请求失败（${r.status}）`)
  return result
}
async function perform(fn) {
  if (busy.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try { await fn() } catch (e) { error.value = e.message || '请求失败' }
  finally { busy.value = false }
}
async function search() {
  const result = await request('gallery-search', { query: query.value, page: page.value })
  items.value = result.items; total.value = result.total
}
async function load() {
  if (isEditor.value) {
    const result = await request('load', { resource: resource.value })
    data.value = result.data; sha.value = result.sha; original.value = JSON.stringify(result.data)
    selected.value = null; patch.value = patchOriginal.value = '{}'; lastCommit.value = ''
    if (props.section === 'galleries') await search()
  } else if (props.section === 'tasks') {
    const [result, deployed] = await Promise.all([request('runs'), fetch(`${import.meta.env.BASE_URL}data/release.json?ts=${Date.now()}`, { cache: 'no-store' }).then(r => r.ok ? r.json() : null).catch(() => null)])
    runs.value = result.runs; release.value = deployed
  } else platforms.value = await request('platforms')
}
function allowLeave() { return !busy.value && (!dirty.value || window.confirm('有未保存的修改，确定离开？可以先导出草稿。')) }
onBeforeRouteLeave(allowLeave)
function beforeUnload(e) { if (dirty.value || busy.value) { e.preventDefault(); e.returnValue = '' } }
window.addEventListener('beforeunload', beforeUnload)
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
onMounted(() => perform(load))
function select(item) {
  if (patchDirty.value && !window.confirm('放弃当前未应用的字段修改？')) return
  selected.value = item
  patch.value = patchOriginal.value = JSON.stringify(data.value[String(item.gallery.gid)] || {}, null, 2)
}
function applyPatch() {
  try {
    const id = String(selected.value.gallery.gid), next = JSON.parse(patch.value)
    validateOverrides({ [id]: next })
    if (Object.keys(next).length) data.value[id] = next
    else delete data.value[id]
    patchOriginal.value = patch.value
    error.value = ''; notice.value = '修改已加入草稿，点击“提交并发布”后保存到 GitHub。'
  } catch (e) { error.value = e.message }
}
function restore() { patch.value = '{}'; applyPatch() }
function setField(field, enabled) {
  try {
    const next = JSON.parse(patch.value)
    if (enabled) next[field] = field === 'hidden' ? true : selected.value.source[field] ?? (field === 'tags' ? [] : '')
    else delete next[field]
    patch.value = JSON.stringify(next, null, 2)
  } catch { error.value = '请先修正 JSON 格式' }
}
function editField(field, value) {
  try { patch.value = JSON.stringify({ ...JSON.parse(patch.value), [field]: value }, null, 2) }
  catch { error.value = '请先修正高级编辑中的格式' }
}
async function save() {
  if (patchDirty.value) { applyPatch(); if (patchDirty.value) return }
  await perform(async () => {
    const validators = { galleries: validateOverrides, daily: validateDaily, translate: validateTranslate }
    validators[props.section](data.value)
    const result = await request('save', { resource: resource.value, data: data.value, sha: sha.value })
    sha.value = result.sha; original.value = JSON.stringify(data.value); lastCommit.value = result.commit
    notice.value = '已提交到 GitHub，等待发布完成后生效。' + (props.section === 'daily' ? ' 新规则在下一次每日抓取时使用；可前往任务页手动触发全量同步。' : props.section === 'translate' ? ' 模型及 JSON 模式需等待 Vercel 后端部署完成。' : '')
  })
}
function exportDraft() {
  const draft = { resource: resource.value, sha: sha.value, data: data.value, ...(patchDirty.value && selected.value ? { unappliedGallery: selected.value.gallery.gid, unappliedPatch: patch.value } : {}) }
  const url = URL.createObjectURL(new Blob([JSON.stringify(draft, null, 2)], { type: 'application/json' }))
  const a = document.createElement('a'); a.href = url; a.download = `${resource.value}-draft.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
}
function reload() { if (allowLeave()) perform(load) }
function getHistory() { perform(async () => { history.value = (await request('history', { resource: resource.value })).commits }) }
function preview(group) {
  const q = new URLSearchParams({ f_cats: String(1023 ^ group.categories), f_search: group.keyword, advsearch: '1' })
  for (const [field, param] of [['minPages', 'f_spf'], ['maxPages', 'f_spt'], ['minRating', 'f_srdd']]) if (group[field] !== null) q.set(param, String(group[field]))
  return `https://exhentai.org/?${q}`
}
function addGroup() { data.value.push({ name: '新筛选组', filters: [], keyword: '', categories: 6, minPages: null, maxPages: null, minRating: null, cutoffDays: 10 }) }
function removeGroup(index) { if (window.confirm('删除此筛选组？提交后生效。')) data.value.splice(index, 1) }
function dispatch(workflow) {
  if (!window.confirm('确认启动此任务？抓取任务可能需要几分钟，并在完成后发布网站。')) return
  perform(async () => { await request('dispatch', { workflow }); await load(); notice.value = '任务已受理，运行记录可能稍后出现。点击刷新查看。' })
}
function rerun(runId) { perform(async () => { await request('rerun', { runId }); notice.value = '已受理重跑请求，请稍后刷新。' }) }
function replace() {
  if (!window.confirm(`替换 ${secretPlatform.value} 的 ${secretName.value}？旧值不会显示，也无法从这里恢复。`)) return
  perform(async () => {
    try { const result = await request('replace-secret', { platform: secretPlatform.value, name: secretName.value, value: secretValue.value }); notice.value = result.message }
    finally { secretValue.value = '' }
    platforms.value = await request('platforms')
  })
}
function redeploy() {
  if (!window.confirm('重新部署 Vercel Production 后端以应用环境变量？')) return
  perform(async () => { backendDeployment.value = await request('redeploy-backend'); notice.value = '后端部署请求已受理，完成情况请查看 Vercel 控制台。' })
}
const formatDate = value => new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
</script>

<template>
  <section class="admin-card">
    <div class="admin-actions"><h2>{{ titles[section] }}</h2><div class="admin-toolbar">
      <template v-if="isEditor"><span class="muted">{{ dirty ? '有未保存修改' : '草稿已保存' }}</span><button :disabled="busy || !data" @click="exportDraft">导出草稿</button><button :disabled="busy" @click="getHistory">修改历史</button><button class="admin-primary" :disabled="busy || !dirty || !data" @click="save">提交并发布</button></template>
      <button :disabled="busy" @click="reload">{{ busy ? '处理中…' : '刷新 / 重新加载' }}</button>
    </div></div>
    <p v-if="error" class="admin-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="admin-notice" role="status">{{ notice }} <a v-if="lastCommit" :href="`https://github.com/ywryn/NoHentai/commit/${lastCommit}`" target="_blank" rel="noopener noreferrer">查看提交</a></p>

    <fieldset v-if="section === 'galleries' && data" :disabled="busy">
      <p class="muted">仅保存人工覆盖字段。抓取继续更新原始值；恢复来源值会移除对应覆盖。隐藏会从公开画廊及每日列表移除，printed 条目仍保留。</p>
      <form class="admin-search" @submit.prevent="page = 1; perform(search)"><input v-model="query" aria-label="搜索画廊" type="search" placeholder="ID、书名、上传者或标签" /><button>搜索</button></form>
      <div class="gallery-editor-layout">
        <aside><p class="muted">{{ total }} 条结果 · 第 {{ page }} 页</p>
          <div class="admin-gallery-list"><button v-for="item in items" :key="item.gallery.gid" :class="{ active: selected?.gallery.gid === item.gallery.gid }" @click="select(item)"><strong>{{ item.gallery.title_jpn || item.gallery.title }}</strong><span>{{ item.gallery.gid }} · {{ item.gallery.hidden ? '已隐藏' : item.gallery.category }} {{ data[String(item.gallery.gid)] ? '· 有人工覆盖' : '' }}</span></button></div>
          <div class="admin-toolbar"><button :disabled="page <= 1" @click="page--; perform(search)">上一页</button><button :disabled="page * 30 >= total" @click="page++; perform(search)">下一页</button></div>
        </aside>
        <div v-if="selected" class="admin-fields"><h3>画廊 {{ selected.gallery.gid }}</h3>
          <p class="muted">勾选要人工维护的字段。取消勾选后恢复使用来源值。</p>
          <div v-for="[field, label] in galleryFields" :key="field" class="override-field">
            <label class="override-toggle"><input type="checkbox" :checked="Object.hasOwn(patchValue, field)" @change="setField(field, $event.target.checked)" />人工维护{{ label }}</label>
            <template v-if="Object.hasOwn(patchValue, field)">
              <label v-if="field === 'hidden'" class="override-toggle"><input type="checkbox" :checked="patchValue.hidden" @change="editField(field, $event.target.checked)" />从公开画廊与每日列表隐藏</label>
              <label v-else-if="field === 'tags'">标签（每行一个，留空表示清空）<textarea class="small-textarea" :value="patchValue.tags?.join('\n')" @input="editField(field, $event.target.value.split('\n').map(t => t.trim()).filter(Boolean))" /></label>
              <label v-else-if="field === 'category'">分类<select :value="patchValue.category" @change="editField(field, $event.target.value)"><option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</option></select></label>
              <label v-else>{{ label }}<input :value="patchValue[field]" @input="editField(field, $event.target.value)" /></label>
            </template>
            <p v-else class="muted source-value">来源：{{ field === 'hidden' ? '正常展示' : Array.isArray(selected.source[field]) ? selected.source[field].join(' · ') : selected.source[field] || '未提供' }}</p>
          </div>
          <details><summary>高级编辑</summary><label>人工覆盖（JSON）<textarea v-model="patch" spellcheck="false" /></label></details>
          <div class="admin-toolbar"><button @click="applyPatch">应用到草稿</button><button @click="restore">全部恢复来源值</button></div>
          <details><summary>查看当前原始数据</summary><pre>{{ JSON.stringify(selected.source, null, 2) }}</pre></details>
        </div><p v-else class="muted">选择一条画廊查看并修改元数据。</p>
      </div>
    </fieldset>

    <fieldset v-if="section === 'daily' && data" :disabled="busy" class="admin-fields">
      <p class="muted">规则保存后在下次抓取使用。预览链接打开来源站点，回溯天数由抓取脚本执行。</p>
      <article v-for="(group, index) in data" :key="index" class="daily-rule admin-card">
        <div class="admin-actions"><h3>筛选组 {{ index + 1 }}</h3><button @click="removeGroup(index)">删除分组</button></div>
        <div class="admin-fields"><label>分组名称<input v-model="group.name" /></label><label>搜索语法<input v-model="group.keyword" /></label>
          <label>展示标签（每行一个）<textarea class="small-textarea" :value="group.filters.join('\n')" @input="group.filters = $event.target.value.split('\n').filter(Boolean)" /></label>
          <div><p>包含分类</p><div class="category-options"><label v-for="[name, bit] in categoryOptions" :key="bit" class="override-toggle"><input type="checkbox" :checked="Boolean(group.categories & bit)" @change="group.categories = $event.target.checked ? group.categories | bit : group.categories & ~bit" />{{ name }}</label></div></div>
          <div class="admin-grid"><label>回溯天数<input v-model.number="group.cutoffDays" type="number" min="1" max="365" /></label>
          <label>最少页数（空为不限）<input :value="group.minPages" type="number" min="1" @input="group.minPages = $event.target.value === '' ? null : Number($event.target.value)" /></label><label>最多页数（空为不限）<input :value="group.maxPages" type="number" min="1" @input="group.maxPages = $event.target.value === '' ? null : Number($event.target.value)" /></label>
          <label>最低评分<select v-model="group.minRating"><option :value="null">不限</option><option v-for="n in [2,3,4,5]" :key="n" :value="n">{{ n }}</option></select></label></div>
          <a :href="preview(group)" target="_blank" rel="noopener noreferrer">在来源站点预览搜索条件 ↗</a>
        </div>
      </article>
      <button :disabled="data.length >= 20" @click="addGroup">新增筛选组</button>
    </fieldset>

    <fieldset v-if="section === 'translate' && data" :disabled="busy" class="admin-fields">
      <p class="muted">模型和 JSON 模式随 Vercel 部署生效，默认 OCR 随前端发布生效。API Key 与服务地址在“凭证与测活”中管理。</p>
      <label>默认模型（空为沿用 LLM_MODEL 环境变量）<input :value="data.model" placeholder="例如 gpt-4o-mini" @input="data.model = $event.target.value || null" /></label>
      <label>默认 OCR<select v-model="data.defaultOcr"><option value="google">Google Vision（保留现有 Paddle 回退）</option><option value="paddle">PaddleOCR</option><option value="ocrspace">OCR.Space</option></select></label>
      <label>JSON 输出模式<select v-model="data.jsonMode"><option :value="null">沿用 LLM_JSON_MODE 环境变量</option><option :value="true">开启</option><option :value="false">关闭</option></select></label>
    </fieldset>

    <template v-if="section === 'tasks'">
      <div class="admin-card"><h3>当前前端发布</h3><p v-if="release">版本 <a :href="`https://github.com/ywryn/NoHentai/commit/${release.commit}`" target="_blank" rel="noopener noreferrer">{{ release.commit.slice(0, 12) }}</a> · 构建于 {{ formatDate(release.builtAt) }}（北京时间）</p><p v-else class="muted">当前线上版本尚无发布标记，部署本次改造后可显示。</p></div>
      <div class="admin-toolbar"><button v-for="[file, label] in workflows" :key="file" :disabled="busy" @click="dispatch(file)">{{ label }}</button></div>
      <div class="admin-table-wrap"><table><thead><tr><th>任务</th><th>状态</th><th>提交</th><th>更新时间（北京时间）</th><th>操作</th></tr></thead><tbody><tr v-for="run in runs" :key="run.id"><td>{{ run.name }}</td><td>{{ statuses[run.conclusion || run.status] || run.conclusion || run.status }}</td><td><code>{{ run.sha.slice(0, 8) }}</code></td><td>{{ formatDate(run.updatedAt) }}</td><td><a :href="run.url" target="_blank" rel="noopener noreferrer">步骤与日志</a> <button v-if="run.status === 'completed'" :disabled="busy" @click="rerun(run.id)">重跑</button></td></tr></tbody></table></div>
      <p v-if="!runs.length && !busy" class="muted">没有可显示的运行记录，或尚未加载成功。</p>
    </template>

    <template v-if="section === 'system'">
      <p class="muted">仅替换指定凭证，不读取旧值。GitHub 与 Vercel 独立更新，请分别核对结果；这里只修改 Vercel Production 环境。</p>
      <fieldset :disabled="busy" class="admin-fields">
        <div v-if="platforms" class="admin-grid"><div v-for="platform in ['github','vercel']" :key="platform"><h3>{{ platform }}</h3><p v-if="platforms[platform].error" class="admin-error">{{ platforms[platform].error }}</p><p v-for="s in platforms[platform].secrets" :key="s.name" class="secret-status"><code>{{ s.name }}</code><span>{{ s.configured === null ? '未知' : s.configured ? '已配置' : '未配置' }}</span></p></div></div>
        <form class="admin-fields" @submit.prevent="replace"><div class="admin-grid"><label>目标平台<select v-model="secretPlatform" @change="secretName = ''; secretValue = ''"><option value="github">GitHub Actions</option><option value="vercel">Vercel Production</option></select></label><label>配置项<select v-model="secretName" required><option value="" disabled>选择配置项</option><option v-for="s in secretOptions" :key="s.name" :value="s.name">{{ s.name }}</option></select></label></div>
          <label>替换为新值<input v-model="secretValue" type="password" autocomplete="off" required maxlength="16000" /></label><button :disabled="!secretName || !secretValue || !platforms?.[secretPlatform]?.available">替换所选凭证</button>
        </form>
        <button @click="redeploy">重新部署 Vercel 后端</button><a v-if="backendDeployment?.url" :href="backendDeployment.url" target="_blank" rel="noopener noreferrer">打开新部署</a>
        <hr /><div class="admin-actions"><h3>即时测活</h3><button @click="perform(async () => { health = await request('health') })">运行检查</button></div>
        <p class="muted">检查首页、画廊数据与后端鉴权接口的可达性，不消耗 OCR / 翻译额度。第三方服务凭证是否有效仍需实际业务调用确认。</p>
        <p v-if="health">检查于 {{ formatDate(health.checkedAt) }}（北京时间）</p>
        <div v-if="health" class="admin-table-wrap"><table><thead><tr><th>服务</th><th>结果</th><th>状态码</th><th>耗时</th></tr></thead><tbody><tr v-for="check in health.checks" :key="check.name"><td>{{ check.name }}</td><td>{{ check.ok ? '可达' : '异常' }}</td><td>{{ check.status || '连接失败' }}</td><td>{{ check.ms }} ms</td></tr></tbody></table></div>
      </fieldset>
    </template>

    <details v-if="history.length" open class="admin-history"><summary>最近修改（回滚可在仓库中创建还原提交）</summary><ul><li v-for="c in history" :key="c.sha"><a :href="c.url" target="_blank" rel="noopener noreferrer">{{ c.message }}</a> · {{ formatDate(c.date) }}</li></ul></details>
  </section>
</template>

<style scoped>
.admin-search { display:flex; gap:10px; margin:18px 0; }.admin-search input { flex:1; }
.gallery-editor-layout { display:grid; grid-template-columns:minmax(240px, 1fr) minmax(0, 2fr); gap:24px; }
.admin-gallery-list { max-height:580px; overflow:auto; display:grid; gap:8px; margin-bottom:12px; }
.admin-gallery-list button { text-align:left; display:grid; gap:6px; }.admin-gallery-list strong { font-size:13px; line-height:1.5; overflow-wrap:anywhere; }.admin-gallery-list span { font-size:12px; color:var(--muted-color); }
.admin-gallery-list button.active { border-color:var(--primary-color); background:var(--primary-soft-bg); }
.small-textarea { min-height:100px; }.daily-rule { margin:0; }.secret-status { display:flex; justify-content:space-between; gap:8px; font-size:12px; overflow-wrap:anywhere; }.secret-status span { white-space:nowrap; }.admin-history { margin-top:24px; }.admin-history li { margin:10px 0; }
.override-field { border-bottom:1px solid var(--row-border); padding-bottom:14px; display:grid; gap:12px; }.admin-shell .override-toggle { display:flex; align-items:center; gap:8px; }.source-value { margin:0; overflow-wrap:anywhere; }.category-options { display:flex; flex-wrap:wrap; gap:12px 20px; }
@media(max-width:800px) { .gallery-editor-layout { grid-template-columns:1fr; }.admin-gallery-list { max-height:300px; } }
</style>
