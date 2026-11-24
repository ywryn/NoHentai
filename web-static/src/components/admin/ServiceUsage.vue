<script setup>
import { onMounted, ref } from 'vue'
import { adminRequest, formatDate } from '@/utils/adminApi'
import AdminIcon from './AdminIcon.vue'

defineProps({ localUsage: Object })

const labels = {
  vision: { name: 'Google Vision', unit: '次' },
  'google-translate': { name: 'Google 翻译', unit: '字符' },
}
const dollars = new Intl.NumberFormat('zh-CN', {
  style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 6,
})
const xai = ref(null)
const loading = ref(false)

async function loadProviderUsage() {
  if (loading.value) return
  loading.value = true
  try {
    xai.value = (await adminRequest('provider-usage')).xai
  } catch {
    xai.value = { state: 'unavailable' }
  } finally {
    loading.value = false
  }
}

function amount(value) {
  return value == null ? '暂不可用' : dollars.format(Number(value))
}

onMounted(loadProviderUsage)
</script>

<template>
  <article class="a-card ops-surface service-usage" aria-labelledby="service-usage-title">
    <header class="ops-section-title">
      <h2 id="service-usage-title">服务用量</h2>
      <RouterLink to="/admin/services" class="a-text-button">
        用量设置 <AdminIcon name="arrow-right" :size="16" />
      </RouterLink>
    </header>

    <section aria-labelledby="site-usage-title">
      <h3 id="site-usage-title">本站预扣 <small v-if="localUsage">{{ localUsage.month }} · UTC</small></h3>
      <dl v-if="localUsage" class="usage-metrics">
        <div v-for="item in localUsage.items" :key="item.id">
          <dt>{{ labels[item.id].name }}</dt>
          <dd>
            <strong>{{ item.count.toLocaleString('zh-CN') }}</strong>
            <span>{{ labels[item.id].unit }}</span>
          </dd>
          <dd class="usage-detail">
            {{ !item.configured ? '服务未配置' : item.limit === 0 ? '本站额度已关闭' : '本站月上限 ' + item.limit.toLocaleString('zh-CN') + ' ' + labels[item.id].unit }}
          </dd>
        </div>
      </dl>
      <p v-else class="ops-muted">当前未能读取本站预扣计数。</p>
    </section>

    <section class="provider-usage" aria-labelledby="provider-usage-title" :aria-busy="loading">
      <header class="ops-section-title">
        <h3 id="provider-usage-title">xAI 官方账单</h3>
        <button class="a-text-button" type="button" :disabled="loading" @click="loadProviderUsage">
          {{ loading ? '查询中…' : '查询账单' }}
        </button>
      </header>
      <template v-if="xai?.state === 'available'">
        <dl class="usage-metrics">
          <div>
            <dt>团队当月开销</dt>
            <dd><strong>{{ amount(xai.spendUsd) }}</strong></dd>
            <dd class="usage-detail">{{ xai.month }} · UTC</dd>
          </div>
          <div>
            <dt>团队预付余额</dt>
            <dd><strong>{{ amount(xai.balanceUsd) }}</strong></dd>
          </div>
        </dl>
        <p class="ops-muted">上次查询 {{ formatDate(xai.checkedAt) }}。供应商汇总可能延迟。</p>
      </template>
      <p v-else-if="!loading" class="ops-muted" role="status">
        {{ xai?.state === 'unconfigured' ? '尚未配置 xAI 团队账单凭据。' :
           xai?.state === 'unsupported' ? '当前模型服务未接入官方账单查询。' : '暂时无法读取 xAI 账单。' }}
      </p>
    </section>
  </article>
</template>

<style scoped>
.service-usage > header,
.provider-usage > header {
  flex-wrap: wrap;
  gap: 8px;
}

.service-usage h3 {
  font-size: 13px;
  margin-block: 0 8px;
}

.service-usage h3 small {
  color: var(--a-muted);
  font-size: 11px;
  font-weight: 400;
  margin-inline-start: 6px;
}

.usage-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 10rem), 1fr));
  gap: 10px;
  margin: 0;
}

.usage-metrics > div {
  padding: 10px 12px;
  background: var(--a-subtle);
  border: 1px solid var(--a-border);
  border-radius: 8px;
}

.usage-metrics dt,
.usage-detail {
  color: var(--a-muted);
  font-size: 11px;
}

.usage-metrics dd {
  margin-inline-start: 0;
}

.usage-metrics strong {
  display: inline-block;
  font-size: 21px;
  font-variant-numeric: tabular-nums;
  overflow-wrap: anywhere;
}

.usage-metrics dd > span {
  margin-inline-start: 4px;
  color: var(--a-muted);
  font-size: 11px;
}

.provider-usage {
  margin-block-start: 14px;
  padding-block-start: 14px;
  border-block-start: 1px solid var(--a-border);
}

.provider-usage :is(header, h3) {
  margin-block-end: 8px;
}
</style>
