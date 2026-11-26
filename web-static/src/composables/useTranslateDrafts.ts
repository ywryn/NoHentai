const STORAGE_KEY = 'translate-drafts:v1'
const MAX_DRAFTS = 60

export interface TranslateDraftItem {
  _id: number
  text: string
  translation: string
  translationSource?: string
  confidence?: number
  kind?: string
  box?: number[][]
}

interface StoredDraft {
  updatedAt: number
  items: TranslateDraftItem[]
}

function readAll(): Record<string, StoredDraft> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
  } catch {
    return {}
  }
}

function writeAll(store: Record<string, StoredDraft>) {
  const bounded = Object.fromEntries(
    Object.entries(store)
      .filter(([, v]) => v && Array.isArray(v.items) && v.items.length > 0)
      .sort((a, b) => (b[1].updatedAt || 0) - (a[1].updatedAt || 0))
      .slice(0, MAX_DRAFTS)
  )
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(bounded))
  } catch {
    // Ignore quota errors cleanly.
  }
}

function draftKey(gid: string, page: number) {
  return `${gid}:${page}`
}

export function loadPageDraft(gid: string, page: number): TranslateDraftItem[] | null {
  if (!gid || !Number.isFinite(page) || page < 1) return null
  const entry = readAll()[draftKey(gid, page)]
  if (!entry || !Array.isArray(entry.items) || !entry.items.length) return null
  return entry.items
}

export function savePageDraft(gid: string, page: number, items: any[]) {
  if (!gid || !Number.isFinite(page) || page < 1) return
  const store = readAll()
  const key = draftKey(gid, page)
  if (!Array.isArray(items) || !items.length) {
    if (store[key]) {
      delete store[key]
      writeAll(store)
    }
    return
  }
  store[key] = {
    updatedAt: Date.now(),
    items: items.map((item, idx) => ({
      _id: typeof item._id === 'number' ? item._id : idx + 1,
      text: String(item.text || ''),
      translation: String(item.translation || ''),
      ...(item.translationSource ? { translationSource: String(item.translationSource) } : {}),
      ...(typeof item.confidence === 'number' ? { confidence: item.confidence } : {}),
      ...(item.kind ? { kind: String(item.kind) } : {}),
      ...(Array.isArray(item.box) ? { box: item.box } : {}),
    })),
  }
  writeAll(store)
}

export function clearPageDraft(gid: string, page: number) {
  if (!gid || !Number.isFinite(page) || page < 1) return
  const store = readAll()
  const key = draftKey(gid, page)
  if (store[key]) {
    delete store[key]
    writeAll(store)
  }
}
