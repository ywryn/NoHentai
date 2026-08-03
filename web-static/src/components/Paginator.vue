<script setup>
import { ref, computed, watch } from 'vue'

/**
 * 列表分页器。
 * Home / Printed / Daily 此前各自复制了两份相同的分页 markup（共 6 处），
 * 且只有首末与前后按钮 —— 133 页的情况下用户失去了「自己在哪」的空间感。
 * 这里补上页码序列，跳页输入保留给远距离跳转。
 */
const props = defineProps({
  page: { type: Number, required: true },
  total: { type: Number, required: true },
})

const emit = defineEmits(['go'])

const jumpValue = ref(String(props.page))
watch(() => props.page, p => { jumpValue.value = String(p) })

/** 当前页周围保留 ±1，两端各保留 1，其余折叠为省略号 */
const items = computed(() => {
  const { page, total } = props
  const out = []
  const push = n => out.push({ type: 'page', key: `p${n}`, n })

  if (total <= 7) {
    for (let i = 1; i <= total; i++) push(i)
    return out
  }

  push(1)
  const start = Math.max(2, page - 1)
  const end = Math.min(total - 1, page + 1)
  if (start > 2) out.push({ type: 'gap', key: 'g1' })
  for (let i = start; i <= end; i++) push(i)
  if (end < total - 1) out.push({ type: 'gap', key: 'g2' })
  push(total)
  return out
})

function go(n) {
  const target = Math.max(1, Math.min(props.total, Number(n) || 1))
  if (target !== props.page) emit('go', target)
}

function submitJump() {
  const digits = jumpValue.value.replace(/[^\d]/g, '')
  if (!digits) {
    jumpValue.value = String(props.page)
    return
  }
  go(digits)
}
</script>

<template>
  <nav class="pagination-control" :aria-label="`分页，共 ${total} 页`">
    <div class="paginator-mini">
      <button class="pag-btn pag-nav" type="button" :disabled="page <= 1" aria-label="第一页" @click="go(1)">«</button>
      <button class="pag-btn pag-nav" type="button" :disabled="page <= 1" aria-label="上一页" @click="go(page - 1)">‹</button>

      <template v-for="item in items" :key="item.key">
        <span v-if="item.type === 'gap'" class="pag-gap" aria-hidden="true">…</span>
        <button
          v-else
          class="pag-btn pag-page"
          :class="{ active: item.n === page }"
          type="button"
          :aria-label="`第 ${item.n} 页`"
          :aria-current="item.n === page ? 'page' : undefined"
          @click="go(item.n)"
        >{{ item.n }}</button>
      </template>

      <button class="pag-btn pag-nav" type="button" :disabled="page >= total" aria-label="下一页" @click="go(page + 1)">›</button>
      <button class="pag-btn pag-nav" type="button" :disabled="page >= total" aria-label="最后一页" @click="go(total)">»</button>

      <label class="pag-jump-inline">
        <span class="sr-only">跳转到页码</span>
        <input
          v-model="jumpValue"
          class="pag-jump-input"
          inputmode="numeric"
          autocomplete="off"
          spellcheck="false"
          @keydown.enter.prevent="submitJump"
          @blur="submitJump"
        />
        <span class="pag-jump-total">/ {{ total }}</span>
      </label>
    </div>
  </nav>
</template>

<style scoped>
.pag-page {
  font-size: 12px;
  font-weight: 600;
}

.pag-gap {
  color: var(--faint-color);
  padding: 0 2px;
  font-size: 13px;
  user-select: none;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* 窄屏收起页码序列与跳页框，只保留方向键 —— 底部标签栏已占用空间 */
@media (max-width: 560px) {
  .pag-page,
  .pag-gap {
    display: none;
  }

  .pag-page.active {
    display: flex;
  }
}
</style>
