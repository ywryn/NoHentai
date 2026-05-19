# GalleryReader 重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 全量重写 `/gallery/:gid/read` 阅读器，实现书本/滚动模式、RTL 双页、slide/flip 动画、缩略图导航、设置面板。

**Architecture:** `useReader.ts` composable 作为唯一状态源，通过 `provide(READER_KEY, reader)` 注入全树；子组件 `inject(READER_KEY)` 消费。书本模式用 Vue `<Transition>` + CSS 实现 slide/flip 动画；滚动模式用 `IntersectionObserver` 懒加载。所有旧 `GalleryReader.vue` 代码在最后一步删除。

**Tech Stack:** Vue 3 Composition API (`<script setup>`), TypeScript, Vite, CSS Transitions（无额外动画库）

---

## 文件清单

| 操作 | 路径 |
|------|------|
| 新建 | `web-static/src/assets/reader.css` |
| 新建 | `web-static/src/composables/useReader.ts` |
| 新建 | `web-static/src/components/reader/GalleryReader.vue` |
| 新建 | `web-static/src/components/reader/ReaderTopBar.vue` |
| 新建 | `web-static/src/components/reader/PageImage.vue` |
| 新建 | `web-static/src/components/reader/BookView.vue` |
| 新建 | `web-static/src/components/reader/ScrollView.vue` |
| 新建 | `web-static/src/components/reader/ThumbStrip.vue` |
| 新建 | `web-static/src/components/reader/ThumbGrid.vue` |
| 新建 | `web-static/src/components/reader/SettingsPanel.vue` |
| 修改 | `web-static/src/router/index.ts` |
| 删除 | `web-static/src/components/GalleryReader.vue` |

---

## Task 1: reader.css — 公共 CSS 变量与工具类

**Files:**
- Create: `web-static/src/assets/reader.css`

- [ ] **Step 1: 创建 reader.css**

```css
/* web-static/src/assets/reader.css */
:root {
  --reader-bg: #0a0f1a;
  --reader-surface: rgba(255,255,255,0.06);
  --reader-border: rgba(255,255,255,0.1);
  --reader-text: #f1f5f9;
  --reader-muted: #94a3b8;
  --reader-accent: #60a5fa;
  --reader-error: #f87171;
  --reader-overlay: rgba(0,0,0,0.8);
  --reader-bar-h: 48px;
  --reader-strip-h: 72px;
  --reader-anim: 0.28s ease;
}

.reader-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(148,163,184,0.2);
  border-top-color: var(--reader-accent);
  border-radius: 50%;
  animation: reader-spin 0.8s linear infinite;
}
@keyframes reader-spin { to { transform: rotate(360deg); } }

.reader-btn {
  background: none;
  border: none;
  color: var(--reader-text);
  cursor: pointer;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 14px;
  line-height: 1;
  transition: background var(--reader-anim);
  white-space: nowrap;
}
.reader-btn:hover { background: rgba(255,255,255,0.1); }
.reader-btn:active { background: rgba(255,255,255,0.15); }
.reader-btn:disabled { opacity: 0.3; cursor: default; pointer-events: none; }

/* Book/Scroll view transition animations */

/* Slide: enter from left (RTL forward / LTR backward) */
.slide-left-enter-from  { transform: translateX(-100%); }
.slide-left-leave-to    { transform: translateX(100%); }
.slide-left-enter-active,
.slide-left-leave-active { transition: transform var(--reader-anim); }

/* Slide: enter from right (LTR forward / RTL backward) */
.slide-right-enter-from  { transform: translateX(100%); }
.slide-right-leave-to    { transform: translateX(-100%); }
.slide-right-enter-active,
.slide-right-leave-active { transition: transform var(--reader-anim); }

/* Flip: pages come from left */
.flip-left-enter-from  { transform: perspective(1200px) rotateY(90deg);  opacity: 0; }
.flip-left-leave-to    { transform: perspective(1200px) rotateY(-90deg); opacity: 0; }
.flip-left-enter-active,
.flip-left-leave-active  { transition: transform var(--reader-anim), opacity var(--reader-anim); }

/* Flip: pages come from right */
.flip-right-enter-from  { transform: perspective(1200px) rotateY(-90deg); opacity: 0; }
.flip-right-leave-to    { transform: perspective(1200px) rotateY(90deg);  opacity: 0; }
.flip-right-enter-active,
.flip-right-leave-active { transition: transform var(--reader-anim), opacity var(--reader-anim); }

/* Instant (no animation) */
.instant-enter-active,
.instant-leave-active { transition: none; }
```

- [ ] **Step 2: 验证文件存在**

```bash
ls web-static/src/assets/reader.css
```

Expected: 文件存在，无报错。

- [ ] **Step 3: Commit**

```bash
git add web-static/src/assets/reader.css
git commit -m "feat(reader): add reader.css design tokens and transition classes"
```

---

## Task 2: useReader.ts — 核心 composable

**Files:**
- Create: `web-static/src/composables/useReader.ts`

- [ ] **Step 1: 创建 useReader.ts**

```typescript
// web-static/src/composables/useReader.ts
import { ref, reactive, computed } from 'vue'
import type { InjectionKey } from 'vue'

const API_BASE = (import.meta as any).env?.VITE_API_BASE ?? 'https://no-hentai.vercel.app'
const SETTINGS_KEY = 'reader-settings'

export interface PageInfo {
  pageNum: number
  pageUrl: string
  thumbSprite: string
  thumbX: number
  thumbW: number
  thumbH: number
}

export interface ImageData {
  imageUrl: string
  nlParam: string | null
}

export interface ReaderSettings {
  readingMode: 'book' | 'scroll'
  bookDirection: 'rtl' | 'ltr'
  pageTurnAnimation: 'slide' | 'flip' | 'none'
  pagesPerScreen: 1 | 2
  widthScale: number
  scrollPageMargin: number
}

const DEFAULT_SETTINGS: ReaderSettings = {
  readingMode: 'book',
  bookDirection: 'rtl',
  pageTurnAnimation: 'slide',
  pagesPerScreen: 2,
  widthScale: 100,
  scrollPageMargin: 8,
}

function loadSettings(): ReaderSettings {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY)
    if (!raw) return { ...DEFAULT_SETTINGS }
    return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) }
  } catch {
    return { ...DEFAULT_SETTINGS }
  }
}

export function useReader() {
  const pages = ref<PageInfo[]>([])
  const total = ref(0)
  const galleryTitle = ref('')
  const initLoading = ref(true)
  const initError = ref<string | null>(null)
  const currentPage = ref(1)
  const windowWidth = ref(window.innerWidth)
  const settings = reactive<ReaderSettings>(loadSettings())
  const imageCache = new Map<number, ImageData>()

  const effectivePagesPerScreen = computed<1 | 2>(() =>
    settings.pagesPerScreen === 2 && windowWidth.value >= 900 ? 2 : 1
  )

  function onResize() {
    windowWidth.value = window.innerWidth
  }

  function updateSetting<K extends keyof ReaderSettings>(key: K, value: ReaderSettings[K]) {
    (settings as ReaderSettings)[key] = value as any
    try { localStorage.setItem(SETTINGS_KEY, JSON.stringify({ ...settings })) } catch {}
  }

  async function init(gid: string, token: string, startPage: number) {
    initLoading.value = true
    initError.value = null
    try {
      const res = await fetch(`${API_BASE}/api/gallery-images?gid=${encodeURIComponent(gid)}&token=${encodeURIComponent(token)}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      if (data.error) throw new Error(data.error)
      pages.value = (data.images ?? []) as PageInfo[]
      total.value = data.total as number
      galleryTitle.value = `Gallery #${gid}`
    } catch (e: any) {
      initError.value = e.message ?? 'Failed to load gallery'
    } finally {
      initLoading.value = false
      if (!initError.value) goTo(startPage)
    }
  }

  async function getImageUrl(pageNum: number): Promise<ImageData> {
    const cached = imageCache.get(pageNum)
    if (cached) return cached
    const pg = pages.value.find(p => p.pageNum === pageNum)
    if (!pg) throw new Error(`Page ${pageNum} not found`)
    const res = await fetch(`${API_BASE}/api/image-url?pageUrl=${encodeURIComponent(pg.pageUrl)}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (data.error) throw new Error(data.error)
    const result: ImageData = { imageUrl: data.imageUrl, nlParam: data.nlParam ?? null }
    imageCache.set(pageNum, result)
    return result
  }

  async function retryImage(pageNum: number, nlParam?: string | null): Promise<ImageData> {
    imageCache.delete(pageNum)
    const pg = pages.value.find(p => p.pageNum === pageNum)
    if (!pg) throw new Error(`Page ${pageNum} not found`)
    let pageUrl = pg.pageUrl
    if (nlParam) pageUrl += (pageUrl.includes('?') ? '&' : '?') + `nl=${encodeURIComponent(nlParam)}`
    const res = await fetch(`${API_BASE}/api/image-url?pageUrl=${encodeURIComponent(pageUrl)}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (data.error) throw new Error(data.error)
    const result: ImageData = { imageUrl: data.imageUrl, nlParam: data.nlParam ?? null }
    imageCache.set(pageNum, result)
    return result
  }

  function preload(center: number) {
    const step = effectivePagesPerScreen.value
    for (const off of [1, -1, 2, -2, 3, -3]) {
      const n = center + off * step
      if (n >= 1 && n <= total.value) getImageUrl(n).catch(() => {})
    }
  }

  function goTo(pageNum: number) {
    const n = Math.max(1, Math.min(total.value, pageNum))
    currentPage.value = n
    preload(n)
  }

  function prev() { goTo(currentPage.value - effectivePagesPerScreen.value) }
  function next() { goTo(currentPage.value + effectivePagesPerScreen.value) }

  return {
    pages, total, galleryTitle, initLoading, initError,
    currentPage, settings, effectivePagesPerScreen, windowWidth,
    imageCache, getImageUrl, retryImage,
    updateSetting, init, goTo, prev, next, onResize,
  }
}

export type ReaderState = ReturnType<typeof useReader>
export const READER_KEY: InjectionKey<ReaderState> = Symbol('reader')
```

- [ ] **Step 2: 检查 TypeScript 编译**

```bash
cd web-static && npx vue-tsc --noEmit 2>&1 | head -30
```

Expected: 无 `useReader.ts` 相关错误（其他文件的既有错误可忽略）。

- [ ] **Step 3: Commit**

```bash
git add web-static/src/composables/useReader.ts
git commit -m "feat(reader): add useReader composable with state, API, cache, settings"
```

---

## Task 3: GalleryReader.vue — 根容器

**Files:**
- Create: `web-static/src/components/reader/GalleryReader.vue`

- [ ] **Step 1: 创建目录并新建 GalleryReader.vue**

```bash
mkdir -p web-static/src/components/reader
```

```vue
<!-- web-static/src/components/reader/GalleryReader.vue -->
<template>
  <div class="gr-root">
    <!-- Init loading -->
    <div v-if="initLoading" class="gr-center">
      <div class="reader-spinner" />
      <p style="color: var(--reader-muted); margin: 0">Loading gallery…</p>
    </div>

    <!-- Init error -->
    <div v-else-if="initError" class="gr-center gr-error">
      <p>{{ initError }}</p>
      <button class="reader-btn" @click="router.back()">← Back</button>
    </div>

    <!-- Reader -->
    <template v-else>
      <ReaderTopBar
        :bar-visible="barVisible"
        :show-thumb-grid="showThumbGrid"
        :show-settings="showSettings"
        @back="router.back()"
        @toggle-thumb-grid="showThumbGrid = !showThumbGrid"
        @toggle-settings="showSettings = !showSettings"
        @mouseover="showBar"
      />

      <BookView   v-if="settings.readingMode === 'book'"   @toggle-bar="toggleBar" />
      <ScrollView v-else @toggle-bar="toggleBar" />

      <ThumbStrip :bar-visible="barVisible" />

      <Teleport to="body">
        <ThumbGrid    v-if="showThumbGrid" @close="showThumbGrid = false" />
        <SettingsPanel v-if="showSettings" @close="showSettings = false" />
      </Teleport>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, provide, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useReader, READER_KEY } from '@/composables/useReader'
import ReaderTopBar  from './ReaderTopBar.vue'
import BookView      from './BookView.vue'
import ScrollView    from './ScrollView.vue'
import ThumbStrip    from './ThumbStrip.vue'
import ThumbGrid     from './ThumbGrid.vue'
import SettingsPanel from './SettingsPanel.vue'
import '@/assets/reader.css'

const route  = useRoute()
const router = useRouter()

const reader = useReader()
provide(READER_KEY, reader)

const { initLoading, initError, settings, prev, next, updateSetting, onResize, init } = reader

const gid       = route.params.gid as string
const token     = (route.query.token as string) || ''
const startPage = parseInt(route.query.page as string) || 1

const barVisible    = ref(true)
const showThumbGrid = ref(false)
const showSettings  = ref(false)
let barTimer: ReturnType<typeof setTimeout> | null = null

function showBar() {
  barVisible.value = true
  resetBarTimer()
}
function toggleBar() {
  barVisible.value = !barVisible.value
  if (barVisible.value) resetBarTimer()
}
function resetBarTimer() {
  if (barTimer) clearTimeout(barTimer)
  barTimer = setTimeout(() => { barVisible.value = false }, 4000)
}

function onKey(e: KeyboardEvent) {
  if ((e.target as HTMLElement).tagName === 'INPUT') return
  showBar()
  const rtl = settings.bookDirection === 'rtl'
  switch (e.key) {
    case 'ArrowLeft':
    case 'a': rtl ? next() : prev(); break
    case 'ArrowRight':
    case 'd': rtl ? prev() : next(); break
    case 'Escape':
      if (showThumbGrid.value) { showThumbGrid.value = false; return }
      if (showSettings.value)  { showSettings.value  = false; return }
      router.back(); break
    case 'f': case 'F': showThumbGrid.value = !showThumbGrid.value; break
    case 's': case 'S': showSettings.value  = !showSettings.value;  break
    case 'm': case 'M':
      updateSetting('readingMode', settings.readingMode === 'book' ? 'scroll' : 'book'); break
  }
}

onMounted(async () => {
  window.addEventListener('keydown', onKey)
  window.addEventListener('resize', onResize)
  resetBarTimer()
  await init(gid, token, startPage)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('resize', onResize)
  if (barTimer) clearTimeout(barTimer)
})
</script>

<style scoped>
.gr-root {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: var(--reader-bg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  user-select: none;
  color: var(--reader-text);
}
.gr-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--reader-muted);
}
.gr-error { color: var(--reader-error); }
</style>
```

- [ ] **Step 2: 验证编译**

```bash
cd web-static && npx vue-tsc --noEmit 2>&1 | grep "GalleryReader" | head -10
```

Expected: 无 GalleryReader 相关错误。

- [ ] **Step 3: Commit**

```bash
git add web-static/src/components/reader/GalleryReader.vue
git commit -m "feat(reader): add GalleryReader root container with keyboard/lifecycle"
```

---

## Task 4: ReaderTopBar.vue — 顶部栏

**Files:**
- Create: `web-static/src/components/reader/ReaderTopBar.vue`

- [ ] **Step 1: 创建 ReaderTopBar.vue**

```vue
<!-- web-static/src/components/reader/ReaderTopBar.vue -->
<template>
  <div
    class="top-bar"
    :class="{ 'top-bar-hidden': !barVisible }"
    @mouseover="$emit('mouseover')"
  >
    <button class="reader-btn top-bar-back" @click="$emit('back')">← Back</button>
    <span class="top-bar-title">{{ galleryTitle }}</span>
    <span class="top-bar-counter">{{ pageCounter }}</span>
    <button
      class="reader-btn"
      :class="{ 'btn-active': showThumbGrid }"
      title="Thumbnails (F)"
      @click="$emit('toggleThumbGrid')"
    >⊞</button>
    <button
      class="reader-btn"
      :class="{ 'btn-active': showSettings }"
      title="Settings (S)"
      @click="$emit('toggleSettings')"
    >⚙</button>
  </div>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { READER_KEY } from '@/composables/useReader'

defineProps<{
  barVisible: boolean
  showThumbGrid: boolean
  showSettings: boolean
}>()
defineEmits<{
  back: []
  toggleThumbGrid: []
  toggleSettings: []
  mouseover: []
}>()

const reader = inject(READER_KEY)!
const { galleryTitle, currentPage, total, effectivePagesPerScreen } = reader

const pageCounter = computed(() => {
  const p = currentPage.value
  const t = total.value
  const step = effectivePagesPerScreen.value
  if (step === 2 && p < t) return `${p}–${p + 1} / ${t}`
  return `${p} / ${t}`
})
</script>

<style scoped>
.top-bar {
  position: relative;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px;
  height: var(--reader-bar-h);
  background: linear-gradient(to bottom, rgba(0,0,0,0.85), transparent);
  transition: opacity 0.3s;
  flex-shrink: 0;
}
.top-bar-hidden { opacity: 0; pointer-events: none; }
.top-bar-back { flex-shrink: 0; }
.top-bar-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  color: var(--reader-muted);
  min-width: 0;
}
.top-bar-counter {
  font-size: 13px;
  color: var(--reader-muted);
  flex-shrink: 0;
}
.btn-active { background: rgba(96,165,250,0.2); color: var(--reader-accent); }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web-static/src/components/reader/ReaderTopBar.vue
git commit -m "feat(reader): add ReaderTopBar with title, counter, controls"
```

---

## Task 5: PageImage.vue — 图片槽（懒加载 + 重试）

**Files:**
- Create: `web-static/src/components/reader/PageImage.vue`

- [ ] **Step 1: 创建 PageImage.vue**

```vue
<!-- web-static/src/components/reader/PageImage.vue -->
<template>
  <div ref="elRef" class="page-image">
    <div v-if="state === 'loading'" class="pi-center">
      <div class="reader-spinner" />
    </div>
    <img
      v-show="state === 'loaded'"
      :src="imgSrc"
      class="pi-img"
      draggable="false"
      @load="onLoad"
      @error="onImgError"
    />
    <div v-if="state === 'error'" class="pi-center pi-error">
      <p>Failed to load page {{ pageNum }}</p>
      <button class="reader-btn" @click="retry">Retry</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, inject } from 'vue'
import { READER_KEY } from '@/composables/useReader'

const props = defineProps<{
  pageNum: number
  lazy?: boolean
}>()

const reader = inject(READER_KEY)!
const { getImageUrl, retryImage } = reader

type State = 'idle' | 'loading' | 'loaded' | 'error'
const state  = ref<State>('idle')
const imgSrc = ref('')
const elRef  = ref<HTMLElement | null>(null)
let nlParam: string | null = null
let observer: IntersectionObserver | null = null

async function load() {
  state.value = 'loading'
  imgSrc.value = ''
  try {
    const data = await getImageUrl(props.pageNum)
    nlParam  = data.nlParam
    imgSrc.value = data.imageUrl
    // state transitions to 'loaded' via @load event
  } catch {
    state.value = 'error'
  }
}

async function retry() {
  state.value = 'loading'
  imgSrc.value = ''
  try {
    const data = await retryImage(props.pageNum, nlParam)
    nlParam  = data.nlParam
    imgSrc.value = data.imageUrl
  } catch {
    state.value = 'error'
  }
}

function onLoad()     { state.value = 'loaded' }
function onImgError() { state.value = 'error' }

function startLoad() {
  if (state.value !== 'idle') return
  load()
}

onMounted(() => {
  if (!props.lazy) {
    startLoad()
    return
  }
  observer = new IntersectionObserver(
    entries => {
      if (entries[0].isIntersecting) {
        startLoad()
        observer?.disconnect()
        observer = null
      }
    },
    { rootMargin: '300px' }
  )
  observer.observe(elRef.value!)
})

onBeforeUnmount(() => {
  observer?.disconnect()
})

watch(() => props.pageNum, () => {
  state.value = 'idle'
  imgSrc.value = ''
  nlParam = null
  observer?.disconnect()
  observer = null
  if (!props.lazy) startLoad()
  // lazy mode: re-attach observer
  else {
    state.value = 'idle'
    if (elRef.value) {
      observer = new IntersectionObserver(entries => {
        if (entries[0].isIntersecting) { startLoad(); observer?.disconnect(); observer = null }
      }, { rootMargin: '300px' })
      observer.observe(elRef.value)
    }
  }
})
</script>

<style scoped>
.page-image {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  min-height: 200px;
}
.pi-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 100%;
  width: 100%;
  position: absolute;
  inset: 0;
}
.pi-error { color: var(--reader-error); font-size: 13px; text-align: center; }
.pi-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  display: block;
  pointer-events: none;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web-static/src/components/reader/PageImage.vue
git commit -m "feat(reader): add PageImage with lazy IntersectionObserver and retry"
```

---

## Task 6: BookView.vue — 书本翻页模式

**Files:**
- Create: `web-static/src/components/reader/BookView.vue`

- [ ] **Step 1: 创建 BookView.vue**

```vue
<!-- web-static/src/components/reader/BookView.vue -->
<template>
  <div
    class="book-view"
    :style="{ '--width-scale': settings.widthScale / 100 }"
    @touchstart.passive="onTouchStart"
    @touchend.passive="onTouchEnd"
  >
    <Transition :name="transitionName">
      <div
        :key="currentPage"
        class="spread"
        :class="{
          'spread-double': effectivePagesPerScreen === 2,
          'spread-rtl': settings.bookDirection === 'rtl',
        }"
      >
        <PageImage
          class="page-slot"
          :page-num="currentPage"
          :style="pageStyle"
        />
        <PageImage
          v-if="effectivePagesPerScreen === 2 && currentPage < total"
          class="page-slot"
          :page-num="currentPage + 1"
          :style="pageStyle"
        />
      </div>
    </Transition>

    <!-- Click zones -->
    <div class="click-zone click-zone-left"   @click="onClickLeft"   />
    <div class="click-zone click-zone-center" @click="$emit('toggleBar')" />
    <div class="click-zone click-zone-right"  @click="onClickRight"  />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, inject } from 'vue'
import { READER_KEY } from '@/composables/useReader'
import PageImage from './PageImage.vue'

defineEmits<{ toggleBar: [] }>()

const reader = inject(READER_KEY)!
const { currentPage, total, settings, effectivePagesPerScreen, prev, next } = reader

// Track flip direction to pick the right CSS transition
const flipDir = ref<'forward' | 'backward'>('forward')
let lastPage = currentPage.value

watch(currentPage, newVal => {
  flipDir.value = newVal > lastPage ? 'forward' : 'backward'
  lastPage = newVal
})

const transitionName = computed(() => {
  if (settings.pageTurnAnimation === 'none') return 'instant'
  // RTL + forward → visual: LEFT;  RTL + backward → visual: RIGHT
  // LTR + forward → visual: RIGHT; LTR + backward → visual: LEFT
  const rtl = settings.bookDirection === 'rtl'
  const fwd = flipDir.value === 'forward'
  const dir = (rtl ? fwd : !fwd) ? 'left' : 'right'
  return `${settings.pageTurnAnimation}-${dir}`
})

const pageStyle = computed(() => ({
  maxWidth: `calc(${settings.widthScale}% / ${effectivePagesPerScreen.value})`,
}))

// RTL: ← key = forward (page++); click LEFT = forward
function onClickLeft()  { settings.bookDirection === 'rtl' ? next() : prev() }
function onClickRight() { settings.bookDirection === 'rtl' ? prev() : next() }

// Touch swipe
let touchX = 0
function onTouchStart(e: TouchEvent) { touchX = e.touches[0].clientX }
function onTouchEnd(e: TouchEvent) {
  const dx = e.changedTouches[0].clientX - touchX
  if (Math.abs(dx) < 40) return
  dx < 0 ? onClickRight() : onClickLeft()
}
</script>

<style scoped>
.book-view {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: var(--reader-bg);
}

/* Spread: the "page spread" that gets transitioned */
.spread {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  position: absolute;
  inset: 0;
}
.spread-rtl { flex-direction: row-reverse; }

.page-slot {
  flex: 1 1 0;
  min-width: 0;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
/* Single page: constrain width */
.spread:not(.spread-double) .page-slot {
  flex: 0 0 auto;
  max-height: 100%;
}
.spread-double .page-slot:first-child  { justify-content: flex-end; }
.spread-double .page-slot:last-child   { justify-content: flex-start; }

/* Click zones */
.click-zone {
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 5;
  cursor: pointer;
}
.click-zone-left   { left: 0;   width: 30%; }
.click-zone-center { left: 30%; width: 40%; }
.click-zone-right  { right: 0;  width: 30%; }
</style>
```

- [ ] **Step 2: 启动开发服务器，验证书本模式**

```bash
cd web-static && npm run dev
```

打开 `http://localhost:3000`，通过 GalleryDetail 进入 `/gallery/:gid/read`（此时路由还指向旧文件，需在 Task 11 切换）。

先通过直接修改路由临时测试：在 `router/index.ts` 将 GalleryReader import 路径改为 `@/components/reader/GalleryReader.vue`，刷新后验证：
- 画廊加载完成
- 书本模式显示图片
- 左右点击区域翻页
- 宽屏时显示双页
- RTL 方向正确（当前页在右）
- slide 动画播放

- [ ] **Step 3: Commit**

```bash
git add web-static/src/components/reader/BookView.vue
git commit -m "feat(reader): add BookView with RTL double-page and slide/flip transitions"
```

---

## Task 7: ScrollView.vue — 连续滚动模式

**Files:**
- Create: `web-static/src/components/reader/ScrollView.vue`

- [ ] **Step 1: 创建 ScrollView.vue**

```vue
<!-- web-static/src/components/reader/ScrollView.vue -->
<template>
  <div
    ref="scrollEl"
    class="scroll-view"
    @click="onScrollClick"
  >
    <PageImage
      v-for="pg in pages"
      :key="pg.pageNum"
      :page-num="pg.pageNum"
      :lazy="true"
      class="scroll-page"
      :style="{
        marginBottom: `${settings.scrollPageMargin}px`,
        maxWidth: `${settings.widthScale}%`,
      }"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, inject, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { READER_KEY } from '@/composables/useReader'
import PageImage from './PageImage.vue'

defineEmits<{ toggleBar: [] }>()

const reader = inject(READER_KEY)!
const { pages, currentPage, settings, total, goTo } = reader

const scrollEl = ref<HTMLElement | null>(null)
let pageEls: HTMLElement[] = []
let scrollObserver: IntersectionObserver | null = null
let programmaticScroll = false

// Keep refs to each PageImage root element to observe them
function setupScrollObserver() {
  scrollObserver?.disconnect()
  if (!scrollEl.value) return
  pageEls = Array.from(scrollEl.value.querySelectorAll<HTMLElement>('.scroll-page'))

  scrollObserver = new IntersectionObserver(
    entries => {
      if (programmaticScroll) return
      let best: { pageNum: number; ratio: number } | null = null
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        const pageNum = parseInt((entry.target as HTMLElement).dataset.page ?? '0')
        if (!best || entry.intersectionRatio > best.ratio) {
          best = { pageNum, ratio: entry.intersectionRatio }
        }
      }
      if (best) currentPage.value = best.pageNum
    },
    { threshold: [0, 0.25, 0.5, 0.75, 1] }
  )

  pageEls.forEach((el, i) => {
    el.dataset.page = String(pages.value[i]?.pageNum ?? i + 1)
    scrollObserver!.observe(el)
  })
}

// goTo in scroll mode: smooth scroll to page
watch(currentPage, async (n, old) => {
  if (n === old) return
  await nextTick()
  const el = scrollEl.value?.querySelectorAll<HTMLElement>('.scroll-page')[n - 1]
  if (!el) return
  programmaticScroll = true
  el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  setTimeout(() => { programmaticScroll = false }, 600)
}, { flush: 'post' })

onMounted(async () => {
  await nextTick()
  setupScrollObserver()
})
onBeforeUnmount(() => { scrollObserver?.disconnect() })

function onScrollClick(e: MouseEvent) {
  const ratio = e.clientX / window.innerWidth
  if (ratio < 0.3) goTo(Math.max(1, currentPage.value - 1))
  else if (ratio > 0.7) goTo(Math.min(total.value, currentPage.value + 1))
  // middle click handled by parent via toggleBar if needed
}
</script>

<style scoped>
.scroll-view {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  align-items: center;
  background: var(--reader-bg);
  padding: 0;
  scrollbar-width: thin;
  scrollbar-color: rgba(148,163,184,0.3) transparent;
}
.scroll-page {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  min-height: 200px;
}
</style>
```

- [ ] **Step 2: 验证滚动模式**

在 SettingsPanel 完成前，临时在浏览器 console 修改：
```javascript
// 在 GalleryReader 提供的 reader 中
// 或直接在 GalleryReader.vue 中将 settings.readingMode 改为 'scroll'
```

检查：
- 所有页垂直排列
- 滚动时图片懒加载
- 顶部页码随滚动更新

- [ ] **Step 3: Commit**

```bash
git add web-static/src/components/reader/ScrollView.vue
git commit -m "feat(reader): add ScrollView with IntersectionObserver lazy loading"
```

---

## Task 8: ThumbStrip.vue — 底部缩略图条

**Files:**
- Create: `web-static/src/components/reader/ThumbStrip.vue`

- [ ] **Step 1: 创建 ThumbStrip.vue**

```vue
<!-- web-static/src/components/reader/ThumbStrip.vue -->
<template>
  <div class="thumb-strip" :class="{ 'strip-hidden': !barVisible }" ref="stripEl">
    <button
      v-for="pg in pages"
      :key="pg.pageNum"
      class="thumb-item"
      :class="{ 'thumb-active': pg.pageNum === currentPage }"
      @click="goTo(pg.pageNum)"
    >
      <div class="thumb-sprite" :style="spriteStyle(pg)" />
      <span class="thumb-num">{{ pg.pageNum }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, inject } from 'vue'
import { READER_KEY } from '@/composables/useReader'
import type { PageInfo } from '@/composables/useReader'

defineProps<{ barVisible: boolean }>()

const reader = inject(READER_KEY)!
const { pages, currentPage, goTo } = reader
const stripEl = ref<HTMLElement | null>(null)

function spriteStyle(pg: PageInfo) {
  const url = pg.thumbSprite.replace(/['"]/g, '')
  const scale = 60 / (pg.thumbH || 60)  // fit into strip height
  return {
    backgroundImage: `url(${url})`,
    backgroundPosition: `${pg.thumbX * scale}px 0`,
    backgroundRepeat: 'no-repeat',
    backgroundSize: `auto ${60}px`,
    width:  `${(pg.thumbW || 42) * scale}px`,
    height: '60px',
    flexShrink: '0',
  }
}

watch(currentPage, async () => {
  await nextTick()
  stripEl.value?.querySelector<HTMLElement>('.thumb-active')?.scrollIntoView({
    behavior: 'smooth',
    block: 'nearest',
    inline: 'center',
  })
})
</script>

<style scoped>
.thumb-strip {
  display: flex;
  flex-direction: row;
  align-items: center;
  height: var(--reader-strip-h);
  background: linear-gradient(to top, rgba(0,0,0,0.85), transparent);
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
  flex-shrink: 0;
  transition: opacity 0.3s;
  gap: 4px;
  padding: 0 8px;
}
.thumb-strip::-webkit-scrollbar { display: none; }
.strip-hidden { opacity: 0; pointer-events: none; }

.thumb-item {
  border: none;
  background: transparent;
  padding: 2px;
  cursor: pointer;
  border-radius: 3px;
  border: 2px solid transparent;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  transition: border-color 0.15s;
}
.thumb-item:hover { border-color: rgba(96,165,250,0.5); }
.thumb-active { border-color: var(--reader-accent) !important; }

.thumb-sprite { display: block; }

.thumb-num {
  font-size: 10px;
  color: var(--reader-muted);
  line-height: 1;
}
</style>
```

- [ ] **Step 2: 验证缩略图条**

检查：
- 底部显示 sprite 缩略图横向条
- 当前页高亮蓝边框
- 点击缩略图跳页
- 翻页时自动滚动居中当前缩略图

- [ ] **Step 3: Commit**

```bash
git add web-static/src/components/reader/ThumbStrip.vue
git commit -m "feat(reader): add ThumbStrip with sprite thumbnails and auto-scroll"
```

---

## Task 9: ThumbGrid.vue — 全屏缩略图网格

**Files:**
- Create: `web-static/src/components/reader/ThumbGrid.vue`

- [ ] **Step 1: 创建 ThumbGrid.vue**

```vue
<!-- web-static/src/components/reader/ThumbGrid.vue -->
<template>
  <div class="tg-overlay" @click.self="$emit('close')">
    <div class="tg-panel">
      <div class="tg-header">
        <span class="tg-title">{{ total }} pages</span>
        <button class="reader-btn" @click="$emit('close')">✕</button>
      </div>
      <div class="tg-grid">
        <button
          v-for="pg in pages"
          :key="pg.pageNum"
          class="tg-item"
          :class="{ 'tg-active': pg.pageNum === currentPage }"
          @click="onSelect(pg.pageNum)"
        >
          <div class="tg-sprite" :style="spriteStyle(pg)" />
          <span class="tg-num">{{ pg.pageNum }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { READER_KEY } from '@/composables/useReader'
import type { PageInfo } from '@/composables/useReader'

const emit = defineEmits<{ close: [] }>()

const reader = inject(READER_KEY)!
const { pages, currentPage, total, goTo } = reader

function onSelect(pageNum: number) {
  goTo(pageNum)
  emit('close')
}

function spriteStyle(pg: PageInfo) {
  const url = pg.thumbSprite.replace(/['"]/g, '')
  const targetH = 120
  const scale = targetH / (pg.thumbH || 120)
  return {
    backgroundImage: `url(${url})`,
    backgroundPosition: `${pg.thumbX * scale}px 0`,
    backgroundRepeat: 'no-repeat',
    backgroundSize: `auto ${targetH}px`,
    width:  `${(pg.thumbW || 85) * scale}px`,
    height: `${targetH}px`,
  }
}
</script>

<style scoped>
.tg-overlay {
  position: fixed;
  inset: 0;
  z-index: 300;
  background: var(--reader-overlay);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.tg-panel {
  width: 100%;
  max-height: 75vh;
  background: #111827;
  border-radius: 16px 16px 0 0;
  display: flex;
  flex-direction: column;
}
.tg-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px 8px;
  border-bottom: 1px solid var(--reader-border);
  flex-shrink: 0;
}
.tg-title { font-size: 14px; color: var(--reader-muted); }

.tg-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px;
  overflow-y: auto;
  justify-content: center;
}
.tg-item {
  border: 2px solid transparent;
  background: var(--reader-surface);
  border-radius: 6px;
  cursor: pointer;
  padding: 4px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  transition: border-color 0.15s;
}
.tg-item:hover { border-color: rgba(96,165,250,0.5); }
.tg-active { border-color: var(--reader-accent) !important; }
.tg-sprite { display: block; border-radius: 3px; }
.tg-num { font-size: 11px; color: var(--reader-muted); }
</style>
```

- [ ] **Step 2: 验证全屏网格**

按 `F` 键或点击 TopBar 网格按钮，检查：
- 底部弹出全屏网格
- sprite 缩略图正确显示
- 当前页高亮
- 点击页面跳转并关闭网格
- 点击遮罩关闭网格

- [ ] **Step 3: Commit**

```bash
git add web-static/src/components/reader/ThumbGrid.vue
git commit -m "feat(reader): add ThumbGrid fullscreen thumbnail grid"
```

---

## Task 10: SettingsPanel.vue — 设置抽屉

**Files:**
- Create: `web-static/src/components/reader/SettingsPanel.vue`

- [ ] **Step 1: 创建 SettingsPanel.vue**

```vue
<!-- web-static/src/components/reader/SettingsPanel.vue -->
<template>
  <div class="sp-overlay" @click.self="$emit('close')">
    <div class="sp-panel">
      <div class="sp-header">
        <span>Settings</span>
        <button class="reader-btn" @click="$emit('close')">✕</button>
      </div>

      <div class="sp-body">
        <!-- Reading Mode -->
        <div class="sp-row">
          <span class="sp-label">Mode</span>
          <div class="sp-radio-group">
            <label class="sp-radio">
              <input type="radio" :checked="settings.readingMode === 'book'"
                @change="update('readingMode', 'book')" />
              Book
            </label>
            <label class="sp-radio">
              <input type="radio" :checked="settings.readingMode === 'scroll'"
                @change="update('readingMode', 'scroll')" />
              Scroll
            </label>
          </div>
        </div>

        <!-- Direction (book only) -->
        <div class="sp-row" v-show="settings.readingMode === 'book'">
          <span class="sp-label">Direction</span>
          <div class="sp-radio-group">
            <label class="sp-radio">
              <input type="radio" :checked="settings.bookDirection === 'rtl'"
                @change="update('bookDirection', 'rtl')" />
              RTL ←
            </label>
            <label class="sp-radio">
              <input type="radio" :checked="settings.bookDirection === 'ltr'"
                @change="update('bookDirection', 'ltr')" />
              LTR →
            </label>
          </div>
        </div>

        <!-- Animation (book only) -->
        <div class="sp-row" v-show="settings.readingMode === 'book'">
          <span class="sp-label">Animation</span>
          <div class="sp-radio-group">
            <label class="sp-radio">
              <input type="radio" :checked="settings.pageTurnAnimation === 'slide'"
                @change="update('pageTurnAnimation', 'slide')" />
              Slide
            </label>
            <label class="sp-radio">
              <input type="radio" :checked="settings.pageTurnAnimation === 'flip'"
                @change="update('pageTurnAnimation', 'flip')" />
              Flip
            </label>
            <label class="sp-radio">
              <input type="radio" :checked="settings.pageTurnAnimation === 'none'"
                @change="update('pageTurnAnimation', 'none')" />
              None
            </label>
          </div>
        </div>

        <!-- Width Scale -->
        <div class="sp-row sp-row-col">
          <div class="sp-label-row">
            <span class="sp-label">Width</span>
            <span class="sp-value">{{ settings.widthScale }}%</span>
          </div>
          <input
            type="range" min="50" max="150" step="5"
            :value="settings.widthScale"
            @input="update('widthScale', parseInt(($event.target as HTMLInputElement).value))"
            class="sp-slider"
          />
        </div>

        <!-- Scroll margin (scroll mode only) -->
        <div class="sp-row sp-row-col" v-show="settings.readingMode === 'scroll'">
          <div class="sp-label-row">
            <span class="sp-label">Page Gap</span>
            <span class="sp-value">{{ settings.scrollPageMargin }}px</span>
          </div>
          <input
            type="range" min="0" max="40" step="2"
            :value="settings.scrollPageMargin"
            @input="update('scrollPageMargin', parseInt(($event.target as HTMLInputElement).value))"
            class="sp-slider"
          />
        </div>

        <!-- Keyboard shortcuts reference -->
        <div class="sp-section-title">Keyboard Shortcuts</div>
        <div class="sp-shortcuts">
          <div class="sp-shortcut"><kbd>← / A</kbd><span>Visual prev</span></div>
          <div class="sp-shortcut"><kbd>→ / D</kbd><span>Visual next</span></div>
          <div class="sp-shortcut"><kbd>F</kbd><span>Thumbnail grid</span></div>
          <div class="sp-shortcut"><kbd>S</kbd><span>Settings</span></div>
          <div class="sp-shortcut"><kbd>M</kbd><span>Toggle mode</span></div>
          <div class="sp-shortcut"><kbd>Esc</kbd><span>Close / Back</span></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { READER_KEY } from '@/composables/useReader'
import type { ReaderSettings } from '@/composables/useReader'

defineEmits<{ close: [] }>()

const reader = inject(READER_KEY)!
const { settings, updateSetting } = reader

function update<K extends keyof ReaderSettings>(key: K, value: ReaderSettings[K]) {
  updateSetting(key, value)
}
</script>

<style scoped>
.sp-overlay {
  position: fixed;
  inset: 0;
  z-index: 300;
  background: var(--reader-overlay);
  display: flex;
  justify-content: flex-end;
}
.sp-panel {
  width: min(320px, 90vw);
  height: 100%;
  background: #111827;
  display: flex;
  flex-direction: column;
  box-shadow: -4px 0 20px rgba(0,0,0,0.5);
}
.sp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--reader-border);
  font-size: 15px;
  font-weight: 600;
  flex-shrink: 0;
}
.sp-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.sp-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.sp-row-col { flex-direction: column; align-items: stretch; }
.sp-label { font-size: 13px; color: var(--reader-muted); flex-shrink: 0; }
.sp-label-row { display: flex; justify-content: space-between; }
.sp-value { font-size: 13px; color: var(--reader-accent); }

.sp-radio-group { display: flex; gap: 8px; flex-wrap: wrap; }
.sp-radio {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  cursor: pointer;
  color: var(--reader-text);
}
.sp-radio input { accent-color: var(--reader-accent); cursor: pointer; }

.sp-slider {
  width: 100%;
  accent-color: var(--reader-accent);
  cursor: pointer;
}

.sp-section-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--reader-muted);
  padding-bottom: 4px;
  border-bottom: 1px solid var(--reader-border);
}
.sp-shortcuts { display: flex; flex-direction: column; gap: 6px; }
.sp-shortcut {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}
kbd {
  background: var(--reader-surface);
  border: 1px solid var(--reader-border);
  border-radius: 4px;
  padding: 2px 6px;
  font-family: monospace;
  font-size: 11px;
  color: var(--reader-text);
  min-width: 52px;
  text-align: center;
}
.sp-shortcut span { color: var(--reader-muted); }
</style>
```

- [ ] **Step 2: 验证设置面板**

按 `S` 键打开，检查：
- 右侧抽屉滑出
- 切换模式（Book/Scroll），主视图切换
- 调节宽度 slider，图片宽度实时变化
- 切换动画类型，翻页效果变化
- 刷新页面，设置从 localStorage 恢复

- [ ] **Step 3: Commit**

```bash
git add web-static/src/components/reader/SettingsPanel.vue
git commit -m "feat(reader): add SettingsPanel with all config options and keyboard reference"
```

---

## Task 11: 收尾 — 更新路由，删除旧文件

**Files:**
- Modify: `web-static/src/router/index.ts:13`
- Delete: `web-static/src/components/GalleryReader.vue`

- [ ] **Step 1: 更新 router/index.ts 的 import 路径**

将：
```typescript
import GalleryReader from '@/components/GalleryReader.vue'
```
改为：
```typescript
import GalleryReader from '@/components/reader/GalleryReader.vue'
```

路由定义本身（`path: '/gallery/:gid/read'`）不变。

- [ ] **Step 2: 删除旧 GalleryReader.vue**

```bash
rm web-static/src/components/GalleryReader.vue
```

- [ ] **Step 3: TypeScript 全量检查**

```bash
cd web-static && npx vue-tsc --noEmit 2>&1 | head -40
```

Expected: 无报错（或仅有与本次改动无关的既有错误）。

- [ ] **Step 4: 完整功能验收**

```bash
cd web-static && npm run dev
```

打开浏览器，访问任意画廊详情页，点击 "Read"，逐一验证：

| 验收项 | 预期结果 |
|--------|---------|
| 初始加载 | 显示 spinner，加载完成后渲染书本模式 |
| 默认 RTL + 双页 | 宽屏时当前页在右，下一页在左 |
| 点击右侧 30% | 回到上一页（RTL） |
| 点击左侧 30% | 前进到下一页（RTL） |
| `→` 键 | 回到上一页（RTL 视觉方向） |
| `←` 键 | 前进到下一页（RTL 视觉方向） |
| slide 动画 | 翻页时平移动画 |
| `S` 键 → 切换 flip | 翻页时 3D 翻书效果 |
| `M` 键 | 切换书本/滚动模式 |
| 滚动模式 | 所有页垂直排列，滚动懒加载 |
| 底部缩略图条 | 横向 sprite 缩略图，当前页高亮 |
| `F` 键 | 全屏网格弹出，点击跳页 |
| `Esc` 键（网格/设置开着） | 关闭网格/设置 |
| `Esc` 键（均关着） | 返回上一页 |
| 图片加载失败 | 显示 Retry 按钮，点击重试 |
| 窗口缩小到 <900px | 自动切换单页 |
| 刷新页面 | 设置从 localStorage 恢复 |

- [ ] **Step 5: Commit**

```bash
git add web-static/src/router/index.ts
git rm web-static/src/components/GalleryReader.vue
git commit -m "feat(reader): wire new reader to router, remove legacy GalleryReader.vue"
```

---

## 自检记录

**Spec coverage:**
- [x] 书本模式（BookView）
- [x] 滚动模式（ScrollView）
- [x] 双页自动切换（effectivePagesPerScreen computed）
- [x] RTL 默认 + 设置切换（SettingsPanel + BookView）
- [x] slide / flip / none 动画（reader.css + BookView transitionName）
- [x] 底部缩略图条（ThumbStrip）
- [x] 全屏缩略图网格（ThumbGrid）
- [x] 设置面板（SettingsPanel）
- [x] 键盘快捷键（GalleryReader onKey）
- [x] 移动端滑动（BookView onTouchStart/End）
- [x] 图片预加载（useReader preload）
- [x] 错误重试 + nlParam（PageImage retry + useReader retryImage）
- [x] 设置持久化（useReader updateSetting + loadSettings）
- [x] 旧文件删除（Task 11）

**Type consistency:**
- `READER_KEY` / `ReaderState` — 定义于 useReader.ts，所有组件统一从 `@/composables/useReader` import
- `PageInfo` / `ImageData` / `ReaderSettings` — 类型集中定义，组件按需 import
- `effectivePagesPerScreen` — computed 返回 `1 | 2`，BookView/TopBar/useReader 均使用此名
- `updateSetting` — 签名 `<K extends keyof ReaderSettings>(key, value)` 全链路一致
