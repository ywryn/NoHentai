// web-static/src/composables/useReader.ts
import { ref, reactive, computed } from 'vue'
import { liveData, liveUrl } from '@/utils/live'
import { fetchPageImage } from '@/utils/pageImage'
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

  let gallery = { gid: '', token: '' }
  let source: string | undefined
  let site = liveSite
  let perPart = 1
  let partCount = 1
  const directories = new Map<number, Promise<void>>()
  const loadedParts = new Set<number>()
  let prefetch: AbortController | undefined

  async function fetchDirectory(part: number, background = false, refresh = false) {
    if (site !== undefined) return liveData('directory', { ...gallery, site, part: String(part) })
    const params = new URLSearchParams({ ...gallery, part: String(part) })
    if (source) params.set('source', source)
    if (refresh) params.set('refresh', 'true')
    const init: RequestInit & { priority?: 'low' } = background ? { priority: 'low' } : {}
    const res = await fetch(`${API_BASE}/api/gallery-images/part?${params}`, init)
    const data = await res.json()
    if (!res.ok) {
      throw new Error(data.error === 'exhentai_blocked' ? '画廊不可访问，请检查站点权限' : data.error || '获取页面列表失败')
    }
    return data
  }

  function installPages(items: PageInfo[]) {
    for (const item of items) {
      pages.value[item.pageNum - 1] = {
        ...item,
        thumbSprite: item.thumbSprite && site !== undefined
          ? liveUrl('image', { site, imageUrl: item.thumbSprite })
          : item.thumbSprite,
      }
    }
  }

  async function init(gid: string, token: string, startPage: number, preloadNeighbors = true) {
    initLoading.value = true
    initError.value = null
    try {
      gallery = { gid, token }
      source = undefined
      directories.clear()
      loadedParts.clear()
      const data = await fetchDirectory(0)
      if (!data.images?.length) throw new Error('未获取到页面列表，请重试')
      source = data.source
      site = data.site ?? liveSite
      perPart = data.images.length
      partCount = data.partCount ?? 1
      total.value = data.total
      galleryTitle.value = data.title ?? `Gallery #${gid}`
      pages.value = Array.from({ length: data.total }, (_, i) => ({
        pageNum: i + 1, pageUrl: '', thumbSprite: '', thumbX: 0, thumbW: 100, thumbH: 142,
      }))
      installPages(data.images)
      loadedParts.add(0)
    } catch (e) {
      initError.value = e instanceof Error ? e.message : '获取页面列表失败'
    } finally {
      initLoading.value = false
      if (!initError.value && preloadNeighbors) goTo(startPage)
    }
  }

  function partFor(pageNum: number) {
    return Math.min(partCount - 1, Math.floor((pageNum - 1) / perPart))
  }

  function loadPart(part: number, background = false, refresh = false) {
    const pending = directories.get(part)
    if (pending) return pending
    const task = fetchDirectory(part, background, refresh).then(data => {
      if (data.total !== total.value) throw new Error('画廊页数已变化，请重新打开')
      if (part === 0) {
        perPart = data.images.length
        partCount = data.partCount ?? 1
      }
      installPages(data.images)
      loadedParts.add(part)
    }).finally(() => directories.delete(part))
    directories.set(part, task)
    return task
  }

  async function loadThumbnails(first: number, last: number) {
    if (!total.value) return
    for (let part = partFor(first); part <= partFor(last); part++) {
      if (!loadedParts.has(part)) await loadPart(part, true).catch(() => {})
    }
  }

  async function loadPageImage(pageNum: number, options: Parameters<typeof fetchPageImage>[2] = {}) {
    const part = partFor(pageNum)
    if (!pages.value[pageNum - 1]?.pageUrl) {
      await loadPart(part, options.background)
      if (!pages.value[pageNum - 1]?.pageUrl) {
        await loadPart(0, options.background, true)
        const refreshedPart = partFor(pageNum)
        if (refreshedPart > 0) await loadPart(refreshedPart, options.background, true)
      }
    }
    const pageUrl = pages.value[pageNum - 1]?.pageUrl
    if (!pageUrl) throw new Error(`无法定位第 ${pageNum} 页，请重新打开画廊`)
    return fetchPageImage(pageUrl, site, options)
  }

  function preload(center: number) {
    prefetch?.abort()
    // Live images are intentionally not retained by the browser HTTP cache.
    if (site !== undefined) return
    const step = settings.readingMode === 'scroll' ? 1 : effectivePagesPerScreen.value
    // Start after the visible spread and warm the next two consecutive images.
    const first = center + step
    const last = Math.min(first + 1, total.value)
    if (first > last) return
    const controller = new AbortController()
    prefetch = controller
    void (async () => {
      for (let pageNum = first; pageNum <= last; pageNum++) {
        if (controller.signal.aborted) break
        await loadPageImage(pageNum, { signal: controller.signal, background: true }).catch(() => {})
      }
    })()
  }

  function stopPreload() { prefetch?.abort() }

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
    loadPageImage, loadThumbnails, stopPreload,
    updateSetting, init, goTo, prev, next, preload, onResize,
  }
}

export type ReaderState = ReturnType<typeof useReader>
export const READER_KEY: InjectionKey<ReaderState> = Symbol('reader')
