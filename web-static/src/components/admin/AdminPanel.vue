<script setup>
import { computed, inject, ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { validateOverrides, validateDaily, validateTranslate, CATEGORIES } from '../../../../shared/adminData.js'
import AdminIcon from './AdminIcon.vue'
import AdminPanePlaceholder from './AdminPanePlaceholder.vue'

const props = defineProps({ adminPassword: { type: String, required: true }, section: { type: String, required: true } })
const confirm = inject('adminConfirm')
const openNavigation = inject('adminOpenNavigation')
const detailPane = ref(null)
const API_BASE = import.meta.env.VITE_API_BASE || 'https://no-hentai.vercel.app'
const resource = computed(() => props.section === 'galleries' ? 'overrides' : props.section)
const isEditor = computed(() => ['galleries', 'daily', 'translate'].includes(props.section))
const data = ref(null), sha = ref(''), original = ref(''), busy = ref(false), initial = ref(true), error = ref(''), notice = ref(''), lastCommit = ref('')
const writing = ref(false), activity = ref('load')
const saving = computed(() => busy.value && activity.value === 'save')
const reading = computed(() => busy.value && ['load', 'search'].includes(activity.value))
const searching = computed(() => busy.value && activity.value === 'search')
const editorStatus = computed(() => saving.value ? '正在保存…' : initial.value ? '正在加载…' : reading.value ? (searching.value ? '正在搜索…' : '正在刷新…') : !data.value ? '内容未加载' : dirty.value ? (props.section === 'galleries' ? `${changedCount.value} 个画廊有未保存修改` : '有未保存修改') : lastCommit.value ? '已保存，等待发布' : '没有待保存的修改')
watch(data, () => { if (dirty.value) { notice.value = ''; lastCommit.value = '' } }, { deep: true })
const query = ref(''), page = ref(1), total = ref(0), items = ref([]), selected = ref(null), patch = ref('{}'), patchError = ref('')
const dirty = computed(() => Boolean(patchError.value) || (data.value !== null && JSON.stringify(data.value) !== original.value))
const galleryFields = [['title', '展示标题'], ['title_jpn', '日文标题'], ['tags', '标签'], ['category', '分类'], ['uploader', '上传者']]
const categoryOptions = [['Misc', 1], ['Doujinshi', 2], ['Manga', 4], ['Artist CG', 8], ['Game CG', 16], ['Image Set', 32], ['Cosplay', 64], ['Asian Porn', 128], ['Non-H', 256], ['Western', 512]]
const activeGroup = ref(0), detailOpen = ref(false), history = ref([]), historyDialog = ref(null), credentialDialog = ref(null)
const group = computed(() => props.section === 'daily' ? data.value?.[activeGroup.value] : null)
const lastRefreshed = ref('')
let refreshTimer, polling = false
const runs = ref([]), runFilter = ref('all'), release = ref(null), platforms = ref(null), health = ref(null), backendDeployment = ref(null)
const overviewErrors = ref([]), secretPlatform = ref('github'), secretName = ref(''), secretValue = ref('')
const secretLabels = { EXHENTAI_BASE_URL: '抓取来源地址', EXHENTAI_COOKIE_MEMBER_ID: '登录 Cookie · Member ID', EXHENTAI_COOKIE_PASS_HASH: '登录 Cookie · Pass Hash', EXHENTAI_COOKIE_IGNEOUS: '登录 Cookie · Igneous', LLM_API_KEY: '翻译服务 API Key', LLM_API_BASE: '翻译服务地址', LLM_MODEL: '环境默认模型', LLM_JSON_MODE: '环境 JSON 模式', GOOGLE_VISION_API_KEY: 'Google Vision API Key', PADDLEOCR_API_TOKEN: 'PaddleOCR Token', OCR_SPACE_KEY: 'OCR.Space API Key', TRANS_PASSWORD: '翻译工作台密码' }
const titles = { overview: ['站点概览', '内容、配置与运行状态，一目了然。'], galleries: ['画廊', '维护展示信息，保留来源数据的自动更新。'], daily: ['每日筛选', '组织搜索规则，让每日发现更符合你的偏好。'], translate: ['翻译配置', '为翻译工作台选择合适的默认能力。'], tasks: ['任务与发布', '运行同步任务，跟踪每一次内容发布。'], health: ['服务测活', '检查网站与接口是否可达，快速定位连接问题。'], credentials: ['凭证管理', '集中查看平台连接，安全替换服务凭证。'] }
const workflows = [ ['deploy.yml', '发布前端', '发布仓库中已保存的内容与配置', 'arrow'], ['sync.yml', '全量同步', '同步收藏、标签翻译和每日结果后发布', 'refresh'], ['sync-ex.yml', '同步画廊', '更新收藏画廊并发布前端', 'gallery'], ['sync-translations.yml', '同步标签翻译', '更新标签翻译并发布前端', 'translate'] ]
const statuses = { queued: '排队中', in_progress: '运行中', completed: '已完成', waiting: '等待中', success: '成功', failure: '失败', cancelled: '已取消', timed_out: '超时', action_required: '需要处理', skipped: '已跳过' }
const visibleRuns = computed(() => runs.value.filter(r => runFilter.value === 'all' || (runFilter.value === 'failure' ? ['failure', 'timed_out', 'action_required'].includes(r.conclusion) : r.conclusion === runFilter.value || r.status === runFilter.value)))
const failures = computed(() => runs.value.filter(r => ['failure', 'timed_out', 'action_required'].includes(r.conclusion)).length)
const changedCount = computed(() => {
  if (props.section !== 'galleries' || !data.value) return 0
  const before = JSON.parse(original.value || '{}')
  return new Set([...Object.keys(data.value), ...Object.keys(before)].filter(id => JSON.stringify(data.value[id]) !== JSON.stringify(before[id]))).size
})
const healthOk = computed(() => health.value?.checks.filter(c => c.ok).length || 0)
const safePatch = computed(() => selected.value ? data.value?.[String(selected.value.gallery.gid)] || {} : {})
const selectedGallery = computed(() => selected.value ? { ...selected.value.source, ...safePatch.value } : null)
const missingVercel = computed(() => platforms.value?.vercel?.missing?.length ? platforms.value.vercel.missing : ['ADMIN_VERCEL_TOKEN', 'ADMIN_VERCEL_PROJECT_ID'])
async function request(action, body = {}) {
  const r = await fetch(`${API_BASE}/api/admin`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: props.adminPassword, action, ...body }) })
  const result = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(result.error || `请求失败（${r.status}）`)
  return result
}
async function perform(fn, write = false, operation = 'action') {
  if (busy.value) return
  busy.value = true; writing.value = write; activity.value = operation; error.value = ''; notice.value = ''
  try { await fn() } catch (e) { error.value = e.message || '请求失败，请稍后重试' }
  finally { busy.value = false; writing.value = false; initial.value = false }
}
async function search(targetPage = 1) {
  const result = await request('gallery-search', { query: query.value, page: targetPage })
  items.value = result.items; total.value = result.total; page.value = targetPage
}
async function loadRelease() {
  const r = await fetch(`${import.meta.env.BASE_URL}data/release.json?ts=${Date.now()}`, { cache: 'no-store' })
  if (!r.ok) throw new Error('暂时无法读取线上发布版本')
  release.value = await r.json()
}
async function load() {
  if (isEditor.value) {
    // Publish one complete snapshot, never the editable metadata ahead of its list.
    const [result, gallery] = await Promise.all([
      request('load', { resource: resource.value }),
      props.section === 'galleries' ? request('gallery-search', { query: query.value, page: 1 }) : null,
    ])
    data.value = result.data; sha.value = result.sha; original.value = JSON.stringify(result.data)
    selected.value = null; patch.value = '{}'; patchError.value = ''; lastCommit.value = ''; detailOpen.value = false
    activeGroup.value = 0
    if (gallery) { items.value = gallery.items; total.value = gallery.total; page.value = 1 }
  } else if (props.section === 'tasks' || props.section === 'overview') {
    overviewErrors.value = []
    const results = await Promise.allSettled([request('runs'), loadRelease()])
    if (results[0].status === 'fulfilled') { runs.value = results[0].value.runs; lastRefreshed.value = new Date().toISOString() }
    else overviewErrors.value.push('运行记录暂时无法加载，请检查 GitHub Actions 权限后重试。')
    if (results[1].status === 'rejected') overviewErrors.value.push('暂时无法读取线上发布版本。')
  } else if (props.section === 'health') health.value = await request('health')
  else platforms.value = await request('platforms')
}
async function allowLeave() {
  if (writing.value) return false
  return !dirty.value || await confirm({ title: '离开前保存修改？', description: '当前修改尚未提交。返回编辑可以继续保存，也可以选择放弃修改后离开。', confirmLabel: '放弃并离开', danger: true })
}
onBeforeRouteLeave(allowLeave)
function beforeUnload(e) { if (dirty.value || writing.value) { e.preventDefault(); e.returnValue = '' } }
function shortcut(e) { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's' && isEditor.value) { e.preventDefault(); if (dirty.value && !busy.value) save() } }
window.addEventListener('beforeunload', beforeUnload); window.addEventListener('keydown', shortcut)
onBeforeUnmount(() => { window.removeEventListener('beforeunload', beforeUnload); window.removeEventListener('keydown', shortcut); clearInterval(refreshTimer) })
onMounted(() => {
  perform(load, false, 'load')
  if (['tasks', 'overview'].includes(props.section)) refreshTimer = setInterval(async () => {
    if (polling || busy.value || document.visibilityState !== 'visible' || !runs.value.some(r => ['queued', 'in_progress', 'waiting'].includes(r.status))) return
    polling = true
    try { runs.value = (await request('runs')).runs; lastRefreshed.value = new Date().toISOString(); await loadRelease() } catch { /* Keep the current records visible; manual retry remains available. */ } finally { polling = false }
  }, 15000)
})
function galleryValue(item) { return { ...item.source, ...(data.value?.[String(item.gallery.gid)] || {}) } }
function select(item) {
  if (patchError.value) { error.value = '请先修正高级编辑中的格式，再切换画廊。'; return }
  selected.value = item
  patch.value = JSON.stringify(data.value[String(item.gallery.gid)] || {}, null, 2)
  detailOpen.value = true
  nextTick(() => detailPane.value?.scrollTo({ top: 0, behavior: 'instant' }))
}
function updatePatch(next) {
  const id = String(selected.value.gallery.gid)
  validateOverrides({ [id]: next })
  if (Object.keys(next).length) data.value[id] = next
  else delete data.value[id]
  patch.value = JSON.stringify(next, null, 2); patchError.value = ''
}
function editField(field, value) { updatePatch({ ...safePatch.value, [field]: value }) }
function resetField(field) { const next = { ...safePatch.value }; delete next[field]; updatePatch(next) }
function advancedPatch(value) {
  patch.value = value
  try { updatePatch(JSON.parse(value)) } catch (e) { patchError.value = e.message }
}
async function restore() {
  if (await confirm({ title: '恢复所有来源值？', description: '该画廊的人工修改将从草稿移除，保存后公开页面使用最新来源信息。', confirmLabel: '恢复来源值' })) updatePatch({})
}
async function save() {
  if (busy.value || !dirty.value || patchError.value) return
  const snapshot = JSON.parse(JSON.stringify(data.value))
  await perform(async () => {
    const validators = { galleries: validateOverrides, daily: validateDaily, translate: validateTranslate }
    validators[props.section](snapshot)
    const result = await request('save', { resource: resource.value, data: snapshot, sha: sha.value })
    sha.value = result.sha; original.value = JSON.stringify(snapshot); lastCommit.value = result.commit
    notice.value = props.section === 'daily' ? '规则已保存，将在下次同步每日结果时使用。' : props.section === 'translate' ? '配置已保存，等待前端与后端部署完成后生效。' : '修改已保存，等待前端发布完成后生效。'
  }, true, 'save')
}
function exportDraft() {
  const draft = { resource: resource.value, sha: sha.value, data: data.value, ...(patchError.value ? { unappliedGallery: selected.value?.gallery.gid, unappliedPatch: patch.value } : {}) }
  const url = URL.createObjectURL(new Blob([JSON.stringify(draft, null, 2)], { type: 'application/json' }))
  const a = document.createElement('a'); a.href = url; a.download = `${resource.value}-draft.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
}
async function reload() { if (await allowLeave()) perform(load, false, 'load') }
function getHistory() { perform(async () => { history.value = (await request('history', { resource: resource.value })).commits; historyDialog.value.showModal() }) }
function preview(g) {
  const q = new URLSearchParams({ f_cats: String(1023 ^ g.categories), f_search: g.keyword, advsearch: '1' })
  for (const [field, param] of [['minPages', 'f_spf'], ['maxPages', 'f_spt'], ['minRating', 'f_srdd']]) if (g[field] !== null) q.set(param, String(g[field]))
  return `https://exhentai.org/?${q}`
}
function selectGroup(index) { activeGroup.value = index; detailOpen.value = true; nextTick(() => detailPane.value?.scrollTo({ top: 0, behavior: 'instant' })) }
function addGroup() { data.value.push({ name: '新筛选组', filters: [], keyword: '', categories: 6, minPages: null, maxPages: null, minRating: null, cutoffDays: 10 }); selectGroup(data.value.length - 1) }
async function removeGroup() {
  if (await confirm({ title: '删除这个筛选组？', description: `“${group.value.name}”会从规则中移除，保存后生效。`, confirmLabel: '删除分组', danger: true })) { data.value.splice(activeGroup.value, 1); activeGroup.value = Math.max(0, activeGroup.value - 1); detailOpen.value = false }
}
function moveGroup(direction) { const to = activeGroup.value + direction; if (to < 0 || to >= data.value.length) return; const [g] = data.value.splice(activeGroup.value, 1); data.value.splice(to, 0, g); activeGroup.value = to }
async function dispatch(workflow) {
  const label = workflows.find(w => w[0] === workflow)?.[1]
  if (!await confirm({ title: `启动${label}？`, description: '任务将使用已保存的配置运行，并在成功后发布网站。当前浏览器里未保存的修改不会被使用。', confirmLabel: '启动任务' })) return
  perform(async () => { await request('dispatch', { workflow }); await load(); notice.value = '任务已启动，运行记录可能稍后出现。刷新即可查看最新状态。' })
}
async function rerun(runId) {
  if (!await confirm({ title: '重新运行此任务？', description: '将重新执行这个任务的全部步骤。', confirmLabel: '重新运行' })) return
  perform(async () => { await request('rerun', { runId }); notice.value = '重跑请求已受理，请稍后刷新运行记录。' })
}
function openCredential(platform, name) { secretPlatform.value = platform; secretName.value = name; secretValue.value = ''; credentialDialog.value.showModal() }
async function replace() {
  await perform(async () => {
    try { const result = await request('replace-secret', { platform: secretPlatform.value, name: secretName.value, value: secretValue.value }); notice.value = result.message; credentialDialog.value.close() }
    finally { secretValue.value = '' }
    platforms.value = await request('platforms')
  }, true)
}
async function redeploy() {
  if (!await confirm({ title: '重新部署后端？', description: '部署完成后，Vercel Production 中刚更新的环境变量才会应用到后端。', confirmLabel: '开始部署' })) return
  perform(async () => { backendDeployment.value = await request('redeploy-backend'); notice.value = '后端部署已受理，可前往 Vercel 查看进度。' })
}
const formatDate = value => value ? new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) : '—'
const statusTone = r => ['failure', 'timed_out', 'action_required'].includes(r.conclusion) ? 'danger' : r.conclusion === 'success' ? 'success' : ['queued', 'in_progress', 'waiting'].includes(r.status) ? 'accent' : 'neutral'
</script>

<template>
  <div class="a-page" :aria-busy="busy">
    <header class="a-page-heading"><div class="a-page-title"><button class="a-button a-icon-button a-mobile-menu" aria-label="打开管理导航" @click="openNavigation"><AdminIcon name="menu" /></button><div><h1>{{ titles[section][0] }}</h1><template v-if="isEditor"><div class="a-heading-status" role="status"><span :class="['a-save-indicator', { 'is-dirty': dirty, 'is-loading': reading || !data }]" /><div><strong>{{ editorStatus }}</strong><small v-if="data">{{ dirty ? '离开页面前请保存。' : section === 'daily' ? '新规则在下次每日同步时使用。' : '线上内容以部署完成的版本为准。' }}</small></div></div></template><p v-else>{{ titles[section][1] }}</p></div></div><div class="a-heading-actions"><button v-if="isEditor" class="a-button" aria-label="修改历史" :disabled="busy || !data" @click="getHistory"><AdminIcon name="clock" :size="16" /><span class="a-secondary-action-label">修改历史</span></button><button class="a-button" :aria-label="section === 'health' ? '重新检测' : '刷新'" :disabled="busy" @click="reload"><AdminIcon name="refresh" :size="16" :class="{ 'a-spin': reading }" /><span class="a-secondary-action-label">{{ section === 'health' ? '重新检测' : '刷新' }}</span></button><template v-if="isEditor"><button class="a-button a-heading-export" aria-label="导出草稿" :disabled="busy || !data" @click="exportDraft"><AdminIcon name="download" :size="16" /><span class="a-secondary-action-label">导出草稿</span></button><button class="a-button a-primary" :disabled="busy || !data || !dirty || Boolean(patchError)" @click="save"><span v-if="saving" class="a-spinner" /><AdminIcon v-else name="check" :size="17" />{{ saving ? '正在保存…' : '保存更改' }}</button></template></div></header>
    <div v-if="error" class="a-alert a-alert-error" role="alert"><AdminIcon name="info" /><div>{{ error }}<button v-if="isEditor && data" class="a-text-button" @click="exportDraft">导出当前草稿</button></div></div>
    <div v-if="notice" class="a-alert a-alert-success" role="status"><AdminIcon name="check" /><div>{{ notice }} <RouterLink v-if="lastCommit" to="/admin/tasks">查看发布进度 →</RouterLink><a v-if="lastCommit" :href="`https://github.com/ywryn/NoHentai/commit/${lastCommit}`" target="_blank" rel="noopener noreferrer">查看提交</a></div></div>
    <div v-for="message in overviewErrors" :key="message" class="a-alert a-alert-warning" role="alert"><AdminIcon name="info" />{{ message }}</div>
    <div v-if="initial && !isEditor" class="a-loading-state" role="status"><span class="a-spinner" /><p>正在加载{{ titles[section][0] }}…</p><div class="a-skeleton" /><div class="a-skeleton" /><div class="a-skeleton" /></div>


    <template v-if="section === 'overview' && !initial">
      <div class="a-stat-grid"><article class="a-card a-stat"><span><AdminIcon name="arrow" />当前前端版本</span><strong class="a-mono">{{ release?.commit?.slice(0,8) || '暂无数据' }}</strong><small>{{ release ? formatDate(release.builtAt) : '发布信息暂不可用' }}</small></article><article class="a-card a-stat"><span><AdminIcon name="tasks" />最近任务</span><strong>{{ runs.length }}</strong><small>最近获取的运行记录</small></article><article class="a-card a-stat"><span><AdminIcon name="info" />需要关注</span><strong :class="{ 'a-danger-text': failures }">{{ failures }}</strong><small>最近记录中的失败或超时任务</small></article></div>
      <section class="a-card"><div class="a-section-heading"><div><h2>继续你的工作</h2><p>常用入口，直接开始。</p></div></div><div class="a-quick-grid"><RouterLink v-for="[path,label,description,icon] in [['galleries','维护画廊','编辑展示信息与可见性','gallery'],['printed','整理实体书单','更新书目与画廊关联','book'],['daily','调整每日筛选','管理搜索条件与范围','filter'],['health','检查服务状态','检查站点与接口可达性','pulse']]" :key="path" :to="`/admin/${path}`" class="a-quick-link"><span class="a-icon-tile"><AdminIcon :name="icon" /></span><div><strong>{{ label }}</strong><p>{{ description }}</p></div><AdminIcon name="chevron" :size="16" /></RouterLink></div></section>
      <section class="a-card"><div class="a-section-heading"><div><h2>最近运行</h2><p>查看同步与发布的最新结果。</p></div><RouterLink to="/admin/tasks" class="a-text-link">全部任务 <AdminIcon name="arrow" :size="15" /></RouterLink></div><div v-if="runs.length" class="a-recent-runs"><a v-for="run in runs.slice(0,5)" :key="run.id" :href="run.url" target="_blank" rel="noopener noreferrer"><span class="a-run-icon"><AdminIcon :name="run.conclusion === 'success' ? 'check' : 'tasks'" /></span><div><strong>{{ run.name }}</strong><small>{{ formatDate(run.updatedAt) }}</small></div><span class="a-badge" :class="`a-badge-${statusTone(run)}`">{{ statuses[run.conclusion || run.status] || run.status }}</span><AdminIcon name="arrow" :size="15" /></a></div><div v-else class="a-empty"><AdminIcon name="tasks" :size="28" /><p>暂无可显示的运行记录</p></div></section>
      <div class="a-inline-note"><AdminIcon name="info" :size="17" /><p>编辑后先保存，再等待发布完成。每日规则将在下次同步时使用。</p></div>
    </template>

    <template v-if="section === 'galleries'">
      <div class="a-master-detail" :class="{ 'a-detail-open': detailOpen }">
        <section class="a-card a-master-list"><form class="a-search-row" @submit.prevent="perform(() => search(1), false, 'search')"><div class="a-search-input"><AdminIcon name="search" :size="18" /><input v-model="query" :disabled="busy || !data" aria-label="搜索画廊" type="search" placeholder="搜索标题、ID、上传者或标签" /></div><button class="a-button" :disabled="busy || !data">{{ searching ? '搜索中…' : '搜索' }}</button></form><div class="a-list-caption"><span>{{ !data && reading ? '正在加载画廊…' : !data ? '尚未加载' : `${total.toLocaleString()} 个画廊` }}</span><span v-if="data">{{ searching ? '更新结果中…' : `第 ${page} 页` }}</span></div>
          <div class="a-gallery-list" :aria-busy="reading"><AdminPanePlaceholder v-if="!data" :loading="initial || reading" variant="list" label="正在加载画廊列表…" @retry="reload" /><button v-for="item in items" :key="item.gallery.gid" class="a-gallery-row" :class="{ 'is-selected': selected?.gallery.gid === item.gallery.gid }" :disabled="busy" @click="select(item)"><span class="a-cover"><img v-if="item.gallery.thumb" :src="item.gallery.thumb" alt="" loading="lazy" referrerpolicy="no-referrer" /><AdminIcon v-else name="gallery" /></span><span class="a-gallery-copy"><strong>{{ galleryValue(item).title_jpn || galleryValue(item).title }}</strong><span>#{{ item.gallery.gid }}<i>·</i>{{ galleryValue(item).category }}</span><span class="a-row-badges"><span v-if="data[String(item.gallery.gid)]" class="a-badge a-badge-accent">人工编辑</span><span v-if="galleryValue(item).hidden" class="a-badge a-badge-neutral">已隐藏</span></span></span><AdminIcon name="chevron" :size="16" /></button><div v-if="data && !reading && !items.length" class="a-empty"><AdminIcon name="search" :size="28" /><h3>没有找到画廊</h3><p>试试更短的标题或画廊 ID。</p><button v-if="query" class="a-button" @click="query = ''; perform(() => search(1), false, 'search')">清除搜索</button></div></div>
          <footer class="a-pagination"><button class="a-button" :disabled="busy || !data || page <= 1" @click="perform(() => search(page-1), false, 'search')"><AdminIcon name="back" :size="16" />上一页</button><span>{{ data ? `${page} / ${Math.max(1,Math.ceil(total/30))}` : '—' }}</span><button class="a-button" :disabled="busy || !data || page*30 >= total" @click="perform(() => search(page+1), false, 'search')">下一页<AdminIcon name="chevron" :size="16" /></button></footer>
        </section>
        <section ref="detailPane" class="a-card a-detail-pane"><AdminPanePlaceholder v-if="!data" :loading="initial || reading" label="正在准备画廊编辑区…" @retry="reload" /><template v-else-if="selected"><div class="a-detail-heading"><button class="a-button a-ghost a-mobile-back" @click="detailOpen = false"><AdminIcon name="back" :size="16" />返回画廊</button><div class="a-section-heading"><div><span class="a-eyebrow">GALLERY #{{ selected.gallery.gid }}</span><h2>编辑画廊</h2></div><span class="a-badge" :class="Object.keys(safePatch).length ? 'a-badge-accent' : 'a-badge-neutral'">{{ Object.keys(safePatch).length ? '人工编辑' : '跟随来源' }}</span></div><p class="a-muted">直接编辑即可。修改会保留在本页，点击标题区的保存按钮后提交。</p></div>
          <fieldset :disabled="busy" class="a-form-stack">
            <div v-for="[field,label] in galleryFields" :key="field" class="a-field-block"><label :for="`gallery-${field}`" class="a-field-label">{{ label }}</label><textarea v-if="field === 'tags'" :id="`gallery-${field}`" rows="4" :value="selectedGallery.tags?.join('\n')" @input="editField(field,$event.target.value.split('\n').map(t=>t.trim()).filter(Boolean))" /><select v-else-if="field === 'category'" :id="`gallery-${field}`" :value="selectedGallery.category" @change="editField(field,$event.target.value)"><option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</option></select><input v-else :id="`gallery-${field}`" :value="selectedGallery[field] || ''" @input="editField(field,$event.target.value)" /><div class="a-field-foot"><span>{{ Object.hasOwn(safePatch,field) ? '已人工修改' : '跟随来源更新' }}{{ field === 'tags' ? ' · 每行一个标签' : '' }}</span><button v-if="Object.hasOwn(safePatch,field)" type="button" class="a-text-button" @click="resetField(field)">恢复来源值</button></div></div>
            <label class="a-switch-row"><div><strong>在公开列表中显示</strong><span>关闭后，从画廊和每日列表隐藏。</span></div><input type="checkbox" class="a-switch" :checked="!selectedGallery.hidden" @change="editField('hidden',!$event.target.checked)" /></label>
            <details class="a-disclosure"><summary>高级编辑与来源数据</summary><label class="a-field">人工覆盖（JSON）<textarea class="a-code" :value="patch" rows="8" spellcheck="false" @input="advancedPatch($event.target.value)" /></label><p v-if="patchError" class="a-danger-text" role="alert">{{ patchError }}</p><details><summary>查看来源数据</summary><pre>{{ JSON.stringify(selected.source,null,2) }}</pre></details><button class="a-button" @click="restore">全部恢复来源值</button></details>
          </fieldset></template><div v-else class="a-empty a-empty-detail"><span class="a-icon-tile"><AdminIcon name="gallery" :size="28" /></span><h2>选择一个画廊</h2><p>从左侧选择记录，编辑标题、标签与展示状态。<br />人工修改不会被自动抓取覆盖。</p></div></section>
      </div>
    </template>

    <template v-if="section === 'daily'">
      <div class="a-inline-note"><AdminIcon name="info" :size="17" /><p>规则保存后用于下一次每日同步。<RouterLink to="/admin/tasks">前往运行同步 →</RouterLink></p></div>
      <div class="a-master-detail a-rules-layout" :class="{ 'a-detail-open': detailOpen }"><section class="a-card a-master-list"><div class="a-section-heading"><h2>筛选组 <span class="a-count">{{ data ? data.length : '…' }}</span></h2><button class="a-button a-icon-button" :disabled="busy || !data || data.length >= 20" aria-label="新增筛选组" @click="addGroup"><AdminIcon name="plus" :size="18" /></button></div><div class="a-rule-list"><AdminPanePlaceholder v-if="!data" :loading="initial || reading" variant="list" label="正在加载每日规则…" @retry="reload" /><button v-for="(g,index) in data || []" :key="index" class="a-rule-row" :class="{ 'is-selected': activeGroup === index }" :disabled="busy" @click="selectGroup(index)"><span class="a-rule-number">{{ String(index+1).padStart(2,'0') }}</span><div><strong>{{ g.name || '未命名筛选组' }}</strong><small>最近 {{ g.cutoffDays }} 天 · {{ g.minRating ? `${g.minRating} 星以上` : '不限评分' }}</small><span class="a-tag-row"><span v-for="tag in g.filters.slice(0,3)" :key="tag" class="a-tag">{{ tag }}</span></span></div><AdminIcon name="chevron" :size="16" /></button></div><button class="a-add-row" :disabled="busy || !data || data.length >= 20" @click="addGroup"><AdminIcon name="plus" :size="17" />新增筛选组</button></section>
        <section ref="detailPane" class="a-card a-detail-pane"><AdminPanePlaceholder v-if="!data" :loading="initial || reading" label="正在准备规则编辑区…" @retry="reload" /><template v-else-if="group"><button class="a-button a-ghost a-mobile-back" @click="detailOpen = false"><AdminIcon name="back" :size="16" />返回筛选组</button><div class="a-section-heading"><div><span class="a-eyebrow">FILTER GROUP {{ String(activeGroup+1).padStart(2,'0') }}</span><h2>编辑筛选条件</h2></div><div class="a-toolbar"><button class="a-button a-icon-button" aria-label="上移筛选组" :disabled="busy || activeGroup === 0" @click="moveGroup(-1)">↑</button><button class="a-button a-icon-button" aria-label="下移筛选组" :disabled="busy || activeGroup === data.length-1" @click="moveGroup(1)">↓</button></div></div><fieldset :disabled="busy" class="a-form-stack"><label class="a-field">分组名称<input v-model="group.name" placeholder="为这组规则命名" /></label><label class="a-field">搜索条件<textarea v-model="group.keyword" rows="3" placeholder="输入来源站点支持的搜索语法" /><span class="a-field-help">沿用来源站点的标签与排除语法。</span></label><div class="a-field"><span>包含分类</span><div class="a-category-grid"><label v-for="[name,bit] in categoryOptions" :key="bit" class="a-check-chip"><input type="checkbox" :checked="Boolean(group.categories & bit)" @change="group.categories = $event.target.checked ? group.categories | bit : group.categories & ~bit" />{{ name }}</label></div></div><div class="a-form-grid"><label class="a-field">回溯天数<input v-model.number="group.cutoffDays" type="number" min="1" max="365" /></label><label class="a-field">最低评分<select v-model="group.minRating"><option :value="null">不限评分</option><option v-for="n in [2,3,4,5]" :key="n" :value="n">{{ n }} 星以上</option></select></label><label class="a-field">最少页数<input :value="group.minPages" type="number" min="1" placeholder="不限" @input="group.minPages = $event.target.value === '' ? null : Number($event.target.value)" /></label><label class="a-field">最多页数<input :value="group.maxPages" type="number" min="1" placeholder="不限" @input="group.maxPages = $event.target.value === '' ? null : Number($event.target.value)" /></label></div><label class="a-field">展示标签<textarea rows="3" :value="group.filters.join('\n')" @input="group.filters = $event.target.value.split('\n').filter(Boolean)" /><span class="a-field-help">每行一个，用于每日页面的筛选说明。</span></label><div class="a-rule-footer"><a class="a-button" :href="preview(group)" target="_blank" rel="noopener noreferrer"><AdminIcon name="arrow" :size="16" />预览搜索</a><button class="a-text-button a-danger-text" @click="removeGroup">删除筛选组</button></div></fieldset></template><div v-else class="a-empty"><h2>添加第一个筛选组</h2><p>至少保留一组规则后才能保存。</p><button class="a-button" @click="addGroup">新增筛选组</button></div></section></div>
    </template>

    <template v-if="section === 'translate'">
      <section class="a-card a-settings-card"><div class="a-settings-intro"><span class="a-icon-tile"><AdminIcon name="translate" /></span><h2>翻译模型</h2><p>设置工作台默认使用的模型与输出格式。</p><span class="a-badge a-badge-neutral">后端部署后生效</span></div><AdminPanePlaceholder v-if="!data" :loading="initial || reading" label="正在加载模型配置…" @retry="reload" /><fieldset v-else :disabled="busy" class="a-form-stack"><label class="a-field">默认模型<input aria-label="默认模型" :value="data.model" placeholder="沿用环境默认模型" @input="data.model = $event.target.value || null" /><span class="a-field-help">例如 gpt-4o-mini。留空时沿用已有服务配置。</span></label><label class="a-field">JSON 输出模式<select v-model="data.jsonMode"><option :value="null">沿用环境配置</option><option :value="true">开启结构化 JSON 输出</option><option :value="false">关闭</option></select><span class="a-field-help">仅在模型服务支持时开启。</span></label></fieldset></section>
      <section class="a-card a-settings-card"><div class="a-settings-intro"><span class="a-icon-tile"><AdminIcon name="search" /></span><h2>文字识别</h2><p>工作台初次打开时使用的 OCR 来源，仍可在工作台中切换。</p><span class="a-badge a-badge-neutral">前端发布后生效</span></div><AdminPanePlaceholder v-if="!data" :loading="initial || reading" label="正在加载识别配置…" @retry="reload" /><fieldset v-else :disabled="busy" class="a-ocr-options"><label v-for="[value,title,description] in [['google','Google Vision','优先使用 Vision，保留现有 Paddle 回退。'],['paddle','PaddleOCR','使用已配置的 PaddleOCR 服务。'],['ocrspace','OCR.Space','使用已配置的 OCR.Space 服务。']]" :key="value" class="a-radio-card" :class="{ 'is-selected': data.defaultOcr === value }"><input v-model="data.defaultOcr" type="radio" name="default-ocr" :value="value" /><div><strong>{{ title }}</strong><p>{{ description }}</p></div></label></fieldset></section>
      <RouterLink class="a-card a-linked-card" to="/admin/credentials"><AdminIcon name="key" /><div><strong>管理 API Key 与服务地址</strong><p>凭证单独管理，不会保存到公开配置中。</p></div><AdminIcon name="arrow" :size="18" /></RouterLink>
    </template>

    <template v-if="section === 'tasks' && !initial">
      <section class="a-release-card a-card"><span class="a-icon-tile"><AdminIcon name="arrow" /></span><div><span class="a-eyebrow">CURRENT FRONTEND RELEASE</span><h2>{{ release ? '当前前端版本' : '发布版本暂不可用' }}</h2><p>{{ release ? formatDate(release.builtAt) + ' 构建 · 北京时间' : '可在下方任务记录中查看部署结果。' }}</p></div><a v-if="release" class="a-badge a-badge-neutral a-mono" :href="`https://github.com/ywryn/NoHentai/commit/${release.commit}`" target="_blank" rel="noopener noreferrer">{{ release.commit.slice(0,8) }}<AdminIcon name="arrow" :size="13" /></a></section>
      <div class="a-workflow-grid"><button v-for="[file,label,description,icon] in workflows" :key="file" class="a-card a-workflow" :disabled="busy" @click="dispatch(file)"><AdminIcon :name="icon" :size="22" /><strong>{{ label }}</strong><p>{{ description }}</p><span>启动任务 <AdminIcon name="arrow" :size="15" /></span></button></div>
      <section class="a-card"><div class="a-section-heading"><div><h2>运行记录</h2><p v-if="lastRefreshed">更新于 {{ formatDate(lastRefreshed) }} · 任务运行时自动刷新</p></div><select v-model="runFilter" aria-label="筛选运行状态" class="a-compact-select"><option value="all">全部状态</option><option value="in_progress">运行中</option><option value="success">成功</option><option value="failure">需要关注</option></select></div><div class="a-run-list"><article v-for="run in visibleRuns" :key="run.id" class="a-run-row"><span class="a-run-icon"><AdminIcon :name="run.conclusion === 'success' ? 'check' : 'tasks'" /></span><div class="a-run-copy"><strong>{{ run.name }}</strong><small><code>{{ run.sha.slice(0,8) }}</code><span>·</span>{{ formatDate(run.updatedAt) }}</small></div><span class="a-badge" :class="`a-badge-${statusTone(run)}`">{{ statuses[run.conclusion || run.status] || run.status }}</span><div class="a-toolbar"><a :href="run.url" class="a-button a-small" target="_blank" rel="noopener noreferrer">查看日志<AdminIcon name="arrow" :size="13" /></a><button v-if="run.status === 'completed'" class="a-button a-small" :disabled="busy" @click="rerun(run.id)">重跑</button></div></article><div v-if="!visibleRuns.length" class="a-empty"><AdminIcon name="tasks" :size="30" /><h3>没有符合条件的任务</h3><p>切换筛选条件，或从上方启动一次任务。</p></div></div></section>
    </template>

    <template v-if="section === 'health' && !initial">
      <div class="a-health-summary a-card"><span class="a-health-orb" :class="{ 'is-warning': !health || healthOk !== health.checks.length }"><AdminIcon name="pulse" :size="29" /></span><div><h2>{{ !health ? '等待检测结果' : healthOk === health.checks.length ? '服务连接正常' : '部分服务需要关注' }}</h2><p>{{ health ? `${healthOk} / ${health.checks.length} 项检查通过 · ${formatDate(health.checkedAt)}` : '点击重新检测，查看当前连接状态。' }}</p></div><span v-if="health" class="a-badge" :class="healthOk === health.checks.length ? 'a-badge-success' : 'a-badge-warning'">{{ healthOk === health.checks.length ? '全部可达' : '有异常' }}</span></div>
      <div v-if="health" class="a-health-grid"><article v-for="check in health.checks" :key="check.name" class="a-card a-health-card"><div><span class="a-icon-tile"><AdminIcon :name="check.name.includes('Vercel') ? 'shield' : 'gallery'" /></span><span class="a-badge" :class="check.ok ? 'a-badge-success' : 'a-badge-danger'">{{ check.ok ? '可达' : '连接异常' }}</span></div><h2>{{ check.name }}</h2><p class="a-health-url">{{ check.url }}</p><dl><div><dt>响应时间</dt><dd>{{ check.ms }}<small> ms</small></dd></div><div><dt>HTTP 状态</dt><dd>{{ check.status || '无响应' }}</dd></div></dl><p v-if="!check.ok" class="a-danger-text">连接未通过检查，可稍后重试并查看对应平台的运行日志。</p></article></div>
      <div class="a-inline-note"><AdminIcon name="info" :size="18" /><p>检测不需要 Vercel 管理凭证，也不会消耗翻译或 OCR 额度。可达性正常不代表第三方 Cookie 或密钥有效。</p></div><RouterLink class="a-text-link" to="/admin/credentials">需要管理平台环境变量？前往凭证管理 <AdminIcon name="arrow" :size="15" /></RouterLink>
    </template>

    <template v-if="section === 'credentials' && !initial">
      <div v-if="platforms" class="a-connection-grid"><section v-for="platform in ['github','vercel']" :key="platform" class="a-card a-connection-card"><div class="a-section-heading"><div class="a-platform-title"><span class="a-platform-mark">{{ platform === 'github' ? 'G' : '▲' }}</span><h2>{{ platform === 'github' ? 'GitHub Actions' : 'Vercel' }}</h2></div><span class="a-badge" :class="platforms[platform].available ? 'a-badge-success' : platforms[platform].code === 'not_configured' ? 'a-badge-neutral' : 'a-badge-warning'">{{ platforms[platform].available ? '已连接' : platforms[platform].code === 'not_configured' ? '未连接' : '连接需检查' }}</span></div>
        <template v-if="!platforms[platform].available"><div class="a-connection-help"><h3>{{ platform === 'vercel' && platforms.vercel.code === 'not_configured' ? '连接 Vercel 后管理环境变量' : '暂时无法读取平台配置' }}</h3><p>{{ platforms[platform].error }}</p><template v-if="platform === 'vercel' && platforms.vercel.code === 'not_configured'"><ol><li>在 Vercel 创建具有目标项目权限的 Token。</li><li>将以下缺失项添加到后端的 Production 环境变量。</li><li>重新部署后端，再回到这里刷新连接。</li></ol><div class="a-missing-vars"><code v-for="name in missingVercel" :key="name">{{ name }}</code></div><p class="a-field-help">Team 项目还可配置 ADMIN_VERCEL_TEAM_ID。已有管理密码和 GitHub Token 不包含 Vercel 管理授权。</p><a href="https://vercel.com/account/settings/tokens" target="_blank" rel="noopener noreferrer" class="a-button">打开 Vercel Token 设置<AdminIcon name="arrow" :size="15" /></a></template><p v-if="platform === 'vercel'" class="a-field-help">这不会影响内容编辑或服务测活。</p></div></template>
        <template v-else><p class="a-muted">{{ platform === 'github' ? '用于后续启动的抓取任务。' : '仅管理 Production 环境，修改后需要重新部署。' }}</p><div class="a-credential-list"><article v-for="s in platforms[platform].secrets" :key="s.name"><div><strong>{{ secretLabels[s.name] || s.name }}</strong><code>{{ s.name }}</code></div><span class="a-credential-state"><i :class="['a-dot', { 'a-dot-muted': !s.configured }]" />{{ s.configured ? '已配置' : '未配置' }}</span><button class="a-button a-small" :disabled="busy" :aria-label="`${platform} ${s.name} ${s.configured ? '替换' : '配置'}`" @click="openCredential(platform,s.name)">{{ s.configured ? '替换' : '配置' }}</button></article></div><div v-if="platform === 'vercel'" class="a-connection-actions"><button class="a-button" :disabled="busy" @click="redeploy"><AdminIcon name="refresh" :size="16" />重新部署后端</button><a v-if="backendDeployment?.url" :href="backendDeployment.url" target="_blank" rel="noopener noreferrer">查看新部署</a></div></template>
      </section></div><div class="a-inline-note"><AdminIcon name="shield" :size="18" /><p>仅展示配置状态，不读取旧密钥。各平台独立更新，替换后请确认对应的生效方式。</p></div>
    </template>

    <dialog ref="historyDialog" class="a-modal a-history-dialog" aria-labelledby="admin-history-title"><div class="a-section-heading"><div><span class="a-eyebrow">VERSION HISTORY</span><h2 id="admin-history-title">修改历史</h2></div><button class="a-button a-icon-button" aria-label="关闭修改历史" @click="historyDialog.close()"><AdminIcon name="close" /></button></div><p class="a-muted">查看最近提交。需要回滚时，可在仓库创建还原提交后重新发布。</p><div v-for="c in history" :key="c.sha" class="a-history-entry"><span class="a-history-dot" /><div><a :href="c.url" target="_blank" rel="noopener noreferrer">{{ c.message }}<AdminIcon name="arrow" :size="14" /></a><small>{{ formatDate(c.date) }} · {{ c.sha.slice(0,8) }}</small></div></div><p v-if="!history.length" class="a-muted">暂无修改记录。</p></dialog>
    <dialog ref="credentialDialog" class="a-modal a-credential-dialog" aria-labelledby="credential-title" @close="secretValue = ''" @cancel="e => { if (busy) e.preventDefault() }"><form @submit.prevent="replace"><div class="a-section-heading"><span class="a-icon-tile"><AdminIcon name="key" /></span><button type="button" class="a-button a-icon-button" aria-label="关闭凭证编辑" :disabled="busy" @click="credentialDialog.close()"><AdminIcon name="close" /></button></div><h2 id="credential-title">{{ secretLabels[secretName] || '更新凭证' }}</h2><p class="a-muted">{{ secretPlatform === 'github' ? 'GitHub Actions · 后续任务使用新值' : 'Vercel Production · 重新部署后生效' }}</p><code class="a-secret-key">{{ secretName }}</code><label class="a-field">新值<input v-model="secretValue" type="password" autocomplete="off" required maxlength="16000" placeholder="输入新的配置值" :disabled="busy" /></label><p class="a-field-help">旧值不会显示，请确认新值完整。保存后无法从这里恢复旧值。</p><div v-if="error" class="a-alert a-alert-error" role="alert">{{ error }}</div><div class="a-confirm-actions"><button type="button" class="a-button" :disabled="busy" @click="credentialDialog.close()">取消</button><button class="a-button a-primary" :disabled="busy || !secretValue">{{ busy ? '正在保存…' : '保存新值' }}</button></div></form></dialog>
  </div>
</template>
