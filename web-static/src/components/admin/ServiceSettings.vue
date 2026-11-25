<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute } from 'vue-router'
import { adminRequest, formatDate } from '@/utils/adminApi'
import { serviceChanges } from '@/utils/adminDrafts'
import AdminMenuButton from './AdminMenuButton.vue'
import AdminTabs from './AdminTabs.vue'

const route = useRoute()
const confirm = inject('adminConfirm')
const groups = ref([])
const active = ref('favorites')
const error = ref('')
const notice = ref('')
const busy = ref(false)
const loading = ref(true)
const sourceName = { database: '后台配置', environment: '服务器启动配置', default: '系统默认' }
const icons = { favorites: 'gallery', 'translate-google': 'translate', translate: 'tasks', ocr: 'search' }
const tabLabels = { favorites: '收藏来源', 'translate-google': '普通翻译', translate: '模型翻译', ocr: '文字识别' }
const descriptions = {
  'translate-google': '翻译工作台选择 Google 翻译 API 时使用。字符上限按 UTC 自然月计算。',
  translate: '模型翻译使用作品上下文和术语表。工作台密码及翻译并发上限由两种方式共用。',
}
const choiceName = value => ({ google: 'Google Vision', paddle: 'PaddleOCR', ocrspace: 'OCR.Space', true: '开启', false: '关闭' })[String(value)] || String(value)
const isTranslation = group => group.id === 'translate' || group.id === 'translate-google'

function dirty(group) {
  return Object.keys(serviceChanges(group.values, JSON.parse(group.original))).length > 0
}

const anyDirty = computed(() => groups.value.some(dirty))
const tabs = computed(() => groups.value.map(group => ({
  id: group.id,
  label: tabLabels[group.id] || group.label,
  icon: icons[group.id],
  count: dirty(group) ? '待保存' : undefined,
})))

function selectLinkedGroup() {
  if (groups.value.some(group => group.id === route.query.group)) active.value = route.query.group
}
watch(() => route.query.group, selectLinkedGroup)

function checkLabel(group) {
  if (!group.check) return '尚未验证'
  if (group.check.version !== group.version) return '配置已更改，需重新测试'
  return group.check.ok ? '验证通过' : '验证未通过'
}

async function load(replaceId = null) {
  loading.value = true
  try {
    const result = await adminRequest('services')
    const previous = groups.value
    groups.value = result.groups.map(group => {
      const draft = previous.find(item => item.id === group.id)
      if (group.id !== replaceId && draft && dirty(draft)) return draft
      const values = Object.fromEntries(group.fields.map(field => [field.key, field.effective]))
      return { ...group, values, original: JSON.stringify(values) }
    })
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function save(group) {
  if (busy.value || !dirty(group)) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const values = serviceChanges(group.values, JSON.parse(group.original))
    const result = await adminRequest('service-save', { service: group.id, version: group.version, values })
    await load(group.id)
    notice.value = result.unchanged ? '内容未发生变化，无需保存。' : `${group.label}已保存，后续请求或新任务使用新配置。`
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function test(group) {
  if (busy.value || dirty(group)) return
  if (group.id !== 'favorites' && !await confirm({
    title: `测试${group.label}？`,
    description: isTranslation(group)
      ? '将发送一小段测试文字，会产生一次真实翻译请求。'
      : '将发送服务器生成的测试图片，会产生一次真实 OCR 请求并计入用量。',
    confirmLabel: '发送测试请求',
  })) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const result = await adminRequest('service-test', { service: group.id })
    await load(group.id)
    if (result.ok) notice.value = result.message
    else error.value = result.message
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function leave() {
  return !busy.value && (!anyDirty.value || await confirm({
    title: '放弃未保存的服务配置？',
    description: '离开后将丢失当前未保存的修改。',
    confirmLabel: '放弃并离开',
    danger: true,
  }))
}

function beforeUnload(event) {
  if (anyDirty.value || busy.value) {
    event.preventDefault()
    event.returnValue = ''
  }
}

window.addEventListener('beforeunload', beforeUnload)
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
onBeforeRouteLeave(leave)
onMounted(async () => {
  await load()
  selectLinkedGroup()
})
</script>

<template>
  <div class="a-page service-page" :aria-busy="loading || busy">
    <header class="a-page-heading">
      <div class="a-page-title"><AdminMenuButton /><h1>服务配置</h1></div>
      <button type="button" class="a-button" :disabled="busy || loading || anyDirty" @click="load()">刷新状态</button>
    </header>
    <p v-if="error" class="a-alert a-alert-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="a-alert a-alert-success" role="status">{{ notice }}</p>
    <p v-if="loading && !groups.length" role="status">正在加载服务配置…</p>
    <AdminTabs v-if="tabs.length" v-model="active" class="service-tabs" prefix="service-tabs" label="服务类别" :items="tabs" />
    <section v-for="group in groups" v-show="group.id === active" :id="'service-tabs-panel-' + group.id" :key="group.id"
      class="a-card service-panel" role="tabpanel" :aria-labelledby="'service-tabs-' + group.id">
      <header class="service-panel-heading">
        <div>
          <h2>{{ group.label }}</h2>
          <p v-if="descriptions[group.id]">{{ descriptions[group.id] }}</p>
          <a v-if="group.id === 'translate-google'" class="service-attribution" href="https://translate.google.com/" target="_blank" rel="noopener noreferrer">
            <img src="@/assets/google-translate.png" alt="Powered by Google Translate" width="122" height="16" />
          </a>
        </div>
        <span class="ops-state" :class="group.check?.version === group.version ? (group.check.ok ? 'success' : 'failed') : 'unchecked'">{{ checkLabel(group) }}</span>
      </header>

      <form @submit.prevent="save(group)">
        <fieldset :disabled="busy || loading" class="service-fields">
          <div v-for="field in group.fields" :key="field.key" class="a-field service-field"
            :class="{ 'service-field-wide': ['url', 'secret'].includes(field.type) }">
            <label :for="'service-' + field.key">{{ field.label }}</label>
            <select v-if="field.type === 'select'" :id="'service-' + field.key" v-model="group.values[field.key]">
              <option v-for="option in field.limits.filter(value => value !== null)" :key="String(option)" :value="option">{{ choiceName(option) }}</option>
            </select>
            <input v-else-if="field.type === 'number'" :id="'service-' + field.key" v-model.number="group.values[field.key]"
              type="number" required :min="field.limits[0]" :max="field.limits[1]" :step="field.key === 'RETRY_DELAY_SECONDS' ? 'any' : 1" />
            <input v-else :id="'service-' + field.key" v-model="group.values[field.key]"
              :type="field.type === 'url' ? 'url' : field.key === 'EXHENTAI_LOGIN_PASSWORD' ? 'password' : 'text'"
              :maxlength="field.key === 'TRANS_PASSWORD' ? 1024 : field.type === 'secret' ? 16000 : 2000"
              autocomplete="off" spellcheck="false" />
            <small class="ops-muted">{{ field.key.startsWith('EXHENTAI_LOGIN_')
              ? (field.configured ? '已配置，输入新值可替换' : '手动刷新 Cookie 时使用')
              : sourceName[field.source] }}</small>
          </div>
        </fieldset>
        <footer class="service-panel-footer">
          <div class="service-feedback">
            <p v-if="dirty(group)" class="service-unsaved">有未保存修改</p>
            <p v-if="group.check" class="ops-muted">{{ group.check.message }} · {{ formatDate(group.check.checked_at) }}</p>
          </div>
          <div class="service-actions">
            <button type="button" class="a-button" :disabled="busy || loading || dirty(group)" @click="test(group)">{{ group.id === 'favorites' ? '验证收藏访问' : '发送测试请求' }}</button>
            <button type="submit" class="a-button a-primary" :disabled="busy || loading || !dirty(group)">保存{{ group.label }}</button>
          </div>
        </footer>
      </form>
    </section>
    <p v-if="groups.length" class="a-inline-note">清空密钥并保存会停用该密钥。正在运行的同步任务继续使用启动时的配置。</p>
  </div>
</template>

<style scoped>
.service-page { container: service-page / inline-size; }

.service-panel {
  --service-inset: 24px;
  justify-self: start;
  width: min(100%, 900px);
}

.service-page > .service-panel { padding: 0; }

.service-panel-heading,
.service-panel-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px 20px;
  padding: 16px var(--service-inset);
}

.service-panel-heading { border-bottom: 1px solid var(--a-border); }
.service-panel-heading p { margin-top: 5px; color: var(--a-muted); font-size: 12px; line-height: 1.65; }
.service-panel-heading .ops-state { flex-shrink: 0; }
.service-attribution { display: inline-flex; margin-top: 8px; padding: 3px 5px; border-radius: 4px; background: #fff; }
.service-attribution img { display: block; }

.service-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 20px;
  padding: 20px var(--service-inset);
}

.service-field { gap: 5px; }
.service-field-wide { grid-column: 1 / -1; }
.service-field :is(input, select) { width: 100%; min-width: 0; }
.service-field small { font-size: 11px; }

.service-panel-footer {
  flex-wrap: wrap;
  border-top: 1px solid var(--a-border);
}

.service-feedback { flex: 1 1 160px; min-width: 0; }
.service-feedback:empty { display: none; }
.service-unsaved { color: var(--a-amber); font-size: 12px; }
.service-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-inline-start: auto; }

@container service-page (max-width: 550px) {
  .service-tabs {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
  }

  .service-tabs :deep(button) { min-width: 0; padding-inline: 6px; gap: 4px; }
  .service-tabs :deep(small) { padding-inline: 3px; }
  .service-panel { --service-inset: 14px; }
  .service-panel-heading { flex-wrap: wrap; }
  .service-fields { grid-template-columns: minmax(0, 1fr); }
  .service-field :is(input, select) { min-height: 42px; font-size: 16px; }
}
</style>
