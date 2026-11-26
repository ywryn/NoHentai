const STORAGE_KEY = 'translate-drafts:v2'
const MAX_DRAFTS = 60

interface TranslateDraftItem {
  _id: string | number
  text: string
  bbox: [number, number, number, number]
}

interface StoredDraft {
  ts: number
  version: string
  ocrResults: TranslateDraftItem[]
  lastOcrSource: string | null
}

function readAll(): Record<string, StoredDraft> {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
  } catch {
    return {}
  }
}

function writeAll(store: Record<string, StoredDraft>) {
  const bounded = Object.fromEntries(
    Object.entries(store)
      .sort((a, b) => (b[1]?.ts || 0) - (a[1]?.ts || 0))
      .slice(0, MAX_DRAFTS)
  )
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(bounded))
    return true
  } catch {
    // Storage may be disabled or full.
    return false
  }
}

export function validOcrResults(items: unknown): items is TranslateDraftItem[] {
  return Array.isArray(items) && items.length > 0 && items.every(item =>
    item && (typeof item._id === 'number' || typeof item._id === 'string') &&
    typeof item.text === 'string' && Array.isArray(item.bbox) &&
    item.bbox.length === 4 && item.bbox.every(Number.isFinite)
  )
}

export function loadPageDraft(key: string, version: string): StoredDraft | null {
  const entry = readAll()[key]
  return entry?.version === version && validOcrResults(entry.ocrResults) ? entry : null
}

export function savePageDraft(key: string, version: string, ocrResults: TranslateDraftItem[], lastOcrSource: string | null) {
  if (!validOcrResults(ocrResults)) return false
  const store = readAll()
  store[key] = { ts: Date.now(), version, ocrResults, lastOcrSource }
  return writeAll(store)
}

export function clearPageDraft(key: string) {
  const store = readAll()
  if (store[key]) {
    delete store[key]
    writeAll(store)
  }
}
