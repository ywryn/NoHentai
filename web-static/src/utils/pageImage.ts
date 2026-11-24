const base = import.meta.env.VITE_API_BASE ?? ''

type PageImage = { blob: Blob; version: string | null }
type Request = { controller: AbortController; users: number; promise: Promise<PageImage> }

const pending = new Map<string, Request>()

export async function fetchPageImage(pageUrl: string, site: string | undefined, options: {
  refresh?: boolean
  background?: boolean
  signal?: AbortSignal
} = {}): Promise<PageImage> {
  const { refresh, background, signal } = options
  signal?.throwIfAborted()
  const params = new URLSearchParams({ pageUrl })
  if (site !== undefined) params.set('site', site)
  const url = base + '/api/page-image?' + params
  const key = refresh ? url + '&refresh' : url
  let task = pending.get(key)
  if (!task) {
    const controller = new AbortController()
    const init: RequestInit & { priority?: 'low' } = {
      signal: controller.signal,
      cache: refresh ? 'reload' : 'default',
    }
    if (refresh) init.headers = { 'X-Page-Image-Refresh': '1' }
    if (background) init.priority = 'low'
    const promise = fetch(url, init).then(async response => {
      if (site !== undefined && response.status === 401) {
        window.dispatchEvent(new Event('cost-session-expired'))
      }
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data.error || `图片请求失败（HTTP ${response.status}）`)
      }
      return { blob: await response.blob(), version: response.headers.get('ETag') }
    }).finally(() => {
      if (pending.get(key)?.controller === controller) pending.delete(key)
    })
    task = { controller, users: 0, promise }
    pending.set(key, task)
  }

  const request = task
  request.users++
  let cancel: (() => void) | undefined
  try {
    return await new Promise<PageImage>((resolve, reject) => {
      cancel = () => reject(signal?.reason)
      signal?.addEventListener('abort', cancel, { once: true })
      request.promise.then(resolve, reject)
    })
  } finally {
    if (cancel) signal?.removeEventListener('abort', cancel)
    if (--request.users === 0 && pending.get(key) === request) {
      pending.delete(key)
      request.controller.abort()
    }
  }
}
