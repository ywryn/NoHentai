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
        :show-sidebar="showSidebar"
        :show-thumb-grid="showThumbGrid"
        @back="router.back()"
        @toggle-sidebar="showSidebar = !showSidebar"
        @toggle-thumb-grid="showThumbGrid = !showThumbGrid"
      />

      <div class="gr-content">
        <ThumbStrip v-if="showSidebar" />
        <BookView   v-if="settings.readingMode === 'book'" />
        <ScrollView v-else />
      </div>

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
      router.back(); break
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
</style>
