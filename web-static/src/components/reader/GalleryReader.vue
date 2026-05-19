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
