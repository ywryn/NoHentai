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
