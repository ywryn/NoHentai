// web-static/src/composables/useReader.ts
import { ref, reactive, computed, nextTick, watch } from 'vue'
import { liveData, liveUrl } from '@/utils/live'
import { fetchPageImage, PageImageRequestError } from '@/utils/pageImage'
import type { InjectionKey } from 'vue'

const API_BASE = (import.meta as any).env?.VITE_API_BASE ?? ''
const SETTINGS_KEY = 'reader-settings'
type PageImageOptions = NonNullable<Parameters<typeof fetchPageImage>[2]> & {
  refreshDirectory?: boolean
  manualRetry?: boolean
}

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
  pageTurnAnimation: 'slide' | 'flip' | 'fade' | 'none'
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
  const directories = new Map<number, { refresh: boolean; task: Promise<PageInfo[]> }>()
  const loadedParts = new Set<number>()
  const prefetch = new Map<number, AbortController>()
  let upcoming: number[] = []
  let foregroundInFlight = 0
  let preloadEnabled = false
  let quotaSuspended = false
  let rateLimitedUntil = 0

  async function fetchDirectory(part: number, background = false, refresh = false) {
    if (site !== undefined) return liveData('directory', { ...gallery, site, part: String(part) })
    const params = new URLSearchParams({ ...gallery, part: String(part) })
    if (source) params.set('source', source)
    if (refresh) params.set('refresh', 'true')
    const init: RequestInit & { priority?: 'low' } = background ? { priority: 'low' } : {}
    const res = await fetch(`${API_BASE}/api/gallery-images/part?${params}`, init)
    const data = await res.json().catch(() => null)
    if (!res.ok) {
      const message = data?.error === 'exhentai_blocked' ? '画廊不可访问，请检查站点权限' : data?.error || '获取页面列表失败'
      throw new PageImageRequestError(message, 'directory_error', res.status)
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
    preloadEnabled = preloadNeighbors
    stopPreload()
    quotaSuspended = false
    rateLimitedUntil = 0
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

  function loadPart(part: number, background = false, refresh = false): Promise<PageInfo[]> {
    const pending = directories.get(part)
    if (pending) {
      if (!refresh || pending.refresh) return pending.task
      return pending.task.catch(() => {}).then(() => loadPart(part, background, true))
    }
    const task = fetchDirectory(part, background, refresh).then(data => {
      if (data.total !== total.value) throw new Error('画廊页数已变化，请重新打开')
      if (part === 0) {
        perPart = data.images.length
        partCount = data.partCount ?? 1
      }
      installPages(data.images)
      loadedParts.add(part)
      return data.images as PageInfo[]
    }).finally(() => {
      if (directories.get(part)?.task === task) directories.delete(part)
    })
    directories.set(part, { refresh, task })
    return task
  }

  async function loadThumbnails(first: number, last: number) {
    if (!total.value) return
    for (let part = partFor(first); part <= partFor(last); part++) {
      if (!loadedParts.has(part)) await loadPart(part, true).catch(() => {})
    }
  }

  async function requestPageImage(pageNum: number, options: PageImageOptions) {
    options.signal?.throwIfAborted()
    try {
      if (options.refreshDirectory || !pages.value[pageNum - 1]?.pageUrl) {
        const part = partFor(pageNum)
        let entries = await loadPart(part, options.background, options.refreshDirectory || options.refresh)
        if (!entries.some(entry => entry.pageNum === pageNum)) {
          options.signal?.throwIfAborted()
          entries = await loadPart(0, options.background, true)
          const refreshedPart = partFor(pageNum)
          if (refreshedPart > 0) entries = await loadPart(refreshedPart, options.background, true)
          if (!entries.some(entry => entry.pageNum === pageNum)) {
            throw new Error(`无法定位第 ${pageNum} 页，请重试`)
          }
        }
      }
    } catch (error) {
      if (options.signal?.aborted || error instanceof PageImageRequestError) throw error
      throw new PageImageRequestError(error instanceof Error ? error.message : '获取页面列表失败', 'directory_error')
    }
    const pageUrl = pages.value[pageNum - 1]?.pageUrl
    if (!pageUrl) throw new PageImageRequestError(`无法定位第 ${pageNum} 页，请重试`, 'directory_error')
    return fetchPageImage(pageUrl, site, options)
  }

  async function loadPageImage(pageNum: number, options: PageImageOptions = {}) {
    if (options.background) return requestPageImage(pageNum, options)
    foregroundInFlight++
    try {
      const image = await requestPageImage(pageNum, options)
      if (quotaSuspended && options.manualRetry && !options.signal?.aborted) {
        quotaSuspended = false
        if (preloadEnabled) preload(currentPage.value)
      }
      return image
    } catch (error) {
      if (!options.signal?.aborted) pausePreloadFor(error)
      throw error
    } finally {
      foregroundInFlight--
      void nextTick(startPreload)
    }
  }

  function pausePreloadFor(error: unknown) {
    if (!(error instanceof PageImageRequestError)) return
    if (error.status === 509) quotaSuspended = true
    else if (error.status === 429) rateLimitedUntil = Date.now() + 60_000
    else return
    stopPreload()
  }

  function isPreloadPaused() {
    return quotaSuspended || Date.now() < rateLimitedUntil
  }

  function startPreload() {
    if (foregroundInFlight || prefetch.size || isPreloadPaused()) return
    const pageNum = upcoming.shift()
    if (pageNum === undefined) return
    const controller = new AbortController()
    prefetch.set(pageNum, controller)
    void requestPageImage(pageNum, { signal: controller.signal, background: true })
      .catch(error => { if (!controller.signal.aborted) pausePreloadFor(error) })
      .finally(() => {
        if (prefetch.get(pageNum) === controller) prefetch.delete(pageNum)
        void nextTick(startPreload)
      })
  }

  function preload(center: number) {
    // ScrollView already loads images near the viewport. Live responses use no-store.
    if (site !== undefined || settings.readingMode === 'scroll' || isPreloadPaused()) {
      stopPreload()
      return
    }
    const first = center + effectivePagesPerScreen.value
    const last = Math.min(first + 1, total.value)
    upcoming = []
    for (let pageNum = first; pageNum <= last; pageNum++) {
      if (!prefetch.has(pageNum) || prefetch.get(pageNum)?.signal.aborted) upcoming.push(pageNum)
    }
    // Keep any task the new spread can use until it settles, even if the
    // visible PageImage has to wait for a directory segment before subscribing.
    for (const [pageNum, controller] of prefetch) {
      if (pageNum < center || pageNum > last) controller.abort()
    }
    void nextTick(startPreload)
  }

  function stopPreload() {
    upcoming = []
    for (const controller of prefetch.values()) controller.abort()
  }

  watch([() => settings.readingMode, effectivePagesPerScreen], () => {
    if (preloadEnabled && !initLoading.value) preload(currentPage.value)
  })

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
