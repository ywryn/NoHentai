<template>
  <div class="gr-root">
    <!-- Init loading -->
    <div v-if="initLoading" class="gr-center">
      <div class="reader-spinner" />
      <p style="color: var(--reader-muted); margin: 0">正在载入画廊…</p>
    </div>

    <!-- Init error -->
    <div v-else-if="initError" class="gr-center gr-error">
      <p>{{ initError }}</p>
      <button class="reader-btn" @click="exit">← 返回详情</button>
    </div>

    <!-- Reader -->
    <template v-else>
      <Transition name="gr-chrome">
        <ReaderTopBar
          v-show="chromeVisible"
          :show-sidebar="showSidebar"
          :show-thumb-grid="showThumbGrid"
          @back="exit"
          @toggle-sidebar="showSidebar = !showSidebar"
          @toggle-thumb-grid="showThumbGrid = !showThumbGrid"
        />
      </Transition>

      <div class="gr-content" @click="onSurfaceClick">
        <ThumbStrip v-if="showSidebar" />
        <BookView   v-if="settings.readingMode === 'book'" />
        <ScrollView v-else />
      </div>

      <!-- 首次进入的操作提示：点击区不可见，新用户无从得知怎么翻页 -->
      <Transition name="gr-chrome">
        <div v-if="showHint" class="gr-hint" @click="dismissHint">
          <div class="gr-hint-card">
            <p class="gr-hint-title">操作提示</p>
            <p>左右两侧点击或滑动翻页，中间区域点击可隐藏工具栏</p>
            <p class="gr-hint-keys">键盘：← → 翻页 · F 页目录 · M 切换模式 · Esc 退出</p>
            <button class="reader-btn gr-hint-btn" type="button">知道了</button>
          </div>
        </div>
      </Transition>

      <Teleport to="body">
        <ThumbGrid v-if="showThumbGrid" @close="showThumbGrid = false" />
      </Teleport>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, provide, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useReader, READER_KEY } from '@/composables/useReader'
import ReaderTopBar  from './ReaderTopBar.vue'
import BookView      from './BookView.vue'
import ScrollView    from './ScrollView.vue'
import ThumbStrip    from './ThumbStrip.vue'
import ThumbGrid     from './ThumbGrid.vue'
import '@/assets/reader.css'

const route  = useRoute()
const router = useRouter()

const reader = useReader()
provide(READER_KEY, reader)

const { initLoading, initError, settings, currentPage, prev, next, updateSetting, onResize, init } = reader

const gid       = route.params.gid as string
const token     = (route.query.token as string) || ''
const startPage = parseInt(route.query.page as string) || 1

const showSidebar   = ref(false)
const showThumbGrid = ref(false)
/** 工具栏显隐，由中间点击区切换，用于沉浸阅读 */
const chromeVisible = ref(true)

const HINT_KEY = 'reader-hint-seen'
const showHint = ref(false)

function dismissHint() {
  showHint.value = false
  try { localStorage.setItem(HINT_KEY, '1') } catch {}
}

/** 中间 40% 区域此前什么都不做，这里让它切换工具栏显隐 */
function onSurfaceClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.classList.contains('click-zone-center')) return
  chromeVisible.value = !chromeVisible.value
}

/** 直接粘贴 URL 进入时 router.back() 会把用户带离本站 */
function exit() {
  if (window.history.state?.back) router.back()
  else router.push({ name: 'GalleryDetail', params: { gid } })
}

function onKey(e: KeyboardEvent) {
  if ((e.target as HTMLElement).tagName === 'INPUT') return
  const rtl = settings.bookDirection === 'rtl'
  switch (e.key) {
    case 'ArrowLeft':
    case 'a': rtl ? next() : prev(); break
    case 'ArrowRight':
    case 'd': rtl ? prev() : next(); break
    case 'Escape':
      if (showThumbGrid.value) { showThumbGrid.value = false; return }
      if (showHint.value) { dismissHint(); return }
      exit(); break
    case 'f': case 'F': showThumbGrid.value = !showThumbGrid.value; break
    case 'm': case 'M':
      updateSetting('readingMode', settings.readingMode === 'book' ? 'scroll' : 'book'); break
  }
}

watch(currentPage, page => {
  const pageParam = String(page)
  if ((route.query.page as string | undefined) === pageParam) return
  router.replace({
    query: {
      ...route.query,
      page: pageParam,
    },
  })
})

onMounted(async () => {
  try { showHint.value = !localStorage.getItem(HINT_KEY) } catch { showHint.value = true }
  window.addEventListener('keydown', onKey)
  window.addEventListener('resize', onResize)
  await init(gid, token, startPage)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('resize', onResize)
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
.gr-content {
  flex: 1;
  display: flex;
  flex-direction: row;
  overflow: hidden;
  min-height: 0;
}

.gr-chrome-enter-active,
.gr-chrome-leave-active {
  transition: opacity var(--dur-base) var(--ease-out);
}
.gr-chrome-enter-from,
.gr-chrome-leave-to { opacity: 0; }

.gr-hint {
  position: absolute;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.72);
  cursor: pointer;
}

.gr-hint-card {
  max-width: 340px;
  padding: 20px 22px;
  border-radius: var(--radius-lg);
  background: rgba(30, 41, 59, 0.96);
  border: 1px solid var(--reader-border);
  text-align: center;
  color: var(--reader-text);
  font-size: 13px;
  line-height: 1.7;
}

.gr-hint-card p { margin: 0 0 6px; }

.gr-hint-title {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 10px !important;
}

.gr-hint-keys {
  color: var(--reader-muted);
  font-size: 12px;
}

.gr-hint-btn {
  margin-top: 12px;
  border: 1px solid var(--reader-border);
  min-height: var(--tap-target);
  padding: 0 20px;
}
</style>
