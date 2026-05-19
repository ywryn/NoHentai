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
let autoRetried = false

async function load() {
  state.value = 'loading'
  imgSrc.value = ''
  autoRetried = false
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

function onLoad() { state.value = 'loaded' }
function onImgError() {
  if (!autoRetried) {
    autoRetried = true
    retry()
  } else {
    state.value = 'error'
  }
}

function startLoad() {
  if (state.value !== 'idle') return
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
  if (!props.lazy) { startLoad(); return }
  attachObserver()
})

onBeforeUnmount(() => {
  observer?.disconnect()
})

watch(() => props.pageNum, () => {
  state.value = 'idle'
  imgSrc.value = ''
  nlParam = null
  autoRetried = false
  observer?.disconnect()
  observer = null
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
