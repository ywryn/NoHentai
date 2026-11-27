// All coordinates in this module are original-image pixels.
export const schemes = [
  { id: 'original', label: '现有排版' },
  { id: 'spacing', label: '几何避让' },
  { id: 'balloon', label: '气泡轮廓' },
]
const union = (a, b) => [
  Math.min(a[0], b[0]),
  Math.min(a[1], b[1]),
  Math.max(a[2], b[2]),
  Math.max(a[3], b[3]),
]
const overlaps = (a, b) => a[0] < b[2] && b[0] < a[2] && a[1] > b[0] && b[1] > a[1]
const vertical = (b) => b[3] - b[1] > 1.6 * (b[2] - b[0])

// Label connected light paper. Reject components open to the page edge.
// Sampling around the text avoids using the ink at the center as a seed.
export function paperRegions(image) {
  const scale = Math.min(1, 720 / Math.max(image.naturalWidth, image.naturalHeight))
  const canvas = document.createElement('canvas')
  const w = (canvas.width = Math.max(1, Math.round(image.naturalWidth * scale)))
  const h = (canvas.height = Math.max(1, Math.round(image.naturalHeight * scale)))
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  ctx.drawImage(image, 0, 0, w, h)
  const { data } = ctx.getImageData(0, 0, w, h)
  const labels = new Int32Array(w * h)
  for (let i = 0; i < labels.length; i++) {
    if (Math.min(data[i * 4], data[i * 4 + 1], data[i * 4 + 2]) < 210) labels[i] = -1
  }
  const queue = new Int32Array(labels.length)
  const valid = new Set()
  let id = 0
  for (let i = 0; i < labels.length; i++) {
    if (labels[i]) continue
    let head = 0,
      tail = 1,
      edge = false
    queue[0] = i
    labels[i] = ++id
    while (head < tail) {
      const p = queue[head++],
        x = p % w
      if (!x || x === w - 1 || p < w || p >= w * (h - 1)) edge = true
      for (const adjacent of [x ? p - 1 : -1, x < w - 1 ? p + 1 : -1, p - w, p + w]) {
        if (labels[adjacent] === 0) {
          labels[adjacent] = id
          queue[tail++] = adjacent
        }
      }
    }
    if (!edge && tail >= 20 && tail < labels.length * 0.25) valid.add(id)
  }
  const at = (x, y) => {
    const col = Math.floor(x * scale),
      row = Math.floor(y * scale)
    return col >= 0 && col < w && row >= 0 && row < h ? labels[row * w + col] : -1
  }
  function owner(box) {
    const counts = new Map()
    for (let i = 0; i < 7; i++)
      for (let j = 0; j < 7; j++) {
        const key = at(
          box[0] + ((i + 0.5) * (box[2] - box[0])) / 7,
          box[1] + ((j + 0.5) * (box[3] - box[1])) / 7,
        )
        if (valid.has(key)) counts.set(key, (counts.get(key) || 0) + 1)
      }
    const best = [...counts].sort((a, b) => b[1] - a[1])[0]
    return best && best[1] >= 20 ? best[0] : null
  }
  return { at, owner, scale }
}

export function candidateGroups(results, mode, paper) {
  if (mode === 'original') return results.map((r) => r.bbox)
  const groups = []
  for (const box of results.flatMap((r) => r.memberBoxes || [r.bbox])) {
    const v = vertical(box)
    const short = Math.min(box[2] - box[0], box[3] - box[1])
    const owner = mode === 'balloon' && paper?.owner(box)
    let best,
      nearest = Infinity
    for (const g of groups) {
      if (g.vertical !== v || (g.owner && owner && owner !== g.owner)) continue
      const [a, b, c, d] = g.box
      const aligned = v
        ? Math.min(d, box[3]) - Math.max(b, box[1])
        : Math.min(c, box[2]) - Math.max(a, box[0])
      const gap = v ? Math.max(0, a - box[2], box[0] - c) : Math.max(0, b - box[3], box[1] - d)
      const length = v ? box[3] - box[1] : box[2] - box[0]
      if (
        aligned >= length * 0.65 &&
        gap < nearest &&
        gap <= short * (owner && owner === g.owner ? 1.6 : 0.65)
      ) {
        best = g
        nearest = gap
      }
    }
    if (best) {
      best.box = union(best.box, box)
      best.owner ||= owner
    } else groups.push({ box, vertical: v, owner })
  }
  return groups.map((g) => g.box)
}

export function expandBox(box, side, step, width, height) {
  const next = [...box]
  next[side] += side < 2 ? -step : step
  next[side] = Math.max(0, Math.min(side % 2 ? height : width, next[side]))
  return next
}

// Only inspect the newly added strip. Ink inside the original OCR box is expected.
export function safeExpansion(box, side, step, bounds, obstacles, paper, owner) {
  const next = expandBox(box, side, step, ...bounds)
  if (next[side] === box[side] || obstacles.some((other) => overlaps(next, other))) return null
  if (owner) {
    const strip = [...next]
    strip[(side + 2) % 4] = box[side]
    const stride = 1 / paper.scale
    for (let y = strip[1]; y <= strip[3]; y += stride)
      for (let x = strip[0]; x <= strip[2]; x += stride) if (paper.at(x, y) !== owner) return null
  }
  return next
}
