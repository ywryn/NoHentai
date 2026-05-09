<template>
  <!-- Password Dialog -->
  <div v-if="!passwordVerified" class="gt-overlay">
    <div class="gt-pwd-dialog">
      <div class="gt-pwd-eyebrow">Translation Workbench</div>
      <h2 class="gt-pwd-title">访问验证</h2>
      <p class="gt-pwd-desc">此功能需要密码才能使用 OCR 和翻译服务</p>
      <div class="gt-pwd-form">
        <input
          ref="pwdInputRef"
          v-model="passwordInput"
          type="password"
          placeholder="输入密码"
          class="gt-pwd-input"
          :disabled="passwordLoading"
          autofocus
          @keydown.enter="verifyPassword"
        />
        <button
          class="gt-btn gt-btn-primary"
          :disabled="passwordLoading || !passwordInput"
          @click="verifyPassword"
        >
          {{ passwordLoading ? '验证中...' : '进入' }}
        </button>
      </div>
      <p v-if="passwordError" class="gt-pwd-error">{{ passwordError }}</p>
      <button class="gt-pwd-back" @click="$router.back()">← 返回</button>
    </div>
  </div>

  <!-- Main Workbench -->
  <div v-else class="gt-workbench">
    <!-- Header -->
    <header class="gt-header">
      <button class="gt-back-btn" @click="$router.back()">←</button>

      <div class="gt-header-info">
        <span v-if="totalPages" class="gt-header-pages">{{ currentPage }} / {{ totalPages }}p</span>
      </div>

      <div class="gt-header-actions">
        <button
          class="gt-btn"
          :disabled="!imageUrl || ocrProcessing || translating || imagesLoading"
          @click="performOcr"
        >
          {{ ocrProcessing ? '识别中...' : 'OCR' }}
        </button>
        <button
          class="gt-btn gt-btn-primary"
          :disabled="!ocrResults.length || translating || ocrProcessing"
          @click="performTranslate"
        >
          {{ translating ? '翻译中...' : '翻译' }}
        </button>
      </div>
    </header>

    <!-- Main body -->
    <div class="gt-body">
      <!-- Image panel -->
      <div class="gt-image-panel" ref="containerRef">
        <div v-if="imageLoading" class="gt-image-placeholder">
          <div class="gt-spinner"></div>
          <span>加载图片...</span>
        </div>
        <div v-else-if="imageError" class="gt-image-placeholder gt-image-error">{{ imageError }}</div>
        <template v-else-if="imageUrl">
          <img
            ref="imgRef"
            :src="imageUrl"
            class="gt-page-img"
            alt="manga page"
            @load="onImageLoad"
          />
          <!-- OCR boxes overlay -->
          <div v-if="ocrResults.length && renderTick >= 0" class="gt-boxes-layer">
            <div
              v-for="(result, i) in ocrResults"
              :key="i"
              class="gt-ocr-box"
              :class="{
                'gt-box-selected': selectedBoxIdx === i,
                'gt-box-translated': !!result.translation,
                'gt-box-hidden': !showBoxes,
              }"
              :style="getBoxStyle(result.bbox)"
              :title="result.translation || result.text"
              @click="selectedBoxIdx = selectedBoxIdx === i ? null : i"
            >
              <span
                v-if="showTranslation && result.translation"
                class="gt-box-trans-text"
                :ref="el => setTransTextRef(el, i)"
              >{{ result.translation }}</span>
            </div>
          </div>
        </template>
        <div v-else class="gt-image-placeholder gt-image-empty">
          <div class="gt-empty-icon">📖</div>
          <p>从右侧选择页面</p>
        </div>

      </div>

      <!-- Sidebar -->
      <div class="gt-sidebar">
        <!-- Thumbnail strip inside sidebar -->
        <div class="gt-strip" v-if="galleryImages.length">
          <button class="gt-strip-nav" :disabled="currentPage <= 1" @click="prevPage">‹</button>
          <div class="gt-strip-scroll" ref="stripRef">
            <div
              v-for="img in galleryImages"
              :key="img.pageNum"
              class="gt-thumb"
              :class="{ 'gt-thumb-active': img.pageNum === currentPage }"
              :style="thumbCellStyle(img)"
              :title="`Page ${img.pageNum}`"
              @click="goToPage(img.pageNum)"
            >
              <div class="gt-thumb-inner" :style="thumbInnerStyle(img)"></div>
              <span class="gt-thumb-num">{{ img.pageNum }}</span>
            </div>
          </div>
          <button class="gt-strip-nav" :disabled="currentPage >= totalPages" @click="nextPage">›</button>
        </div>
        <div v-else-if="imagesLoading" class="gt-strip gt-strip-loading">
          <div class="gt-spinner-sm"></div>
          <span>加载缩略图...</span>
        </div>
        <div v-else-if="imagesError" class="gt-strip gt-strip-error">{{ imagesError }}</div>

        <div class="gt-sidebar-hdr">
          <span class="gt-sidebar-title">识别结果</span>
          <span v-if="ocrResults.length" class="gt-count-badge">{{ ocrResults.length }}</span>
          <span v-if="ocrResults.some(r => r.translation)" class="gt-translated-badge">已翻译</span>
          <div v-if="ocrResults.length" class="gt-sidebar-controls">
            <label class="gt-toggle-label">
              <input v-model="showBoxes" type="checkbox" class="gt-toggle-cb" />
              <span>框</span>
            </label>
            <label class="gt-toggle-label">
              <input v-model="showTranslation" type="checkbox" class="gt-toggle-cb" />
              <span>译文</span>
            </label>
            <button class="gt-btn gt-btn-sm gt-btn-danger" @click="clearResults">清空</button>
          </div>
        </div>

        <div v-if="!ocrResults.length" class="gt-sidebar-empty">
          <div class="gt-sidebar-empty-icon">🔍</div>
          <p>{{ imageUrl ? '点击 OCR 开始识别' : '请先选择页面' }}</p>
        </div>

        <div v-else class="gt-results-list">
          <div
            v-for="(result, i) in ocrResults"
            :key="i"
            class="gt-result-item"
            :class="{ 'gt-result-selected': selectedBoxIdx === i }"
            @click="selectedBoxIdx = selectedBoxIdx === i ? null : i"
          >
            <div class="gt-result-meta">
              <span class="gt-result-idx">{{ i + 1 }}</span>
              <span class="gt-result-conf">{{ (result.confidence * 100).toFixed(0) }}%</span>
              <span v-if="result.is_merged" class="gt-merged-badge">合并×{{ result.original_count }}</span>
              <span v-if="result.translation" class="gt-done-mark">✓</span>
            </div>
            <p class="gt-result-orig">{{ result.text }}</p>
            <p v-if="result.translation" class="gt-result-trans">{{ result.translation }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Toast notifications -->
    <div class="gt-toasts">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="gt-toast"
        :class="'gt-toast-' + toast.type"
      >
        <span>{{ toast.msg }}</span>
        <button class="gt-toast-close" @click="removeToast(toast.id)">×</button>
      </div>
    </div>
  </div>
</template>

<script>
const API_BASE = import.meta.env.VITE_API_BASE || 'https://no-hentai.vercel.app'
const SESSION_KEY = 'trans_password'

// ── OCR merge algorithm (ported from manga-trans ocrService.ts) ───────────────

class Rect {
  constructor(x, y, w, h) {
    this.x0 = x; this.y0 = y; this.x1 = x + w; this.y1 = y + h
    this.w = w; this.h = h
  }
  collision(r) {
    return this.x0 < r.x1 && this.y0 < r.y1 && this.x1 > r.x0 && this.y1 > r.y0
  }
  distanceTo(r) {
    const cx1 = (this.x0 + this.x1) / 2, cy1 = (this.y0 + this.y1) / 2
    const cx2 = (r.x0 + r.x1) / 2,       cy2 = (r.y0 + r.y1) / 2
    return Math.hypot(cx1 - cx2, cy1 - cy2)
  }
  expand(ratio) {
    const ew = this.w * ratio - this.w, eh = this.h * ratio - this.h
    return new Rect(this.x0 - ew / 2, this.y0 - eh / 2, this.w + ew, this.h + eh)
  }
}

function bboxToRect(bbox) {
  return new Rect(bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])
}

function findConnected(rect, allRects, used, group, expandRatio, maxDist) {
  const expanded = rect.expand(expandRatio)
  for (const [r, idx] of allRects) {
    if (used.has(idx)) continue
    if (expanded.collision(r) || rect.distanceTo(r) <= maxDist) {
      group.push(idx)
      used.add(idx)
      findConnected(r, allRects, used, group, expandRatio, maxDist)
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

function mergeOcrResults(items, expandRatio = 1.05, maxDistance = 10, minGroupSize = 2, confidenceThreshold = 0.7) {
  if (!items.length) return []

  const rects = items.map((r, i) => [bboxToRect(r.bbox), i])
  rects.sort(([a], [b]) => b.w * b.h - a.w * a.h)

  const used = new Set()
  const groups = []
  for (const [rect, idx] of rects) {
    if (used.has(idx)) continue
    const group = [idx]
    used.add(idx)
    findConnected(rect, rects, used, group, expandRatio, maxDistance)
    groups.push(group)
  }

  const merged = []
  for (const group of groups) {
    if (group.length >= minGroupSize) {
      const sorted = group
        .map(i => ({ i, r: items[i], cx: (items[i].bbox[0] + items[i].bbox[2]) / 2 }))
        .sort((a, b) => b.cx - a.cx)
      const allX = sorted.flatMap(({ r }) => [r.bbox[0], r.bbox[2]])
      const allY = sorted.flatMap(({ r }) => [r.bbox[1], r.bbox[3]])
      const allPts = []
      for (const { r } of sorted) {
        if (r.polygon?.length) allPts.push(...r.polygon)
        else {
          const [x1, y1, x2, y2] = r.bbox
          allPts.push([x1, y1], [x2, y1], [x2, y2], [x1, y2])
        }
      }
      merged.push({
        text: sorted.map(({ r }) => r.text).join(' '),
        confidence: sorted.reduce((s, { r }) => s + r.confidence, 0) / sorted.length,
        bbox: [Math.min(...allX), Math.min(...allY), Math.max(...allX), Math.max(...allY)],
        polygon: convexHull(allPts),
        is_merged: true,
        original_count: sorted.length,
        original_texts: sorted.map(({ r }) => r.text),
        translation: null,
      })
    } else {
      for (const i of group) merged.push({ ...items[i], is_merged: false, original_count: 1, original_texts: [items[i].text], translation: null })
    }
  }

  // Sort manga reading order: right-to-left columns, top-to-bottom within column
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

// ── Text fit (ported from manga-trans Workbench.tsx) ─────────────────────────

function fitTextToBox(el) {
  const box = el.parentElement
  if (!box) return
  box.offsetHeight // force reflow
  const s = window.getComputedStyle(box)
  const cw = box.clientWidth  - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight)
  const ch = box.clientHeight - parseFloat(s.paddingTop)  - parseFloat(s.paddingBottom)
  if (cw <= 0 || ch <= 0) return

  let lo = 6, hi = 72, best = lo, attempts = 0
  while (lo <= hi && attempts < 20) {
    attempts++
    const mid = Math.floor((lo + hi) / 2)
    el.style.fontSize = mid + 'px'
    el.style.lineHeight = '1.2'
    el.offsetHeight // force reflow
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
}

// ── Component ─────────────────────────────────────────────────────────────────

export default {
  name: 'GalleryTranslate',

  data() {
    return {
      // Auth
      passwordInput: '',
      passwordVerified: false,
      passwordLoading: false,
      passwordError: '',

      // Gallery meta
      gid: null,
      token: null,

      // Gallery images (thumbnails)
      galleryImages: [],
      imagesLoading: false,
      imagesError: null,
      thumbSource: null,

      // Current page
      currentPage: 1,
      imageUrl: null,
      imageUrlRaw: null,
      imageLoading: false,
      imageError: null,
      nlParam: null,

      // OCR / translate state
      ocrResults: [],
      ocrProcessing: false,
      translating: false,

      // UI state
      showBoxes: true,
      showTranslation: true,
      selectedBoxIdx: null,
      renderTick: 0,
      transTextRefs: {},

      // Toasts
      toasts: [],
      toastCounter: 0,
    }
  },

  computed: {
    totalPages() {
      return this.galleryImages.length
    },
  },

  watch: {
    renderTick() {
      if (this.showTranslation && Object.keys(this.transTextRefs).length) {
        this.applyTextFit()
      }
    },
    showTranslation(val) {
      if (val && Object.keys(this.transTextRefs).length) {
        this.$nextTick(() => this.applyTextFit())
      }
    },
  },

  created() {
    this.gid = this.$route.params.gid
    this.token = this.$route.query.token || null
    const page = parseInt(this.$route.query.page) || 1
    this.currentPage = page

    const savedPwd = sessionStorage.getItem(SESSION_KEY)
    if (savedPwd) {
      this.passwordInput = savedPwd
      this.verifyPassword()
    }
  },

  mounted() {
    this._ro = new ResizeObserver(() => { this.renderTick++ })
    if (this.$refs.containerRef) this._ro.observe(this.$refs.containerRef)
  },

  beforeUnmount() {
    this._ro?.disconnect()
  },

  methods: {
    // ── Auth ──────────────────────────────────────────────────────────────────

    async verifyPassword() {
      if (!this.passwordInput) return
      this.passwordLoading = true
      this.passwordError = ''
      try {
        const res = await fetch(`${API_BASE}/api/trans-verify`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password: this.passwordInput }),
        })
        if (res.ok) {
          sessionStorage.setItem(SESSION_KEY, this.passwordInput)
          this.passwordVerified = true
          this.$nextTick(() => {
            if (this.$refs.containerRef) this._ro?.observe(this.$refs.containerRef)
          })
          this.loadGalleryImages()
        } else {
          this.passwordError = '密码错误'
          sessionStorage.removeItem(SESSION_KEY)
        }
      } catch {
        this.passwordError = '验证失败，请检查网络'
      } finally {
        this.passwordLoading = false
      }
    },

    // ── Gallery images ────────────────────────────────────────────────────────

    async loadGalleryImages() {
      if (!this.token) {
        this.imagesError = '缺少 token 参数'
        return
      }
      this.imagesLoading = true
      this.imagesError = null
      try {
        const res = await fetch(`${API_BASE}/api/gallery-images?gid=${this.gid}&token=${this.token}`)
        const data = await res.json()
        if (data.error === 'exhentai_blocked') {
          this.imagesError = 'ExHentai 独占画廊，服务器无法访问缩略图'
        } else if (data.error) {
          throw new Error(data.error)
        } else {
          this.galleryImages = data.images.slice(0, data.total)
          this.thumbSource = data.source || null
          // Compute sprite count for thumbnail rendering
          const spriteCount = {}
          for (const img of this.galleryImages) {
            spriteCount[img.thumbSprite] = (spriteCount[img.thumbSprite] || 0) + 1
          }
          for (const img of this.galleryImages) {
            img.spriteN = spriteCount[img.thumbSprite] || 1
          }
          // Load the initial page
          const targetPage = Math.min(Math.max(this.currentPage, 1), data.total)
          this.goToPage(targetPage)
        }
      } catch (e) {
        this.imagesError = e.message
      } finally {
        this.imagesLoading = false
      }
    },

    // ── Page navigation ───────────────────────────────────────────────────────

    async goToPage(pageNum) {
      this.currentPage = pageNum
      this.ocrResults = []
      this.selectedBoxIdx = null
      this.imageUrl = null
      this.imageUrlRaw = null
      this.imageError = null
      this.imageLoading = true

      // Scroll strip to center selected thumb
      this.$nextTick(() => {
        const strip = this.$refs.stripRef
        if (!strip) return
        const thumb = strip.querySelector('.gt-thumb-active')
        if (thumb) {
          const stripRect = strip.getBoundingClientRect()
          const thumbRect = thumb.getBoundingClientRect()
          strip.scrollLeft += thumbRect.left - stripRect.left - stripRect.width / 2 + thumbRect.width / 2
        }
      })

      const img = this.galleryImages[pageNum - 1]
      if (!img?.pageUrl) {
        this.imageLoading = false
        this.imageError = '无法获取页面 URL'
        return
      }

      try {
        const res = await fetch(
          `${API_BASE}/api/image-url?pageUrl=${encodeURIComponent(img.pageUrl)}`
        )
        const data = await res.json()
        if (data.error) throw new Error(data.error)
        this.imageUrlRaw = data.imageUrl
        this.imageUrl = `${API_BASE}/api/image-proxy?imageUrl=${encodeURIComponent(data.imageUrl)}`
        this.nlParam = data.nlParam
      } catch (e) {
        this.imageError = `图片加载失败: ${e.message}`
      } finally {
        this.imageLoading = false
      }
    },

    prevPage() {
      if (this.currentPage > 1) this.goToPage(this.currentPage - 1)
    },

    nextPage() {
      if (this.currentPage < this.totalPages) this.goToPage(this.currentPage + 1)
    },

    onImageLoad() {
      this.renderTick++
    },

    // ── OCR ───────────────────────────────────────────────────────────────────

    async performOcr() {
      if (!this.imageUrl) return
      this.ocrProcessing = true
      this.ocrResults = []
      this.selectedBoxIdx = null
      this.showToast('正在 OCR 识别...', 'info')
      try {
        const res = await fetch(`${API_BASE}/api/trans-ocr`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            password: sessionStorage.getItem(SESSION_KEY),
            imageUrl: this.imageUrlRaw,
          }),
        })
        const data = await res.json()
        if (res.status === 401) {
          this.handleAuthError()
          return
        }
        if (data.error) throw new Error(data.error)

        // Merge results client-side
        this.ocrResults = mergeOcrResults(data.results)
        this.showToast(`识别完成，共 ${this.ocrResults.length} 个文本区域`, 'success')
      } catch (e) {
        this.showToast('OCR 失败: ' + e.message, 'error')
      } finally {
        this.ocrProcessing = false
      }
    },

    // ── Translate ─────────────────────────────────────────────────────────────

    async performTranslate() {
      if (!this.ocrResults.length) return
      this.translating = true
      this.showToast(`翻译中，共 ${this.ocrResults.length} 条文本...`, 'info')
      try {
        const res = await fetch(`${API_BASE}/api/trans-translate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            password: sessionStorage.getItem(SESSION_KEY),
            texts: this.ocrResults.map(r => r.text),
          }),
        })
        const data = await res.json()
        if (res.status === 401) {
          this.handleAuthError()
          return
        }
        if (data.error) throw new Error(data.error)

        this.ocrResults = this.ocrResults.map((r, i) => ({
          ...r,
          translation: data.translations[i] ?? null,
        }))
        this.showToast('翻译完成', 'success')
        this.$nextTick(() => this.applyTextFit())
      } catch (e) {
        this.showToast('翻译失败: ' + e.message, 'error')
      } finally {
        this.translating = false
      }
    },

    clearResults() {
      this.ocrResults = []
      this.selectedBoxIdx = null
      this.transTextRefs = {}
    },

    handleAuthError() {
      sessionStorage.removeItem(SESSION_KEY)
      this.passwordVerified = false
      this.passwordInput = ''
      this.passwordError = '密码已失效，请重新输入'
    },

    // ── Text fit ──────────────────────────────────────────────────────────────

    setTransTextRef(el, i) {
      if (el) this.transTextRefs[i] = el
      else delete this.transTextRefs[i]
    },

    applyTextFit() {
      requestAnimationFrame(() => {
        for (const el of Object.values(this.transTextRefs)) {
          fitTextToBox(el)
        }
      })
    },

    // ── Box positioning ───────────────────────────────────────────────────────

    getBoxStyle(bbox) {
      const img = this.$refs.imgRef
      const cont = this.$refs.containerRef
      if (!img || !cont || !img.naturalWidth) return { display: 'none' }
      const ir = img.getBoundingClientRect()
      const cr = cont.getBoundingClientRect()
      const sx = img.clientWidth / img.naturalWidth
      const sy = img.clientHeight / img.naturalHeight
      const [x1, y1, x2, y2] = bbox
      return {
        position: 'absolute',
        left: Math.round(ir.left - cr.left + x1 * sx) + 'px',
        top: Math.round(ir.top - cr.top + y1 * sy) + 'px',
        width: Math.round((x2 - x1) * sx) + 'px',
        height: Math.round((y2 - y1) * sy) + 'px',
      }
    },

    // ── Thumbnail rendering ───────────────────────────────────────────────────

    thumbCellStyle(img) {
      return { aspectRatio: `${img.thumbW} / ${img.thumbH}`, height: '72px' }
    },

    thumbInnerStyle(img) {
      const N = img.spriteN || 1
      const index = img.thumbW > 0 ? Math.round(-img.thumbX / img.thumbW) : 0
      const posX = N <= 1 ? 0 : (index / (N - 1)) * 100
      return {
        backgroundImage: `url(${img.thumbSprite})`,
        backgroundSize: `${N * 100}% auto`,
        backgroundPosition: `${posX}% 0`,
        backgroundRepeat: 'no-repeat',
        width: '100%',
        height: '100%',
      }
    },

    // ── Toasts ────────────────────────────────────────────────────────────────

    showToast(msg, type = 'info', duration = 3500) {
      const id = ++this.toastCounter
      this.toasts = [...this.toasts.slice(-2), { id, msg, type }]
      if (type !== 'error') setTimeout(() => this.removeToast(id), duration)
    },

    removeToast(id) {
      this.toasts = this.toasts.filter(t => t.id !== id)
    },
  },
}
</script>

<style scoped>
/* ── Layout ──────────────────────────────────────────────────────────────────── */

.gt-workbench {
  display: flex;
  flex-direction: column;
  height: 100dvh;
  overflow: hidden;
  background: var(--bg-color);
  color: var(--text-color);
}

/* ── Password overlay ────────────────────────────────────────────────────────── */

.gt-overlay {
  position: fixed;
  inset: 0;
  background: var(--bg-color);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.gt-pwd-dialog {
  background: var(--row-bg);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 32px;
  max-width: 400px;
  width: calc(100vw - 48px);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.gt-pwd-eyebrow {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--primary-color);
}

.gt-pwd-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--text-color);
}

.gt-pwd-desc {
  margin: 0;
  font-size: 13px;
  color: var(--muted-color);
}

.gt-pwd-form {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

.gt-pwd-input {
  flex: 1;
  height: 38px;
  padding: 0 12px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: var(--bg-color);
  color: var(--text-color);
  font-size: 14px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.15s;
}
.gt-pwd-input:focus { border-color: var(--primary-color); }
.gt-pwd-input:disabled { opacity: 0.5; }

.gt-pwd-error {
  margin: 0;
  font-size: 12px;
  color: #f87171;
}

.gt-pwd-back {
  background: none;
  border: none;
  color: var(--muted-color);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  font-family: inherit;
  text-align: left;
  margin-top: 4px;
  transition: color 0.15s;
}
.gt-pwd-back:hover { color: var(--text-color); }

/* ── Header ──────────────────────────────────────────────────────────────────── */

.gt-header {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 52px;
  padding: 0 16px;
  background: var(--row-bg);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.1);
}

.gt-back-btn {
  height: 32px;
  padding: 0 12px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--muted-color);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
  transition: color 0.15s, background 0.15s;
  flex-shrink: 0;
}
.gt-back-btn:hover { background: var(--hover-bg); color: var(--text-color); }

.gt-header-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.gt-header-pages {
  font-size: 12px;
  color: var(--muted-color);
  white-space: nowrap;
}

.gt-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}


/* ── Shared button ───────────────────────────────────────────────────────────── */

.gt-btn {
  height: 32px;
  padding: 0 14px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: var(--row-bg);
  color: var(--text-color);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, color 0.15s, border-color 0.15s, opacity 0.15s;
}
.gt-btn:hover:not(:disabled) { background: var(--hover-bg); border-color: var(--muted-color); }
.gt-btn:disabled { opacity: 0.4; cursor: default; }

.gt-btn-primary {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: #fff;
  font-weight: 600;
}
.gt-btn-primary:hover:not(:disabled) { background: var(--primary-color-hover); border-color: var(--primary-color-hover); }

.gt-btn-sm { height: 26px; padding: 0 10px; font-size: 12px; }

.gt-btn-danger {
  border-color: rgba(248, 113, 113, 0.4);
  color: #f87171;
  background: rgba(248, 113, 113, 0.06);
}
.gt-btn-danger:hover:not(:disabled) { background: rgba(248, 113, 113, 0.12); }


/* ── Thumbnail strip ─────────────────────────────────────────────────────────── */

.gt-strip {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 96px;
  padding: 8px;
  background: var(--sidebar-bg);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
  overflow: hidden;
  width: 100%;
  box-sizing: border-box;
}

.gt-strip-loading,
.gt-strip-error {
  font-size: 12px;
  color: var(--muted-color);
  gap: 8px;
  justify-content: center;
}

.gt-strip-nav {
  height: 36px;
  width: 28px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: var(--row-bg);
  color: var(--text-color);
  font-size: 18px;
  cursor: pointer;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}
.gt-strip-nav:hover:not(:disabled) { background: var(--hover-bg); }
.gt-strip-nav:disabled { opacity: 0.35; cursor: default; }

.gt-strip-scroll {
  display: flex;
  gap: 4px;
  overflow-x: auto;
  flex: 1;
  scrollbar-width: thin;
  scrollbar-color: var(--scrollbar-thumb) transparent;
  padding-bottom: 4px;
}

.gt-thumb {
  position: relative;
  flex-shrink: 0;
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
  border: 2px solid transparent;
  transition: border-color 0.15s, transform 0.1s;
}
.gt-thumb:hover { border-color: var(--muted-color); transform: scale(1.05); }
.gt-thumb-active { border-color: var(--primary-color) !important; }

.gt-thumb-inner {
  width: 100%;
  height: 100%;
}

.gt-thumb-num {
  position: absolute;
  bottom: 2px;
  left: 3px;
  font-size: 9px;
  font-weight: 700;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.8);
  line-height: 1;
  pointer-events: none;
}

/* ── Body (image + sidebar) ──────────────────────────────────────────────────── */

.gt-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* ── Image panel ─────────────────────────────────────────────────────────────── */

.gt-image-panel {
  flex: 1;
  min-width: 0;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-color);
  overflow: hidden;
}

.gt-image-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--muted-color);
  font-size: 13px;
  padding: 64px 24px;
}

.gt-image-error { color: #f87171; }

.gt-image-empty { text-align: center; }

.gt-empty-icon { font-size: 40px; }

.gt-page-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  display: block;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
}

/* ── OCR boxes overlay ───────────────────────────────────────────────────────── */

.gt-boxes-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.gt-ocr-box {
  position: absolute;
  border: 1.5px solid rgba(100, 108, 255, 0.6);
  background: rgba(100, 108, 255, 0.04);
  border-radius: 2px;
  cursor: pointer;
  pointer-events: all;
  overflow: hidden;
  display: flex;
  align-items: stretch;
  transition: border-color 0.1s, background 0.1s;
}
.gt-ocr-box:hover { border-color: var(--primary-color); background: rgba(100, 108, 255, 0.08); }
.gt-box-selected { border-color: var(--primary-color) !important; background: rgba(100, 108, 255, 0.12) !important; box-shadow: 0 0 0 2px rgba(100, 108, 255, 0.25); }
.gt-box-translated { border-color: rgba(74, 222, 128, 0.5); }
.gt-box-hidden { border-color: transparent !important; background: transparent !important; }

.gt-box-trans-text {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1.2;
  text-align: center;
  word-break: break-word;
  white-space: pre-wrap;
  padding: 2px;
  box-sizing: border-box;
  background: rgba(0, 0, 0, 0.75);
  color: #fff;
  overflow: hidden;
}

.gt-sidebar-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.gt-toggle-label {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  font-size: 12px;
  color: var(--muted-color);
  user-select: none;
}

.gt-toggle-cb { cursor: pointer; accent-color: var(--primary-color); }

/* ── Sidebar ─────────────────────────────────────────────────────────────────── */

.gt-sidebar {
  width: 40%;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--row-bg);
  border-left: 1px solid var(--border-color);
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--scrollbar-thumb) transparent;
}

.gt-sidebar-hdr {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.gt-sidebar-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-color);
}

.gt-count-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 10px;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  color: var(--muted-color);
}

.gt-translated-badge {
  font-size: 11px;
  color: #4ade80;
  margin-left: auto;
}

.gt-sidebar-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--muted-color);
  font-size: 13px;
  text-align: center;
  padding: 32px;
}

.gt-sidebar-empty-icon { font-size: 36px; }

.gt-results-list {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.gt-result-item {
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--surface-color);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.gt-result-item:hover { background: var(--hover-bg); }
.gt-result-selected {
  border-color: var(--primary-color) !important;
  background: rgba(100, 108, 255, 0.06) !important;
  box-shadow: 0 0 0 1px rgba(100, 108, 255, 0.2);
}

.gt-result-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.gt-result-idx {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--row-bg);
  border: 1px solid var(--border-color);
  color: var(--muted-color);
}

.gt-result-conf {
  font-size: 11px;
  color: var(--muted-color);
  font-variant-numeric: tabular-nums;
}

.gt-merged-badge {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(100, 108, 255, 0.1);
  color: var(--primary-color);
  border: 1px solid rgba(100, 108, 255, 0.2);
}

.gt-done-mark {
  font-size: 10px;
  color: #4ade80;
  margin-left: auto;
}

.gt-result-orig {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--muted-color);
  word-break: break-all;
}

.gt-result-trans {
  margin: 8px 0 0;
  padding-top: 8px;
  border-top: 1px solid var(--border-color);
  font-size: 12px;
  line-height: 1.5;
  color: var(--primary-color);
  word-break: break-all;
}

/* ── Spinners ────────────────────────────────────────────────────────────────── */

.gt-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: gt-spin 0.7s linear infinite;
}

.gt-spinner-sm {
  width: 16px;
  height: 16px;
  border: 2px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: gt-spin 0.7s linear infinite;
}

@keyframes gt-spin { to { transform: rotate(360deg); } }

/* ── Toasts ──────────────────────────────────────────────────────────────────── */

.gt-toasts {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 200;
  pointer-events: none;
  max-width: 400px;
  width: calc(100vw - 32px);
}

.gt-toast {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  background: var(--row-bg);
  border: 1px solid var(--border-color);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  pointer-events: all;
  color: var(--text-color);
  animation: gt-toast-in 0.2s ease;
}

.gt-toast span { flex: 1; }

.gt-toast-success { border-color: rgba(74, 222, 128, 0.35); color: #4ade80; }
.gt-toast-error   { border-color: rgba(248, 113, 113, 0.35); color: #f87171; }
.gt-toast-info    { color: var(--text-color); }

.gt-toast-close {
  background: none;
  border: none;
  color: inherit;
  opacity: 0.5;
  cursor: pointer;
  font-size: 16px;
  padding: 0;
  line-height: 1;
  flex-shrink: 0;
}
.gt-toast-close:hover { opacity: 1; }

@keyframes gt-toast-in {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ── Mobile ──────────────────────────────────────────────────────────────────── */

/* ── Source indicator ────────────────────────────────────────────────────────── */

.gt-source-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  flex-shrink: 0;
}
.gt-source-e-hentai {
  color: #4ade80;
  border-color: rgba(74, 222, 128, 0.35);
  background: rgba(74, 222, 128, 0.08);
}
.gt-source-e-hentai .gt-source-dot { background: #4ade80; }
.gt-source-exhentai {
  color: #a78bfa;
  border-color: rgba(167, 139, 250, 0.35);
  background: rgba(167, 139, 250, 0.08);
}
.gt-source-exhentai .gt-source-dot { background: #a78bfa; }

@media (max-width: 900px) {
  .gt-sidebar { width: 45%; }
}

@media (max-width: 640px) {
  .gt-workbench {
    height: auto;
    min-height: 100dvh;
    overflow: visible;
  }
  .gt-header {
    position: sticky;
    top: 0;
    z-index: 10;
  }
  .gt-body {
    flex-direction: column;
    flex: none;
    min-height: 0;
    overflow: visible;
  }
  .gt-image-panel {
    display: block;
    overflow: visible;
    min-height: 200px;
  }
  .gt-page-img {
    width: 100%;
    height: auto;
    max-height: none;
  }
  .gt-sidebar {
    width: 100%;
    overflow-y: visible;
    border-left: none;
    border-top: 1px solid var(--border-color);
  }
}
</style>
