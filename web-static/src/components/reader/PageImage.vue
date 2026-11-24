<template>
  <div ref="elRef" class="page-image">
    <div v-if="state === 'loading'" class="pi-center pi-loading">
      <ImageLoadProgress stage="image" />
    </div>
    <img
      v-if="imgSrc"
      v-show="state === 'loaded'"
      :key="imgSrc"
      :src="imgSrc"
      :alt="`第 ${pageNum} 页`"
      class="pi-img"
      draggable="false"
      @load="onLoad"
      @error="onImgError"
    />
    <div v-if="state === 'error'" class="pi-center pi-error">
      <p>第 {{ pageNum }} 页加载失败{{ errorMessage ? `：${errorMessage}` : '' }}</p>
      <button class="reader-btn" @click="retry">重试</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, inject } from 'vue'
import ImageLoadProgress from '@/components/ui/ImageLoadProgress.vue'
import { READER_KEY } from '@/composables/useReader'

const props = withDefaults(defineProps<{
  pageNum: number
  lazy?: boolean
  active?: boolean
}>(), { active: true })

const reader = inject(READER_KEY)!
const { loadPageImage } = reader

type State = 'idle' | 'loading' | 'loaded' | 'error'
const state  = ref<State>('idle')
const imgSrc = ref('')
const elRef  = ref<HTMLElement | null>(null)
const errorMessage = ref('')
let observer: IntersectionObserver | null = null
let request: AbortController | undefined
let autoRetried = false

function clearImage() {
  request?.abort()
  if (imgSrc.value) URL.revokeObjectURL(imgSrc.value)
  imgSrc.value = ''
}

async function load(refresh = false) {
  clearImage()
  const controller = new AbortController()
  request = controller
  state.value = 'loading'
  errorMessage.value = ''
  autoRetried = refresh
  try {
    const { blob } = await loadPageImage(props.pageNum, { refresh, signal: controller.signal })
    if (!controller.signal.aborted) imgSrc.value = URL.createObjectURL(blob)
  } catch (error) {
    if (controller.signal.aborted) return
    errorMessage.value = error instanceof Error ? error.message : ''
    state.value = 'error'
  }
}

function retry() { void load(true) }
function isCurrent(event: Event) {
  return imgSrc.value && (event.currentTarget as HTMLImageElement).src === imgSrc.value
}
function onLoad(event: Event) {
  if (isCurrent(event)) state.value = 'loaded'
}
function onImgError(event: Event) {
  if (!isCurrent(event)) return
  if (!autoRetried) retry()
  else {
    errorMessage.value = '图片解码失败'
    state.value = 'error'
  }
}

function startLoad(force = false) {
  if (!force && state.value !== 'idle') return
  load()
}

function attachObserver() {
  if (!elRef.value) return
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
  observer.observe(elRef.value)
}

onMounted(() => {
  if (props.active === false) return
  if (!props.lazy) { startLoad(); return }
  attachObserver()
})

watch(() => props.active, active => {
  if (active === false) {
    observer?.disconnect()
    observer = null
    if (state.value === 'loading') {
      clearImage()
      state.value = 'idle'
    }
    return
  }
  observer?.disconnect()
  observer = null
  if (!props.lazy) startLoad(state.value !== 'loaded')
  else if (state.value === 'idle') attachObserver()
  else if (state.value === 'error') startLoad(true)
})

onBeforeUnmount(() => {
  clearImage()
  observer?.disconnect()
})

watch(() => props.pageNum, () => {
  state.value = 'idle'
  clearImage()
  autoRetried = false
  observer?.disconnect()
  observer = null
  if (props.active === false) return
  if (!props.lazy) startLoad()
  else attachObserver()
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
  position: absolute;
  inset: 0;
  z-index: 6;
}
.pi-error { color: var(--reader-error); font-size: 13px; text-align: center; }
.pi-loading {
  color: var(--reader-muted);
  font-size: 12px;
  pointer-events: none;
}
.pi-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  display: block;
  pointer-events: none;
}
</style>
