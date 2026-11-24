<script setup>
import AdminMenuButton from './AdminMenuButton.vue'
import AdminTabs from './AdminTabs.vue'
import { ref, inject, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import {sameContent,scheduleDraft} from '@/utils/adminDrafts'
import AdminIcon from './AdminIcon.vue'
import {useRoute} from 'vue-router'
import { onBeforeRouteLeave } from 'vue-router'
import { adminRequest, formatDate } from '@/utils/adminApi'
const confirm = inject('adminConfirm')
const runs=ref([]),schedules=ref([]),error=ref(''),notice=ref(''),busy=ref(false),loading=ref(true),selected=ref(null),modal=ref(null)
const labels={all:'全量同步',favorites:'收藏同步',daily:'每日搜索',translations:'标签翻译'}
const taskIcons = { favorites: 'gallery', translations: 'translate', daily: 'filter' }
const states={queued:'排队中',in_progress:'执行中',success:'成功',failure:'失败',cancelled:'已取消',timed_out:'超时',completed:'已完成'}
const filter = ref('all')
const runPage = ref({ page: 1, pages: 1, total: 0, count: 0, active: 0, failed: 0 })
const runsHeading = ref(null)
const changingPage = ref(false)
let runsRequest = 0
const route=useRoute(),tab=ref('runs'),events=ref([]),logError=ref(''),follow=ref(true),live=ref(true),logLevel=ref('all'),logBody=ref(null),now=ref(Date.now())
const filteredEvents=computed(()=>events.value.filter(e=>logLevel.value==='all'||e.level!=='info'))
let timer,clockTimer,polling=false,detailLoading=false
function elapsed(run){const end=run.status==='completed'?new Date(run.updatedAt).getTime():now.value;const seconds=Math.max(0,Math.floor((end-new Date(run.createdAt).getTime())/1000));return seconds<60?seconds+' 秒':Math.floor(seconds/60)+' 分 '+seconds%60+' 秒'}
function percent(step){return step.status==='success'?100:step.progress.totalBatches?Math.min(100,Math.round((step.progress.completedBatches||0)/step.progress.totalBatches*100)):null}
function time(value){return new Date(value).toLocaleTimeString('zh-CN',{hour12:false})}
async function details(run, initialEvents = []) {
  selected.value = run
  events.value = initialEvents
  logError.value = ''
  live.value = true
  follow.value = true
  await nextTick()
  if (!modal.value || selected.value?.id !== run.id) return
  modal.value.showModal()
  if (initialEvents.length) scrollToLatest()
  await refreshDetails()
}
async function refreshDetails(){if(!selected.value||detailLoading)return;detailLoading=true;const id=selected.value.id;try{const result=await adminRequest('job-detail',{runId:id,after:events.value.at(-1)?.id||0});if(selected.value?.id!==id)return;selected.value=result.run;const hasNewEvents=result.events.length>0;events.value=[...events.value,...result.events].slice(-2000);logError.value='';await nextTick();if(hasNewEvents&&follow.value)scrollToLatest()}catch(e){logError.value=e.message}finally{detailLoading=false}}
function scrollToLatest(){if(logBody.value)logBody.value.scrollTop=logBody.value.scrollHeight}
function logScrolled(){const el=logBody.value;if(el&&el.scrollHeight-el.clientHeight-el.scrollTop>24)follow.value=false}
watch(follow,async enabled=>{if(enabled){await nextTick();scrollToLatest()}})
let backdropPressed=false
function outsideDrawer(event){const rect=modal.value.getBoundingClientRect();return event.target===modal.value&&(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)}
function drawerPointerDown(event){backdropPressed=outsideDrawer(event)}
function drawerPointerUp(event){if(backdropPressed&&outsideDrawer(event))modal.value.close();backdropPressed=false}
const dailyRules=computed(()=>['daily','all'].includes(selected.value?.kind)?selected.value.config?.daily||[]:[])
async function loadRuns(page = runPage.value.page) {
  const request = ++runsRequest
  const status = filter.value
  try {
    const { runs: items, ...pagination } = await adminRequest('runs', { page, status })
    if (request !== runsRequest || status !== filter.value) return false
    runs.value = items
    runPage.value = { ...pagination, status }
    return true
  } catch (e) {
    if (request === runsRequest) error.value = e.message
    return false
  }
}

async function changePage(page, focusHeading = false) {
  changingPage.value = true
  const pending = loadRuns(page)
  const request = runsRequest
  const updated = await pending
  if (request !== runsRequest) return
  changingPage.value = false
  if (updated && focusHeading) {
    await nextTick()
    runsHeading.value?.focus()
  }
}

watch(filter, () => changePage(1))

async function load() {
  try {
    const [, config] = await Promise.all([
      changingPage.value ? null : loadRuns(runPage.value.status === filter.value ? runPage.value.page : 1),
      adminRequest('schedules')
    ])
    schedules.value = config.items.map(s => {
      const draft = schedules.value.find(old => old.kind === s.kind && scheduleDirty(old))
      return draft || { ...s, enabled: Boolean(s.enabled), original: JSON.stringify({ enabled: Boolean(s.enabled), hour: s.hour, minute: s.minute, timezone: s.timezone }) }
    })
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function perform(fn){if(busy.value)return;busy.value=true;error.value='';notice.value='';try{await fn();await load()}catch(e){error.value=e.message}finally{busy.value=false}}
async function dispatch(kind){if(!await confirm({title:`启动${labels[kind]}？`,description:'使用当前已保存的配置加入后台队列，成功后直接更新公开数据。',confirmLabel:'启动任务'}))return;await perform(async()=>{const result=await adminRequest('dispatch',{workflow:kind});notice.value=`任务 #${result.id} 已排队。`})}
async function all(){if(!await confirm({title:'分别同步全部数据？',description:'收藏、标签翻译和每日搜索将作为三个独立任务执行，各自成功后生效。',confirmLabel:'启动三个任务'}))return;await perform(async()=>{await adminRequest('dispatch-all');notice.value='三个同步任务已排队。'})}
async function cancel(run){if(!await confirm({title:'取消此任务？',description:'正在抓取的任务会终止，尚未发布的数据不会覆盖现有结果。',confirmLabel:'取消任务',danger:true}))return;await perform(async()=>{await adminRequest('job-cancel',{runId:run.id});notice.value='取消请求已提交。'})}
async function retry(run,original){if(!await confirm({title:original?'重试失败步骤？':'按当前配置重新执行？',description:original?'使用原任务的冻结配置，复用已成功步骤；原规则若已被修改，发布时仍会进行版本检查。':'全部步骤使用当前配置重新执行。',confirmLabel:original?'重试失败步骤':'重新执行'}))return;await perform(async()=>{await adminRequest('rerun',{runId:run.id,original});notice.value='任务已排队。'})}
function scheduleDirty(s){return !sameContent(JSON.parse(s.original),scheduleDraft(s))}
async function save(s){if(!scheduleDirty(s))return;await perform(async()=>{await adminRequest('schedule-save',{kind:s.kind,version:s.version,...scheduleDraft(s)});s.original=JSON.stringify({enabled:s.enabled,hour:s.hour,minute:s.minute,timezone:s.timezone});notice.value='调度已保存，worker 会在十秒内读取新配置。'})}
onMounted(async () => {
  await load()
  if (!modal.value) return
  const runId = Number(route.query.run)
  if (Number.isSafeInteger(runId) && runId > 0) {
    try {
      const { run, events: entries } = await adminRequest('job-detail', { runId })
      if (modal.value) await details(run, entries)
    } catch (e) {
      error.value = e.message
    }
  }
  if (!modal.value) return
  clockTimer = setInterval(() => now.value = Date.now(), 1000)
  timer = setInterval(async () => {
    if (polling || busy.value || changingPage.value || document.visibilityState !== 'visible') return
    polling = true
    try {
      await loadRuns(runPage.value.status === filter.value ? runPage.value.page : 1)
      if (selected.value && live.value) await refreshDetails()
    } finally {
      polling = false
    }
  }, 2000)
})
const dirty=computed(()=>schedules.value.some(scheduleDirty))
function beforeUnload(e){if(dirty.value){e.preventDefault();e.returnValue=''}}
window.addEventListener('beforeunload',beforeUnload)
onBeforeRouteLeave(async()=>!dirty.value||await confirm({title:'放弃未保存的调度修改？',description:'调度必须保存后才会执行。',confirmLabel:'放弃并离开',danger:true}))
onBeforeUnmount(()=>{clearInterval(timer);clearInterval(clockTimer);window.removeEventListener('beforeunload',beforeUnload)})
</script>
<template>
  <div class="a-page task-page" :aria-busy="busy || loading">
    <header class="a-page-heading ops-page-header">
      <div class="a-page-title">
        <AdminMenuButton />
        <div>
          <h1>同步任务与调度</h1>
          <div v-if="!loading" class="task-queue">
            <span class="task-queue-status">
              <span class="ops-live-dot" :class="{ 'is-running': runPage.active }" aria-hidden="true"></span>
              {{ runPage.active ? `${runPage.active} 个任务排队或执行中` : '队列空闲' }}
            </span>
            <span v-if="runPage.failed" class="task-failed">近期 {{ runPage.failed }} 个任务失败或超时</span>
          </div>
        </div>
      </div>
      <div class="a-heading-actions task-header-actions">
        <button type="button" class="a-button" aria-label="刷新" :disabled="busy || loading || changingPage" @click="load">
          <AdminIcon name="refresh" :size="16" /><span class="a-secondary-action-label">刷新</span>
        </button>
        <button type="button" class="a-button a-primary" :disabled="busy" @click="all">
          <AdminIcon name="plus" :size="16" />分别同步全部
        </button>
      </div>
    </header>

    <p v-if="error" class="a-alert a-alert-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="a-alert a-alert-success" role="status">{{ notice }}</p>
    <AdminTabs v-model="tab" label="任务视图" :items="[
      { id: 'runs', label: '运行记录', icon: 'tasks', count: runPage.count },
      { id: 'schedules', label: '每日调度', icon: 'clock', count: schedules.filter(s => s.enabled).length + ' / ' + schedules.length },
    ]" />

    <section v-if="tab === 'runs'" id="tasks-tabs-panel-runs" class="task-panel" role="tabpanel" aria-labelledby="tasks-tabs-runs">
      <div class="task-launch-row" role="group" aria-label="手动同步">
        <h2>手动同步</h2>
        <div class="task-launch-actions">
          <button v-for="kind in ['favorites', 'translations', 'daily']" :key="kind" type="button" class="a-button ops-launch" :disabled="busy" @click="dispatch(kind)">
            <AdminIcon :name="taskIcons[kind]" :size="17" />{{ labels[kind] }}
          </button>
        </div>
      </div>

      <section class="a-card task-surface" aria-labelledby="runs-heading" :aria-busy="loading || changingPage">
        <header class="task-section-heading">
          <h2 id="runs-heading" ref="runsHeading" tabindex="-1">运行记录</h2>
          <select v-model="filter" aria-label="筛选任务状态">
            <option value="all">全部状态</option>
            <option v-for="status in ['queued', 'in_progress', 'failure', 'success', 'cancelled', 'timed_out']" :key="status" :value="status">{{ states[status] }}</option>
          </select>
        </header>
        <p v-if="loading || (changingPage && runPage.status !== filter)" class="task-list-message" role="status">正在加载运行记录…</p>
        <p v-else-if="runPage.status !== filter" class="task-list-message">运行记录加载失败。</p>
        <template v-else>
          <div v-if="runs.length">
            <div class="task-run-grid task-column-headings" aria-hidden="true">
              <span>任务</span><span>状态与进度</span><span>创建时间</span><span>操作</span>
            </div>
            <article v-for="run in runs" :key="run.id" class="ops-run task-run-grid">
              <div class="task-run-main">
                <h3><button type="button" class="ops-run-title" @click="details(run)">{{ run.name }} <small>#{{ run.id }}</small></button></h3>
                <p v-if="run.summary || run.status === 'queued'" class="task-run-note">{{ run.summary || '等待 worker 领取' }}</p>
                <p v-if="run.parentId" class="task-run-note">重试自 #{{ run.parentId }}</p>
              </div>
              <div class="task-run-progress">
                <span class="ops-state task-run-state" :class="run.conclusion || run.status">{{ run.cancelRequested && run.status === 'in_progress' ? '正在取消' : states[run.conclusion || run.status] }}</span>
                <ul v-if="run.steps.length" class="task-steps">
                  <li v-for="step in run.steps" :key="step.name" :class="step.status">
                    <span>{{ labels[step.name] }}</span>
                    <span class="task-step-result">{{ step.status === 'success' ? '已完成' : step.progress.totalBatches ? `${step.progress.completedBatches || 0} / ${step.progress.totalBatches} 批` : step.progress.pages ? `${step.progress.pages} 页` : states[step.status] }}</span>
                    <div class="ops-progress" :class="{ 'is-indeterminate': percent(step) === null && step.status === 'in_progress' }" aria-hidden="true"><i :style="{ width: (percent(step) || 0) + '%' }" /></div>
                  </li>
                </ul>
              </div>
              <div class="task-run-time">
                <time :datetime="run.createdAt">{{ formatDate(run.createdAt) }}</time>
                <span>耗时 {{ elapsed(run) }}</span>
              </div>
              <div class="task-run-actions">
                <button type="button" class="a-text-button" @click="details(run)"><AdminIcon name="tasks" :size="16" />日志与进度</button>
                <button v-if="run.status !== 'completed'" type="button" class="a-text-button" :disabled="busy || run.cancelRequested" @click="cancel(run)">取消任务</button>
                <template v-else>
                  <button type="button" class="a-text-button" :disabled="busy" @click="retry(run, false)">按当前配置重跑</button>
                  <button v-if="run.conclusion !== 'success'" type="button" class="a-text-button" :disabled="busy" @click="retry(run, true)">重试失败步骤</button>
                </template>
              </div>
            </article>
          </div>
          <div v-else class="ops-empty">
            <AdminIcon name="tasks" :size="30" />
            <h3>{{ runPage.count ? '没有符合筛选的任务' : '暂无运行记录' }}</h3>
          </div>
          <footer v-if="runPage.total" class="a-pagination task-pagination">
            <span class="ops-muted" role="status">共 {{ runPage.total }} 条 · 第 {{ runPage.page }} / {{ runPage.pages }} 页</span>
            <nav v-if="runPage.pages > 1" aria-label="运行记录分页">
              <button type="button" class="a-button" :disabled="changingPage || runPage.page <= 1" @click="changePage(runPage.page - 1, true)">上一页</button>
              <button type="button" class="a-button" :disabled="changingPage || runPage.page >= runPage.pages" @click="changePage(runPage.page + 1, true)">下一页</button>
            </nav>
          </footer>
        </template>
      </section>
    </section>

    <section v-else id="tasks-tabs-panel-schedules" class="task-panel" role="tabpanel" aria-labelledby="tasks-tabs-schedules">
      <section class="a-card task-surface" aria-labelledby="schedule-heading">
        <header class="task-section-heading">
          <div>
            <h2 id="schedule-heading">每日自动同步</h2>
            <p class="ops-muted">按所选时区执行。暂停调度不会取消已排队的任务。</p>
          </div>
        </header>
        <p v-if="loading" class="task-list-message" role="status">正在加载调度…</p>
        <p v-else-if="!schedules.length" class="task-list-message">暂无调度配置。</p>
        <div v-else class="v2-schedules">
          <article v-for="s in schedules" :key="s.kind" class="task-schedule">
            <div class="task-schedule-name">
              <AdminIcon :name="taskIcons[s.kind]" :size="19" />
              <h3>{{ labels[s.kind] }}</h3>
            </div>
            <label class="task-schedule-toggle">
              <span class="ops-switch">
                <input v-model="s.enabled" role="switch" type="checkbox" :disabled="busy" :aria-label="'启用' + labels[s.kind]" />
                <span></span>
              </span>
              <span>{{ s.enabled ? '已启用' : '已暂停' }}</span>
            </label>
            <div class="task-schedule-fields">
              <label class="a-field">时<input v-model.number="s.hour" :disabled="busy" type="number" min="0" max="23" :aria-label="labels[s.kind] + '执行小时'" /></label>
              <label class="a-field">分<input v-model.number="s.minute" :disabled="busy" type="number" min="0" max="59" :aria-label="labels[s.kind] + '执行分钟'" /></label>
              <label class="a-field">时区<select v-model="s.timezone" :disabled="busy"><option>Asia/Shanghai</option><option>UTC</option></select></label>
            </div>
            <p class="task-schedule-next" :class="{ 'task-unsaved': scheduleDirty(s) }">
              <template v-if="scheduleDirty(s)">修改待保存</template>
              <template v-else-if="s.enabled">下次执行 {{ formatDate(s.next_run_at) }}</template>
              <template v-else>启用并保存后开始调度</template>
            </p>
            <button type="button" class="a-button task-schedule-save" :class="{ 'a-primary': scheduleDirty(s) }" :disabled="busy || !scheduleDirty(s)" @click="save(s)">{{ scheduleDirty(s) ? '保存调度' : '已保存' }}</button>
          </article>
        </div>
      </section>
    </section>
<dialog ref="modal" class="a-modal ops-task-drawer" @pointerdown="drawerPointerDown" @pointerup="drawerPointerUp" @close="selected=null"><template v-if="selected"><header class="ops-drawer-header"><div><span class="ops-kicker">TASK #{{selected.id}}</span><h2>{{selected.name}}</h2><p>{{formatDate(selected.createdAt)}} · {{elapsed(selected)}}</p></div><button class="ops-icon" aria-label="关闭任务详情" @click="modal.close()"><AdminIcon name="close"/></button></header><div class="ops-drawer-body touch-scroll-area"><div class="ops-section-title"><span class="ops-state" :class="selected.conclusion||selected.status">{{states[selected.conclusion||selected.status]}}</span><label class="ops-inline-check"><input v-model="live" type="checkbox"/>实时更新</label></div><p class="ops-run-summary">{{selected.summary||'等待执行'}}</p><div class="ops-task-stages"><article v-for="step in selected.steps" :key="step.name" :class="step.status"><AdminIcon :name="step.status==='success'?'check':'clock'" :size="18"/><div><strong>{{labels[step.name]}}</strong><p>{{step.summary||'正在处理'}}</p><small v-if="step.progress.totalGroups">分组 {{step.progress.group}} / {{step.progress.totalGroups}}</small><small v-if="step.progress.pages">已扫描 {{step.progress.pages}} 页<span v-if="step.progress.items">，累计 {{step.progress.items}} 条</span></small><small v-if="step.progress.totalBatches">元数据 {{step.progress.completedBatches||0}} / {{step.progress.totalBatches}} 批</small><div class="ops-progress" :class="{'is-indeterminate':percent(step)===null&&step.status==='in_progress'}"><i :style="{width:(percent(step)||0)+'%'}"/></div></div><span>{{states[step.status]}}</span></article></div><div class="ops-section-title ops-log-heading"><h3>执行日志 <small>{{events.length}}</small></h3><button class="a-text-button" @click="refreshDetails">刷新</button></div><div class="ops-log-tools"><select v-model="logLevel" aria-label="日志级别"><option value="all">全部事件</option><option value="warning">警告与错误</option></select><label class="ops-inline-check"><input v-model="follow" type="checkbox"/>跟随最新</label></div><p v-if="logError" class="a-alert a-alert-error">{{logError}}</p><div ref="logBody" class="ops-log touch-scroll-area" @scroll="logScrolled" role="log" aria-label="任务执行日志" aria-live="off"><div v-for="entry in filteredEvents" :key="entry.id" :class="entry.level"><time>{{time(entry.at)}}</time><span class="ops-log-stage">{{labels[entry.stage]||({queue:'队列',backup:'备份',publish:'发布',finish:'结束'})[entry.stage]}}</span><span>{{entry.message}}</span></div><p v-if="!filteredEvents.length">{{events.length?'暂无警告或错误':selected.status==='queued'?'等待领取任务…':'该任务暂无事件记录。升级前的任务仍可查看上方步骤摘要。'}}</p></div><p class="ops-muted">保留每个任务最近 2,000 条事件。日志记录执行明细，不包含来源链接、Cookie 或服务密钥。</p><details v-if="dailyRules.length" class="ops-config-details"><summary>本次使用的规则 <span>{{dailyRules.length}} 个分组</span></summary><article v-for="group in dailyRules" :key="group.name"><strong>{{group.name}}</strong><p>{{group.keyword||'不限关键词'}}</p><small>回溯 {{group.cutoffDays}} 天 · {{group.minPages||'不限'}}–{{group.maxPages||'不限'}} 页 · 评分 {{group.minRating||'不限'}}</small></article></details></div><footer class="ops-drawer-footer"><span class="ops-muted">{{live?'每 2 秒自动更新':'自动更新已暂停'}}</span><button v-if="selected.status!=='completed'" class="a-button" :disabled="busy||selected.cancelRequested" @click="cancel(selected)">取消任务</button><button v-else class="a-button" :disabled="busy" @click="retry(selected,false)">按当前配置重跑</button></footer></template></dialog>
</div></template>

<style scoped>
.task-page {
  container: task-page / inline-size;
}

.task-queue,
.task-header-actions,
.task-launch-row,
.task-launch-actions,
.task-section-heading,
.task-run-actions,
.task-pagination nav,
.task-schedule-name,
.task-schedule-toggle {
  display: flex;
  align-items: center;
}

.task-queue {
  gap: 4px 10px;
  flex-wrap: wrap;
  margin-top: 5px;
  color: var(--a-muted);
  font-size: 12px;
}

.task-queue-status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.task-queue .ops-live-dot {
  width: 7px;
  height: 7px;
  box-shadow: none;
}

.task-failed {
  color: var(--a-red);
}

.task-header-actions,
.task-launch-actions,
.task-pagination nav {
  gap: 8px;
  flex-wrap: wrap;
}

.task-panel {
  display: grid;
  gap: 18px;
  min-width: 0;
}

.task-launch-row {
  gap: 16px;
  flex-wrap: wrap;
}

.task-launch-row h2 {
  font-size: 13px;
}

.ops-launch:hover:not(:disabled),
.ops-launch:focus-visible {
  background: var(--a-soft);
  border-color: var(--a-accent);
  color: var(--a-text);
}

.task-surface {
  --task-inset: 22px;
}

.task-section-heading {
  min-height: 63px;
  justify-content: space-between;
  gap: 12px;
  padding: 13px var(--task-inset);
}

.task-section-heading p {
  margin-top: 5px;
  line-height: 1.6;
}

.task-section-heading select {
  width: auto;
  min-height: 36px;
}

.task-run-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr) minmax(122px, .75fr) minmax(114px, .65fr);
  gap: 18px;
  align-items: start;
  padding-inline: var(--task-inset);
}

.task-column-headings {
  padding-block: 9px;
  border-block: 1px solid var(--a-border);
  background: var(--a-subtle);
  color: var(--a-muted);
  font-size: 12px;
}

.ops-run {
  padding-block: 15px;
  overflow-wrap: anywhere;
}

.ops-run + .ops-run,
.task-schedule {
  border-top: 1px solid var(--a-border);
}

.task-run-note,
.task-run-time,
.task-schedule-next {
  color: var(--a-muted);
  font-size: 12px;
  line-height: 1.55;
}

.task-run-main .task-run-note {
  margin-top: 5px;
}

.task-run-time {
  display: grid;
  gap: 4px;
  font-variant-numeric: tabular-nums;
}

.task-run-time time {
  color: var(--a-text);
}

.task-steps {
  display: grid;
  gap: 8px;
  margin: 9px 0 0;
  padding: 0;
  list-style: none;
  color: var(--a-muted);
  font-size: 12px;
}

.task-steps li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 4px 6px;
}

.task-step-result {
  color: var(--a-text);
  font-variant-numeric: tabular-nums;
}

.task-run-actions {
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
}

.task-run-actions .a-text-button {
  min-height: 26px;
  margin: -2px 0 0;
}

.task-list-message {
  padding: 16px var(--task-inset);
  border-top: 1px solid var(--a-border);
  color: var(--a-muted);
}

.task-pagination {
  padding-inline: var(--task-inset);
  flex-wrap: wrap;
}

.task-schedule {
  display: grid;
  grid-template-columns: minmax(108px, .8fr) minmax(218px, 1.55fr) minmax(115px, 1fr) auto;
  grid-template-areas:
    'name fields next save'
    'toggle fields next save';
  align-items: center;
  gap: 6px 18px;
  padding: 17px var(--task-inset);
}

.task-schedule-name {
  grid-area: name;
  gap: 8px;
}

.task-schedule-name svg {
  flex-shrink: 0;
  color: var(--a-accent);
}

.task-schedule-toggle {
  grid-area: toggle;
  gap: 8px;
  width: max-content;
  min-height: 32px;
  color: var(--a-muted);
  font-size: 12px;
  cursor: pointer;
}

.task-schedule-fields {
  grid-area: fields;
  display: grid;
  grid-template-columns: minmax(50px, .55fr) minmax(50px, .55fr) minmax(105px, 1.25fr);
  gap: 8px;
}

.task-schedule-fields :is(input, select) {
  width: 100%;
  min-width: 0;
  padding-inline: 7px;
  font-variant-numeric: tabular-nums;
}

.task-schedule-next {
  grid-area: next;
}

.task-schedule-next.task-unsaved {
  color: var(--a-amber);
}

.task-schedule-save {
  grid-area: save;
  justify-self: end;
}

@container task-page (max-width: 690px) {
  .task-surface {
    --task-inset: 14px;
  }

  .task-column-headings {
    display: none;
  }

  .ops-run {
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-areas:
      'main status'
      'time time'
      'steps steps'
      'actions actions';
    gap: 7px 10px;
  }

  .ops-run:first-of-type {
    border-top: 1px solid var(--a-border);
  }

  .task-run-main { grid-area: main; }
  .task-run-progress { display: contents; }
  .task-run-state { grid-area: status; }
  .task-steps { grid-area: steps; margin: 0; }

  .task-run-time {
    grid-area: time;
    display: flex;
    flex-wrap: wrap;
    gap: 4px 12px;
  }

  .task-run-actions {
    grid-area: actions;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 2px 14px;
  }

  .task-run-actions .a-text-button {
    min-height: 42px;
    margin: 0;
  }

  .task-schedule {
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-areas:
      'name toggle'
      'fields fields'
      'next save';
    gap: 12px;
  }

  .task-schedule-toggle {
    min-height: 42px;
  }
}

@container task-page (max-width: 480px) {
  .task-page .a-page-title,
  .task-header-actions {
    flex-basis: 100%;
  }

  .task-header-actions {
    justify-content: flex-end;
  }

  .task-launch-row {
    gap: 8px;
  }

  .task-launch-actions {
    width: 100%;
    gap: 5px;
  }

  .task-launch-actions .a-button {
    flex: 1;
    min-height: 42px;
    padding-inline: 4px;
    font-size: 12px;
  }

  .task-schedule-fields :is(input, select) {
    min-height: 42px;
    font-size: 16px;
  }
}
</style>
