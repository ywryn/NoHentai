<script setup>
import { ref, onMounted } from 'vue'
import { adminRequest, formatDate } from '@/utils/adminApi'
import AdminMenuButton from './AdminMenuButton.vue'
import HistoryPagination from './HistoryPagination.vue'
import RecordHistory from './RecordHistory.vue'

const history = ref(null)
const sections = ref([
  { label: '内容修改', action: 'record-history', result: { items: [], page: 1 }, busy: false, error: '' },
  { label: '配置与账户操作', action: 'audit-events', result: { items: [], page: 1 }, busy: false, error: '' },
])
const labels = { gallery: '画廊', manual: '首页图书', book: '书目', daily: '每日规则' }

async function load(section, page = section.result.page) {
  const request = Symbol()
  section.request = request
  section.busy = true
  section.error = ''
  try {
    const result = await adminRequest(section.action, { page })
    if (section.request === request) section.result = result
  } catch (error) {
    if (section.request === request) section.error = error.message
  } finally {
    if (section.request === request) section.busy = false
  }
}

function refresh() {
  return Promise.all(sections.value.map(section => load(section)))
}

onMounted(refresh)
</script>

<template>
  <div class="a-page">
    <header class="a-page-heading">
      <div class="a-page-title">
        <AdminMenuButton />
        <div><h1>修改记录</h1><p>逐条查看内容变化，删除记录也可恢复。</p></div>
      </div>
      <button type="button" class="a-button" :disabled="sections.some(section => section.busy)" @click="refresh">刷新</button>
    </header>
    <section v-for="section in sections" :key="section.action" class="a-card" :aria-busy="section.busy">
      <h2>{{ section.label }}</h2>
      <p v-if="section.error" class="a-alert a-alert-error" role="alert">{{ section.error }}</p>
      <p v-else-if="section.busy" role="status">正在加载…</p>
      <article v-for="entry in section.result.items" :key="entry.id" class="v2-run">
        <template v-if="section.action === 'record-history'">
          <div class="a-section-heading">
            <div>
              <strong>{{ labels[entry.kind] }} · {{ entry.after?.['书名'] || entry.before?.['书名'] || entry.after?.title || entry.before?.title || entry.after?.name || entry.before?.name || entry.recordId }}</strong>
              <small>{{ formatDate(entry.date) }} · {{ entry.message }}</small>
            </div>
            <button type="button" class="a-button" @click="history.open(entry.kind, entry.recordId, entry.id)">查看差异与恢复</button>
          </div>
          <p>{{ Object.keys(entry.changes).join('、') || '顺序调整' }}</p>
        </template>
        <template v-else>
          <strong>{{ entry.message }}</strong>
          <small>{{ formatDate(entry.date) }}</small>
          <p v-if="entry.fields.length">{{ entry.fields.join('、') }}</p>
        </template>
      </article>
      <p v-if="!section.busy && !section.error && !section.result.items.length">尚无{{ section.label }}记录。</p>
      <HistoryPagination :result="section.result" :busy="section.busy" :label="section.label + '分页'" @change="load(section, $event)" />
    </section>
    <RecordHistory ref="history" @restored="load(sections[0], 1)" />
  </div>
</template>
