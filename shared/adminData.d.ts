export interface GalleryOverride {
  title?: string
  title_jpn?: string
  tags?: string[]
  category?: string
  uploader?: string
  hidden?: boolean
}
export interface DailyGroup {
  name: string
  filters: string[]
  keyword: string
  categories: number
  minPages: number | null
  maxPages: number | null
  minRating: number | null
  cutoffDays: number
}
export interface TranslateConfig {
  model: string | null
  defaultOcr: 'google' | 'paddle' | 'ocrspace'
  jsonMode: boolean | null
}
export const RESOURCES: Readonly<Record<'printed' | 'overrides' | 'daily' | 'translate', string>>
export const GALLERIES_PATH: string
export const CATEGORIES: string[]
export const OVERRIDE_FIELDS: string[]
export function validateOverrides(value: unknown): Record<string, GalleryOverride>
export function validateDaily(value: unknown): DailyGroup[]
export function validateTranslate(value: unknown): TranslateConfig
export function mergeGalleries<T extends { gid: string | number }>(galleries: T[], overrides: Record<string, GalleryOverride>, options?: { includeHidden?: boolean }): Array<T & GalleryOverride>
export function validateReferences(books: Array<{ ID: string; sid: string }>, galleries: Array<{ gid: string | number }>): Array<{ id: string; sid: string }>
