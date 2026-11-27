<script setup>
import { computed, markRaw, onMounted, onBeforeUnmount, ref, shallowRef, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import LayoutComparePane from './LayoutComparePane.vue'
import { paperRegions, schemes } from '@/utils/compareLayouts'
const props = defineProps(['image', 'results', 'page', 'error'])
const route = useRoute()
const back = computed(() => {
  const query = { ...route.query }
  delete query.view
  return { path: route.path, query }
})
const narrow = window.matchMedia('(max-width:767px)')
const mobile = ref(narrow.matches),
  active = ref('original'),
  outlines = ref(false),
  zoom = ref(100),
  selected = ref(null)
const paper = shallowRef(null),
  panes = new Map()
const contourCount = computed(() =>
  paper.value ? props.results.filter((r) => paper.value.owner(r.bbox)).length : 0,
)
const visible = computed(() => (mobile.value ? schemes.filter((s) => s.id === active.value) : schemes))
function breakpoint() {
  mobile.value = narrow.matches
}
onMounted(() => narrow.addEventListener('change', breakpoint))
onBeforeUnmount(() => narrow.removeEventListener('change', breakpoint))
watch(
  () => props.image,
  (img) => {
    paper.value = null
    if (img)
      try {
        paper.value = markRaw(paperRegions(img))
      } catch {
        /* Canvas unavailable: use geometric bounds. */
      }
  },
  { immediate: true },
)
let left = 0,
  top = 0
function sync(source, x, y) {
  if (left === x && top === y) return
  left = x
  top = y
  for (const [id, pane] of panes) if (id !== source) pane.pan(x, y)
}
watch(visible, async () => {
  await nextTick()
  for (const pane of panes.values()) pane.pan(left, top)
})
</script>
<template>
  <section class="lab">
    <header>
      <RouterLink :to="back" replace>返回翻译</RouterLink>
      <h1>排版对比</h1>
      <span>第 {{ page }} 页</span>
    </header>
    <div class="tools">
      <label v-if="mobile"
        >方案
        <select v-model="active">
          <option v-for="s in schemes" :key="s.id" :value="s.id">{{ s.label }}</option>
        </select></label
      >
      <label
        >倍率
        <select v-model.number="zoom">
          <option v-for="n in [100, 150, 200, 300]" :key="n" :value="n">{{ n }}%</option>
        </select></label
      >
      <label><input type="checkbox" v-model="outlines" /> 分组轮廓</label>
    </div>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-else-if="!image" role="status">正在载入当前页…</p>
    <p v-else-if="!results.length">本页尚无识别结果。请返回翻译工作台识别并翻译一次。</p>
    <template v-else>
      <p v-if="outlines && results.some((r) => r.is_merged && !r.memberBoxes)">
        旧缓存仅保存合并框，轮廓以现有文字组估算。
      </p>
      <div class="panels">
        <article v-for="s in visible" :key="s.id">
          <h2>
            {{ s.label }}
            <small v-if="s.id === 'balloon'"
              >识别到轮廓 {{ contourCount }} / {{ results.length }} · 其余使用几何避让</small
            >
          </h2>
          <LayoutComparePane
            :ref="(el) => (el ? panes.set(s.id, el) : panes.delete(s.id))"
            :mode="s.id"
            :image="image"
            :results="results"
            :paper="paper"
            :zoom="zoom"
            :outlines="outlines"
            @select="selected = $event"
            @pan="(x, y) => sync(s.id, x, y)"
          />
        </article>
      </div>
      <aside v-if="selected != null && results[selected]">
        <button @click="selected = null">关闭</button><strong>对白 {{ selected + 1 }}</strong>
        <p>{{ results[selected].text }}</p>
        <p>{{ results[selected].translation || '尚无译文' }}</p>
      </aside>
    </template>
  </section>
</template>
<style scoped>
.lab {
  height: 100dvh;
  display: flex;
  flex-direction: column;
  color: var(--text-color);
  background: var(--surface-color);
  min-height: 0;
}
header,
.tools {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  padding: 0.65rem 1rem;
  border-bottom: 1px solid var(--border-color);
}
h1,
h2,
p {
  margin: 0;
}
h1 {
  font-size: 1.2rem;
}
h2 {
  font-size: 0.95rem;
  padding: 0.5rem 0.75rem;
}
header span {
  color: var(--muted-color);
}
a {
  color: var(--primary-color);
}
label {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}
small {
  font-size: 0.75rem;
  font-weight: 400;
  color: var(--muted-color);
}
select,
button {
  font: inherit;
  color: inherit;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 5px;
  padding: 0.35rem;
}
.panels {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(0, 1fr));
  flex: 1;
  min-height: 0;
  gap: 2px;
}
article {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  background: var(--bg-color);
}
aside,
.lab > p {
  padding: 0.65rem 1rem;
}
aside {
  border-top: 1px solid var(--border-color);
  max-height: 25dvh;
  overflow: auto;
}
aside button {
  float: right;
}
</style>
