import * as OpenCC from 'opencc-js'
import { parseQuery, passesQuery, matchGalleryTerm } from './gallerySearch.js'

const traditional = OpenCC.Converter({ from: 'cn', to: 'tw' })
const normalize = value => traditional(String(value ?? '').normalize('NFKC').toLowerCase()).replace(/[\s\p{P}\p{S}]+/gu, '')

// Match the same gallery snapshot used by Home; candidates always require explicit selection.
export function findBookMatches(galleries, query, book = {}, limit = 20) {
  let raw = query.trim()
  if (!raw) return []
  if (raw.toLowerCase() === String(book.ID || '').toLowerCase()) raw = book['日文名'] || book['书名'] || raw
  const urlId = raw.match(/https?:\/\/(?:e-hentai|exhentai)\.org\/g\/(\d+)/i)?.[1]
  const exactId = urlId || raw.match(/^(?:gid:|sid:)?(\d+)$/i)?.[1]
  if (exactId) return galleries.filter(g => String(g.gid) === exactId).map(gallery => ({ gallery, reason: '画廊 ID 精确匹配', score: 100 }))
  const parsed = parseQuery(raw)
  const needle = normalize(raw)
  return galleries.map(gallery => {
    const titles = [normalize(gallery.title), normalize(gallery.title_jpn)]
    const exact = needle.length >= 2 && titles.some(t => t === needle)
    const contains = needle.length >= 2 && titles.some(t => t.includes(needle))
    const search = passesQuery(gallery, parsed, (g, term) => matchGalleryTerm(g, term, traditional))
    if (!exact && !contains && !search) return null
    return { gallery, score: exact ? 90 : contains ? 70 : 50, reason: exact ? '书名精确匹配' : contains ? '书名包含匹配' : '标题 / 上传者 / 标签匹配' }
  }).filter(Boolean).sort((a, b) => b.score - a.score || Number(b.gallery.gid) - Number(a.gallery.gid)).slice(0, limit)
}
