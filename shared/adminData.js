export const RESOURCES = Object.freeze({
  printed: 'web-static/public/data/future_digi.csv',
  overrides: 'web-static/public/data/gallery-overrides.json',
  daily: 'config/daily.json',
  translate: 'config/translate.json',
})
export const GALLERIES_PATH = 'web-static/public/data/galleries.json'
export const CATEGORIES = ['Doujinshi', 'Manga', 'Artist CG', 'Game CG', 'Western', 'Non-H', 'Image Set', 'Cosplay', 'Asian Porn', 'Misc']
export const OVERRIDE_FIELDS = ['title', 'title_jpn', 'tags', 'category', 'uploader', 'hidden']

function check(condition, message) { if (!condition) throw new Error(message) }
function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value) }
function text(value, max) { return typeof value === 'string' && value.length <= max && !value.includes('\0') }
function strings(value, maxCount, maxLength) {
  return Array.isArray(value) && value.length <= maxCount && value.every(v => text(v, maxLength))
}

export function validateOverrides(value) {
  check(object(value) && Object.keys(value).length <= 20000, '画廊覆盖数据格式不正确')
  for (const [gid, patch] of Object.entries(value)) {
    check(/^[1-9]\d{0,14}$/.test(gid) && object(patch), '画廊 ID 或覆盖数据不正确')
    for (const [key, v] of Object.entries(patch)) {
      check(OVERRIDE_FIELDS.includes(key), `不允许覆盖字段：${key}`)
      if (key === 'hidden') check(typeof v === 'boolean', '隐藏状态必须是布尔值')
      else if (key === 'tags') check(strings(v, 500, 200), '标签必须是字符串数组')
      else if (key === 'category') check(CATEGORIES.includes(v), '画廊分类不正确')
      else check(text(v, 5000), `字段 ${key} 不正确`)
    }
  }
  return value
}

export function mergeGalleries(galleries, overrides, { includeHidden = false } = {}) {
  validateOverrides(overrides)
  const seen = new Set()
  return galleries.map(g => {
    const id = String(g.gid)
    check(/^[1-9]\d*$/.test(id) && !seen.has(id), `画廊 ID 缺失或重复：${id}`)
    seen.add(id)
    return { ...g, ...(overrides[id] || {}) }
  }).filter(g => includeHidden || !g.hidden)
}

export function validateDaily(value) {
  check(Array.isArray(value) && value.length > 0 && value.length <= 20, '每日筛选需要 1–20 个分组')
  const keys = ['name', 'filters', 'keyword', 'categories', 'minPages', 'maxPages', 'minRating', 'cutoffDays']
  const names = new Set()
  for (const g of value) {
    check(object(g) && Object.keys(g).every(k => keys.includes(k)) && keys.every(k => Object.hasOwn(g, k)), '每日筛选字段不完整或包含未知字段')
    check(text(g.name, 120) && g.name.trim() && !names.has(g.name), '分组名称为空或重复')
    names.add(g.name)
    check(strings(g.filters, 30, 120) && text(g.keyword, 2000), '筛选标签或搜索关键词不正确')
    check(Number.isInteger(g.categories) && g.categories >= 1 && g.categories <= 1023, '分类掩码应为 1–1023')
    for (const k of ['minPages', 'maxPages']) check(g[k] === null || (Number.isInteger(g[k]) && g[k] >= 1 && g[k] <= 100000), '页数应为正整数或 null')
    check(g.minPages === null || g.maxPages === null || g.minPages <= g.maxPages, '最小页数不能大于最大页数')
    check(g.minRating === null || (Number.isInteger(g.minRating) && g.minRating >= 2 && g.minRating <= 5), '评分应为 2–5 或 null')
    check(Number.isInteger(g.cutoffDays) && g.cutoffDays >= 1 && g.cutoffDays <= 365, '回溯天数应为 1–365')
  }
  return value
}

export function validateTranslate(value) {
  check(object(value) && Object.keys(value).length === 3 && ['model', 'defaultOcr', 'jsonMode'].every(k => Object.hasOwn(value, k)), '翻译配置字段不正确；密钥请通过凭证管理修改')
  check(value.model === null || (text(value.model, 150) && value.model.trim()), '模型名不正确')
  check(['google', 'paddle', 'ocrspace'].includes(value.defaultOcr), 'OCR 来源不正确')
  check(value.jsonMode === null || typeof value.jsonMode === 'boolean', 'JSON 模式应为布尔值或 null')
  return value
}

export function validateReferences(books, galleries) {
  const ids = new Set(galleries.map(g => String(g.gid)))
  return books.filter(b => b.sid && !ids.has(b.sid)).map(b => ({ id: b.ID, sid: b.sid }))
}
