export const VERTICAL_ASPECT = 1.6

export const POS_COLOR = {
  '名詞':     '#60a5fa',
  '動詞':     '#4ade80',
  '形容詞':   '#fb923c',
  '形容動詞': '#fbbf24',
  '副詞':     '#c084fc',
  '接続詞':   '#f472b6',
  '感動詞':   '#f87171',
  '助詞':     '#22d3ee',
  '助動詞':   '#34d399',
  '連体詞':   '#a3e635',
}

let _kuromojiTokenizer = null
let _kuromojiPromise = null

export function loadKuromoji() {
  if (_kuromojiTokenizer) return Promise.resolve(_kuromojiTokenizer)
  if (_kuromojiPromise) return _kuromojiPromise
  _kuromojiPromise = new Promise((resolve, reject) => {
    const ensureScript = () => new Promise((res, rej) => {
      if (window.kuromoji) { res(); return }
      const s = document.createElement('script')
      s.src = 'https://cdn.jsdelivr.net/npm/kuromoji@0.1.2/build/kuromoji.js'
      s.onload = res
      s.onerror = () => rej(new Error('kuromoji 脚本加载失败'))
      document.head.appendChild(s)
    })
    ensureScript().then(() => {
      window.kuromoji
        .builder({ dicPath: '/kuromoji-dict' })
        .build((err, tokenizer) => {
          if (err) { _kuromojiPromise = null; reject(err); return }
          _kuromojiTokenizer = tokenizer
          resolve(tokenizer)
        })
    }).catch(err => { _kuromojiPromise = null; reject(err) })
  })
  return _kuromojiPromise
}

export function hasKanji(str) {
  return /[一-鿿㐀-䶿]/.test(str)
}

export function toHiragana(katakana) {
  return katakana.replace(/[ァ-ヶ]/g, ch => String.fromCharCode(ch.charCodeAt(0) - 0x60))
}

class Rect {
  constructor(x, y, w, h) {
    this.x0 = x; this.y0 = y; this.x1 = x + w; this.y1 = y + h
    this.w = w; this.h = h
  }
  collision(r) {
    return this.x0 < r.x1 && this.y0 < r.y1 && this.x1 > r.x0 && this.y1 > r.y0
  }
  gapTo(r) {
    const dx = Math.max(0, r.x0 - this.x1, this.x0 - r.x1)
    const dy = Math.max(0, r.y0 - this.y1, this.y0 - r.y1)
    return Math.hypot(dx, dy)
  }
  pad(px) {
    return new Rect(this.x0 - px, this.y0 - px, this.w + px * 2, this.h + px * 2)
  }
}

function bboxToRect(bbox) {
  return new Rect(bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])
}

function findConnected(rect, allRects, used, group, padPx, maxDist) {
  const expanded = rect.pad(padPx)
  for (const [r, idx] of allRects) {
    if (used.has(idx)) continue
    if (expanded.collision(r) || rect.gapTo(r) <= maxDist) {
      group.push(idx)
      used.add(idx)
      findConnected(r, allRects, used, group, padPx, maxDist)
    }
  }
}

function convexHull(pts) {
  if (pts.length < 3) return pts
  const sorted = [...pts].sort((a, b) => a[0] - b[0] || a[1] - b[1])
  const cross = (O, A, B) => (A[0] - O[0]) * (B[1] - O[1]) - (A[1] - O[1]) * (B[0] - O[0])
  const lower = []
  for (const p of sorted) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) lower.pop()
    lower.push(p)
  }
  const upper = []
  for (let i = sorted.length - 1; i >= 0; i--) {
    const p = sorted[i]
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) upper.pop()
    upper.push(p)
  }
  lower.pop(); upper.pop()
  return [...lower, ...upper]
}

function boxOrientation(bbox) {
  const w = Math.max(1, bbox[2] - bbox[0])
  const h = Math.max(1, bbox[3] - bbox[1])
  return h / w > VERTICAL_ASPECT ? 'vertical' : 'horizontal'
}

function median(nums) {
  if (!nums.length) return 0
  const s = [...nums].sort((a, b) => a - b)
  const mid = s.length >> 1
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2
}

export function mergeOcrResults(items, { blockLevel = false, confidenceThreshold = 0.7 } = {}) {
  if (!items.length) return []

  const m = median(items.map(r => Math.min(r.bbox[2] - r.bbox[0], r.bbox[3] - r.bbox[1]))) || 16
  const pad = m * (blockLevel ? 0.6 : 0.4)
  const maxDistance = m * (blockLevel ? 1.0 : 0.6)

  const rects = items.map((r, i) => [bboxToRect(r.bbox), i])
  rects.sort(([a], [b]) => b.w * b.h - a.w * a.h)

  const used = new Set()
  const groups = []
  for (const [rect, idx] of rects) {
    if (used.has(idx)) continue
    const group = [idx]
    used.add(idx)
    findConnected(rect, rects, used, group, pad, maxDistance)
    groups.push(group)
  }

  const merged = []
  for (const group of groups) {
    if (group.length >= 2) {
      const members = group.map(i => items[i])
      const vertical = members.filter(r => boxOrientation(r.bbox) === 'vertical').length * 2 >= members.length
      const sorted = [...members].sort(vertical
        ? (a, b) => (b.bbox[0] + b.bbox[2]) - (a.bbox[0] + a.bbox[2])
        : (a, b) => (a.bbox[1] + a.bbox[3]) - (b.bbox[1] + b.bbox[3]))
      const allX = sorted.flatMap(r => [r.bbox[0], r.bbox[2]])
      const allY = sorted.flatMap(r => [r.bbox[1], r.bbox[3]])
      const allPts = []
      for (const r of sorted) {
        if (r.polygon?.length) allPts.push(...r.polygon)
        else {
          const [x1, y1, x2, y2] = r.bbox
          allPts.push([x1, y1], [x2, y1], [x2, y2], [x1, y2])
        }
      }
      const bbox = [Math.min(...allX), Math.min(...allY), Math.max(...allX), Math.max(...allY)]
      merged.push({
        text: sorted.map(r => r.text).join(''),
        confidence: sorted.reduce((s, r) => s + r.confidence, 0) / sorted.length,
        bbox,
        polygon: convexHull(allPts),
        orientation: vertical ? 'vertical' : 'horizontal',
        is_merged: true,
        original_count: sorted.length,
        original_texts: sorted.map(r => r.text),
        translation: null,
      })
    } else {
      for (const i of group) {
        merged.push({
          ...items[i],
          orientation: boxOrientation(items[i].bbox),
          is_merged: false,
          original_count: 1,
          original_texts: [items[i].text],
          translation: null,
        })
      }
    }
  }

  const avgWidth = merged.reduce((s, r) => s + (r.bbox[2] - r.bbox[0]), 0) / merged.length
  const colThreshold = avgWidth * 1.4
  const sortedByX = [...merged].sort((a, b) => b.bbox[2] - a.bbox[2])
  const columns = []
  let currentCol = []
  for (const r of sortedByX) {
    if (currentCol.length === 0 || currentCol[0].bbox[2] - r.bbox[2] < colThreshold) {
      currentCol.push(r)
    } else {
      columns.push(currentCol)
      currentCol = [r]
    }
  }
  if (currentCol.length) columns.push(currentCol)
  for (const col of columns) col.sort((a, b) => a.bbox[1] - b.bbox[1])

  const CJK_RE = /[぀-鿿가-힯]/
  const NOISE_RE = /^(?:\d+|[a-zA-Z]|[^぀-鿿가-힯a-zA-Z0-9]+)$/
  return columns.flat().filter(r => {
    if (r.confidence < confidenceThreshold) return false
    const t = r.text.trim()
    if (!t) return false
    if (CJK_RE.test(t)) return true
    return !NOISE_RE.test(t)
  })
}

export function fitTextToBox(el, minSize = 1) {
  const box = el.parentElement
  if (!box) return true
  box.offsetHeight
  const s = window.getComputedStyle(box)
  const cw = box.clientWidth  - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight)
  const ch = box.clientHeight - parseFloat(s.paddingTop)  - parseFloat(s.paddingBottom)
  if (cw <= 0 || ch <= 0) return true

  let lo = minSize, hi = 72, best = lo, attempts = 0
  while (lo <= hi && attempts < 20) {
    attempts++
    const mid = Math.floor((lo + hi) / 2)
    el.style.fontSize = mid + 'px'
    el.style.lineHeight = '1.2'
    el.offsetHeight
    if (el.scrollWidth <= cw && el.scrollHeight <= ch) { best = mid; lo = mid + 1 }
    else hi = mid - 1
  }
  el.style.fontSize = best + 'px'
  for (const lh of [1.0, 1.1, 1.2, 1.3, 1.4]) {
    el.style.lineHeight = String(lh)
    el.offsetHeight
    if (el.scrollWidth > cw || el.scrollHeight > ch) {
      el.style.lineHeight = String(Math.max(1.0, lh - 0.1))
      break
    }
  }
  el.offsetHeight
  return best > minSize || (el.scrollWidth <= box.clientWidth && el.scrollHeight <= box.clientHeight)
}
