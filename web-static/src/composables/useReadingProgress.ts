import { ref } from 'vue'

const STORAGE_KEY = 'reading-progress:v1'
const MAX_ENTRIES = 200

export interface ReadingProgressEntry {
  page: number
  total: number
  updatedAt: number
}

function readStore(): Record<string, ReadingProgressEntry> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
    return parsed
  } catch {
    return {}
  }
}

function writeStore(store: Record<string, ReadingProgressEntry>) {
  const entries = Object.entries(store)
    .filter(([, v]) => v && typeof v.page === 'number' && v.page >= 1 && typeof v.total === 'number' && v.total >= 1)
    .sort((a, b) => (b[1].updatedAt || 0) - (a[1].updatedAt || 0))
    .slice(0, MAX_ENTRIES)
  const bounded = Object.fromEntries(entries)
  progressMap.value = bounded
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(bounded))
  } catch {
    // Ignore storage quota errors in restricted/private environments.
  }
}

const progressMap = ref<Record<string, ReadingProgressEntry>>(readStore())

export function getReadingProgress(gid: string | number | null | undefined): ReadingProgressEntry | null {
  if (gid === null || gid === undefined || gid === '') return null
  return progressMap.value[String(gid)] ?? null
}

export function saveReadingProgress(gid: string | number | null | undefined, page: number, total: number) {
  if (gid === null || gid === undefined || gid === '') return
  if (!Number.isFinite(page) || !Number.isFinite(total) || page < 1 || total < 1) return
  const clamped = Math.min(Math.floor(page), Math.floor(total))
  const next = {
    ...progressMap.value,
    [String(gid)]: {
      page: clamped,
      total: Math.floor(total),
      updatedAt: Date.now(),
    },
  }
  writeStore(next)
}

export function clearReadingProgress(gid: string | number | null | undefined) {
  if (gid === null || gid === undefined || gid === '') return
  const key = String(gid)
  if (!progressMap.value[key]) return
  const next = { ...progressMap.value }
  delete next[key]
  writeStore(next)
}

export function useReadingProgress() {
  return {
    progressMap,
    getReadingProgress,
    saveReadingProgress,
    clearReadingProgress,
  }
}
