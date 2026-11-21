// web-static/src/composables/useReader.ts
import { ref, reactive, computed } from 'vue'
import { liveData, liveUrl } from '@/utils/live'
import type { InjectionKey } from 'vue'

const API_BASE = (import.meta as any).env?.VITE_API_BASE ?? ''
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

export function useReader(liveSite?: string) {
  const pages = ref<PageInfo[]>([])
  const total = ref(0)
  const galleryTitle = ref('')
  const initLoading = ref(true)
  const initError = ref<string | null>(null)
  const currentPage = ref(1)
  const navigation = ref({ page: 1, sequence: 0 })
  const windowWidth = ref(window.innerWidth)
  const windowHeight = ref(window.innerHeight)
  const settings = reactive<ReaderSettings>(loadSettings())
  const imageCache = new Map<number, ImageData>()
  const inflightCache = new Map<number, Promise<ImageData>>()

  /**
   * 双页对开的启用条件。
   * 原先要求 windowWidth >= 900，主流手机横屏（844–932px）大量机型
   * 够不着；改为「横向且够宽」判定，兼顾手机横屏与窄窗口桌面。
   */
  const effectivePagesPerScreen = computed<1 | 2>(() => {
    if (settings.pagesPerScreen !== 2) return 1
    const landscape = windowWidth.value > windowHeight.value
    return windowWidth.value >= (landscape ? 720 : 1024) ? 2 : 1
  })

  function onResize() {
    windowWidth.value = window.innerWidth
    windowHeight.value = window.innerHeight
  }

  function updateSetting<K extends keyof ReaderSettings>(key: K, value: ReaderSettings[K]) {
    (settings as ReaderSettings)[key] = value as any
    try { localStorage.setItem(SETTINGS_KEY, JSON.stringify({ ...settings })) } catch {}
  }

  let liveGallery = {gid:'', token:'', site:liveSite ?? ''}
  let perPart = 1
  const directories = new Map<number, Promise<void>>()
  function installPages(items: PageInfo[]) {
    for (const item of items) {
      pages.value[item.pageNum - 1] = {...item, thumbSprite: item.thumbSprite ?
        liveUrl('image', { site: liveGallery.site, imageUrl: item.thumbSprite }) : ''}
    }
  }

  async function init(gid: string, token: string, startPage: number) {
    initLoading.value = true
    initError.value = null
    try {
      if (liveSite !== undefined) {
        liveGallery = {gid, token, site:liveSite}
        const data = await liveData('directory', liveGallery)
        liveGallery.site = data.site
        perPart = data.images.length
        total.value = data.total
        galleryTitle.value = data.title
        pages.value = Array.from({length:data.total}, (_, i) => ({
          pageNum:i+1, pageUrl:'', thumbSprite:'', thumbX:0, thumbW:100, thumbH:142
        }))
        installPages(data.images)
        return
      }
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
    const inflight = inflightCache.get(pageNum)
    if (inflight) return inflight

    if (liveSite !== undefined && !pages.value[pageNum - 1]?.pageUrl) {
      const part = Math.floor((pageNum - 1) / perPart)
      if (!directories.has(part)) directories.set(part,
        liveData('directory', {...liveGallery, part:String(part)}).then(data => installPages(data.images))
          .finally(() => directories.delete(part)))
      await directories.get(part)
    }
    const pg = pages.value.find(p => p.pageNum === pageNum)
    if (!pg) throw new Error(`Page ${pageNum} not found`)

    const promise = (async () => {
      if (liveSite !== undefined) return liveImage(pg.pageUrl)
      const res = await fetch(`${API_BASE}/api/image-url?pageUrl=${encodeURIComponent(pg.pageUrl)}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      if (data.error) throw new Error(data.error)
      return { imageUrl: data.imageUrl, nlParam: data.nlParam ?? null } as ImageData
    })()

    inflightCache.set(pageNum, promise)
    promise
      .then(r => { imageCache.set(pageNum, r) })
      .catch(() => {})
      .finally(() => { inflightCache.delete(pageNum) })

    return promise
  }

  async function liveImage(pageUrl: string): Promise<ImageData> {
    const site = liveGallery.site
    const data = await liveData('image-url', {site, pageUrl})
    return { imageUrl: liveUrl('image', {site, imageUrl:data.imageUrl}), nlParam:data.nlParam }
  }

  async function retryImage(pageNum: number, nlParam?: string | null): Promise<ImageData> {
    imageCache.delete(pageNum)
    const pg = pages.value.find(p => p.pageNum === pageNum)
    if (!pg) throw new Error(`Page ${pageNum} not found`)
    let pageUrl = pg.pageUrl
    if (nlParam) {
      // Remove any existing nl= param before appending
      pageUrl = pageUrl.replace(/([?&])nl=[^&]*/g, '$1').replace(/[?&]$/, '')
      pageUrl += (pageUrl.includes('?') ? '&' : '?') + `nl=${encodeURIComponent(nlParam)}`
    }
    if (liveSite !== undefined) {
      if (!pageUrl) return getImageUrl(pageNum)
      const result = await liveImage(pageUrl)
      imageCache.set(pageNum, result)
      return result
    }
    const res = await fetch(`${API_BASE}/api/image-url?pageUrl=${encodeURIComponent(pageUrl)}&refresh=true`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (data.error) throw new Error(data.error)
    const result: ImageData = { imageUrl: data.imageUrl, nlParam: data.nlParam ?? null }
    imageCache.set(pageNum, result)
    return result
  }

  function preload(center: number) {
    const step = settings.readingMode === 'scroll' ? 1 : effectivePagesPerScreen.value
    const targets = new Set<number>()

    for (const off of [1, -1]) {
      const start = center + off * step
      if (start < 1 || start > total.value) continue
      targets.add(start)
      if (step === 2 && start + 1 <= total.value) targets.add(start + 1)
    }

    for (const pageNum of targets) {
      getImageUrl(pageNum).catch(() => {})
    }
  }

  function goTo(pageNum: number) {
    const n = Math.max(1, Math.min(total.value, pageNum))
    currentPage.value = n
    navigation.value = { page: n, sequence: navigation.value.sequence + 1 }
    preload(n)
  }

  function prev() { goTo(currentPage.value - (settings.readingMode === 'scroll' ? 1 : effectivePagesPerScreen.value)) }
  function next() { goTo(currentPage.value + (settings.readingMode === 'scroll' ? 1 : effectivePagesPerScreen.value)) }

  return {
    pages, total, galleryTitle, initLoading, initError,
    currentPage, navigation, settings, effectivePagesPerScreen, windowWidth, windowHeight,
    imageCache, getImageUrl, retryImage,
    updateSetting, init, goTo, prev, next, preload, onResize,
  }
}

export type ReaderState = ReturnType<typeof useReader>
export const READER_KEY: InjectionKey<ReaderState> = Symbol('reader')
