<!-- Bottom page number navigation, absolute positioned in reading area -->
<template>
  <div class="page-nav" v-if="total > 1">
    <button class="pn-btn pn-arrow" :disabled="isAtStart" @click="onLeft">‹</button>
    <template v-for="item in displayItems" :key="item.key">
      <span v-if="item.type === 'ellipsis'" class="pn-ellipsis">…</span>
      <button
        v-else
        class="pn-btn pn-page"
        :class="{ 'pn-active': item.active }"
        @click="goTo(item.page!)"
      >{{ item.page }}</button>
    </template>
    <button class="pn-btn pn-arrow" :disabled="isAtEnd" @click="onRight">›</button>
  </div>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { READER_KEY } from '@/composables/useReader'

const reader = inject(READER_KEY)!
const { currentPage, total, goTo, prev, next, settings } = reader

const rtl = computed(() => settings.bookDirection === 'rtl')

const isAtStart = computed(() => rtl.value ? currentPage.value >= total.value : currentPage.value <= 1)
const isAtEnd   = computed(() => rtl.value ? currentPage.value <= 1 : currentPage.value >= total.value)

const onLeft  = () => rtl.value ? next() : prev()
const onRight = () => rtl.value ? prev() : next()

interface NavItem {
  type: 'page' | 'ellipsis'
  key: string
  page?: number
  active?: boolean
}

const navItems = computed<NavItem[]>(() => {
  const cur = currentPage.value
  const t = total.value
  const items: NavItem[] = []

  const addPage = (p: number) => {
    items.push({ type: 'page', key: `p${p}`, page: p, active: p === cur })
  }

  if (t <= 9) {
    for (let i = 1; i <= t; i++) addPage(i)
  } else {
    addPage(1)
    if (cur > 4) items.push({ type: 'ellipsis', key: 'e1' })

    const start = Math.max(2, cur - 2)
    const end   = Math.min(t - 1, cur + 2)
    for (let i = start; i <= end; i++) addPage(i)

    if (cur < t - 3) items.push({ type: 'ellipsis', key: 'e2' })
    addPage(t)
  }

  return items
})

const displayItems = computed(() =>
  rtl.value ? [...navItems.value].reverse().map((item, i, arr) => ({
    ...item,
    key: item.type === 'ellipsis' ? `re${i}` : item.key,
  })) : navItems.value
)
</script>

<style scoped>
.page-nav {
  position: absolute;
  bottom: 10px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 3px;
  background: rgba(0,0,0,0.55);
  border-radius: 6px;
  padding: 4px 6px;
  z-index: 10;
  pointer-events: auto;
}

.pn-btn {
  background: none;
  border: none;
  color: rgba(255,255,255,0.75);
  font-size: 13px;
  cursor: pointer;
  padding: 2px 7px;
  border-radius: 3px;
  line-height: 1.5;
  min-width: 28px;
  transition: background 0.15s, color 0.15s;
}
.pn-btn:hover:not(:disabled) {
  background: rgba(255,255,255,0.15);
  color: #fff;
}
.pn-btn:disabled { opacity: 0.3; cursor: default; }
.pn-active {
  background: #22c55e !important;
  color: #fff !important;
  font-weight: 600;
}
.pn-arrow { font-size: 16px; padding: 2px 6px; }
.pn-ellipsis { color: rgba(255,255,255,0.4); padding: 0 2px; font-size: 13px; }
</style>
