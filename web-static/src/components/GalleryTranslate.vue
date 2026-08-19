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
  <div v-else class="gt-workbench" :style="{ '--gt-sheet-h': sheetHeight }">
    <!-- Header -->
    <header class="gt-header">
      <button class="gt-back-btn" @click="$router.back()">←</button>

      <div class="gt-header-info">
        <span v-if="totalPages" class="gt-header-pages">{{ currentPage }} / {{ totalPages }}p</span>
      </div>

      <div class="gt-header-actions">
        <button
          class="gt-btn gt-btn-primary"
          :disabled="!imageUrl || ocrProcessing || translating || imagesLoading"
          @click="performOcrAndTranslate"
        >
          {{ ocrProcessing ? '识别中...' : translating ? '翻译中...' : '翻译' }}
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
              :key="result._id"
              class="gt-ocr-box"
              :class="{
                'gt-box-selected': selectedBoxIdx === i,
                'gt-box-translated': !!result.translation,
                'gt-box-hidden': !showBoxes,
              }"
              :style="getBoxStyle(result, i)"
              :title="result.translation || result.text"
              @click="onBoxClick(i)"
            >
              <span
                v-if="showTranslation && result.translation"
                class="gt-box-trans-text"
                :ref="el => setTransTextRef(el, result._id)"
              >{{ result.translation }}</span>
            </div>
          </div>
        </template>
        <div v-else class="gt-image-placeholder gt-image-empty">
          <div class="gt-empty-icon">📖</div>
          <p>从右侧选择页面</p>
        </div>

      </div>

      <!-- Sidebar（移动端为底部抽屉） -->
      <div
        ref="sidebarRef"
        class="gt-sidebar"
        :class="[`is-${sheetState}`, { 'is-dragging': sheetDragging }]"
      >
        <!-- 移动端抽屉把手：收起时只占一条，图片区因此能拿到整屏 -->
        <div
          class="gt-sheet-handle"
          role="button"
          tabindex="0"
          :aria-expanded="sheetState !== 'peek'"
          aria-label="识别结果面板"
          @pointerdown="onSheetPointerDown"
          @keydown.enter.prevent="cycleSheet"
          @keydown.space.prevent="cycleSheet"
        >
          <span class="gt-sheet-grip"></span>
          <div class="gt-sheet-row">
            <button
              class="gt-sheet-nav"
              type="button"
              :disabled="currentPage <= 1"
              aria-label="上一页"
              @pointerdown.stop
              @click.stop="prevPage"
            >‹</button>
            <span class="gt-sheet-label">
              识别结果
              <span v-if="ocrResults.length" class="gt-sheet-count">{{ ocrResults.length }}</span>
            </span>
            <button
              class="gt-sheet-nav"
              type="button"
              :disabled="currentPage >= totalPages"
              aria-label="下一页"
              @pointerdown.stop
              @click.stop="nextPage"
            >›</button>
          </div>
        </div>

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
              :data-page="img.pageNum"
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

        <!-- Config panel -->
        <div class="gt-config-panel" :class="{ 'gt-config-panel-collapsed': !configPanelExpanded }">
          <button class="gt-config-toggle" @click="configPanelExpanded = !configPanelExpanded">
            <span>功能设置</span>
            <span class="gt-config-toggle-icon" :class="{ 'is-open': configPanelExpanded }">⌃</span>
          </button>
          <template v-if="configPanelExpanded">
          <div class="gt-cfg-row">
            <span class="gt-cfg-key">OCR</span>
            <div class="gt-seg-ctrl">
              <button class="gt-seg-btn" :class="{ active: ocrSource === 'google' }" @click="ocrSource = 'google'">
                <span class="gt-seg-dot google"></span>Google
              </button>
              <button class="gt-seg-btn" :class="{ active: ocrSource === 'paddle' }" @click="ocrSource = 'paddle'">
                <span class="gt-seg-dot paddle"></span>Paddle
              </button>
              <button class="gt-seg-btn" :class="{ active: ocrSource === 'ocrspace' }" @click="ocrSource = 'ocrspace'">
                <span class="gt-seg-dot ocrspace"></span>OCR.Space
              </button>
            </div>
            <button class="gt-clear-btn" :disabled="!ocrResults.length" @click="clearResults">清空</button>
          </div>
          <div class="gt-cfg-row">
            <span class="gt-cfg-key">显示</span>
            <div class="gt-chip-group">
              <button class="gt-chip" :class="{ active: showBoxes }" @click="showBoxes = !showBoxes">框</button>
              <button class="gt-chip" :class="{ active: showTranslation }" @click="showTranslation = !showTranslation">译文</button>
            </div>
          </div>
          <div class="gt-cfg-row">
            <span class="gt-cfg-key">自动</span>
            <label class="gt-switch-row">
              <button
                type="button"
                class="gt-switch"
                :class="{ active: autoTranslate }"
                :aria-pressed="autoTranslate"
                @click="autoTranslate = !autoTranslate"
              >
                <span class="gt-switch-thumb"></span>
              </button>
            </label>
          </div>
          <div class="gt-cfg-row">
            <span class="gt-cfg-key">学习</span>
            <label class="gt-switch-row">
              <button
                type="button"
                class="gt-switch"
                :class="{ active: studyMode }"
                :aria-pressed="studyMode"
                :disabled="kuromojiLoading"
                @click="toggleStudyMode"
              >
                <span class="gt-switch-thumb"></span>
              </button>
            </label>
            <span v-if="studyMode" class="gt-pos-legend">
              <span v-for="(color, pos) in { '名詞': '#60a5fa', '動詞': '#4ade80', '形容詞': '#fb923c', '副詞': '#c084fc', '助詞': '#22d3ee', '助動詞': '#34d399' }" :key="pos" class="gt-pos-dot" :style="{ '--dot-color': color }" :data-pos="pos"></span>
            </span>
          </div>
          </template>
        </div>

        <div class="gt-sidebar-hdr">
          <span class="gt-sidebar-title">识别结果</span>
          <span v-if="ocrResults.length" class="gt-count-badge">{{ ocrResults.length }}</span>
          <span v-if="ocrResults.some(r => r.translation)" class="gt-translated-badge">已翻译</span>
        </div>

        <div v-if="!ocrResults.length" class="gt-sidebar-empty">
          <div class="gt-sidebar-empty-icon">🔍</div>
          <p>{{ imageUrl ? '点击 OCR 开始识别' : '请先选择页面' }}</p>
        </div>

        <div v-else class="gt-results-list">
          <div
            v-for="(result, i) in ocrResults"
            :key="result._id"
            class="gt-result-item"
            :data-idx="i"
            :class="{ 'gt-result-selected': selectedBoxIdx === i }"
            @click="selectedBoxIdx = selectedBoxIdx === i ? null : i"
          >
            <div class="gt-result-meta">
              <span class="gt-result-idx">{{ i + 1 }}</span>
              <span class="gt-result-conf">{{ (result.confidence * 100).toFixed(0) }}%</span>
              <span v-if="result.is_merged" class="gt-merged-badge">合并×{{ result.original_count }}</span>
              <span v-if="result.translation" class="gt-done-mark">✓</span>
              <button class="gt-result-del" @click.stop="deleteResult(i)" title="删除">×</button>
            </div>
            <div v-if="studyMode && studyTokens[result._id]" class="gt-result-orig gt-token-line">
              <span
                v-for="(token, ti) in studyTokens[result._id]"
                :key="ti"
                class="gt-token"
                :style="getTokenStyle(token)"
                @click.stop="onTokenClick(token)"
              >
                <ruby v-if="hasKanji(token.surface_form) && token.reading && token.reading !== '*'">{{ token.surface_form }}<rt>{{ toHiragana(token.reading) }}</rt></ruby>
                <template v-else>{{ token.surface_form }}</template>
              </span>
            </div>
            <p v-else class="gt-result-orig">{{ result.text }}</p>
            <p v-if="result.translation" class="gt-result-trans">{{ result.translation }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Word Card -->
    <Transition name="gt-wc">
      <div v-if="wordCard" class="gt-wc-overlay" @click.self="wordCard = null">
        <div class="gt-wc-panel">
          <div class="gt-wc-header">
            <div class="gt-wc-title-row">
              <span class="gt-wc-surface">{{ wordCard.token.surface_form }}</span>
              <span
                v-if="wordCard.token.reading && wordCard.token.reading !== '*' && wordCard.token.reading !== wordCard.token.surface_form"
                class="gt-wc-kana"
              >{{ wordCard.token.reading }}</span>
              <span v-if="wordCard.word !== wordCard.token.surface_form" class="gt-wc-base-form">→ {{ wordCard.word }}</span>
            </div>
            <div class="gt-wc-meta-row">
              <span class="gt-wc-pos-badge" :style="{ background: getPosColor(wordCard.token.pos) + '22', color: getPosColor(wordCard.token.pos), borderColor: getPosColor(wordCard.token.pos) + '55' }">
                {{ wordCard.token.pos }}{{ wordCard.token.pos_detail_1 && wordCard.token.pos_detail_1 !== '*' ? '・' + wordCard.token.pos_detail_1 : '' }}
              </span>
              <span v-if="wordCard.token.conjugated_form && wordCard.token.conjugated_form !== '*'" class="gt-wc-conj">{{ wordCard.token.conjugated_form }}</span>
            </div>
            <button class="gt-wc-close" @click="wordCard = null">×</button>
          </div>

          <div class="gt-wc-body">
            <div v-if="wordCard.loading" class="gt-wc-state">
              <div class="gt-spinner-sm"></div><span>查询中...</span>
            </div>
            <div v-else-if="wordCard.error" class="gt-wc-state gt-wc-err">{{ wordCard.error }}</div>
            <div v-else-if="!wordCard.entries?.length" class="gt-wc-state">未找到词条</div>
            <div v-else class="gt-wc-entries">
              <div v-for="(entry, ei) in wordCard.entries" :key="ei" class="gt-wc-entry">
                <div class="gt-wc-entry-head">
                  <span class="gt-wc-entry-word">{{ entry.word }}</span>
                  <span v-if="entry.reading" class="gt-wc-entry-reading">{{ entry.reading }}</span>
                  <span v-if="entry.is_common" class="gt-wc-badge gt-wc-common">常用</span>
                  <span v-for="j in entry.jlpt" :key="j" class="gt-wc-badge gt-wc-jlpt">{{ j }}</span>
                </div>
                <ol class="gt-wc-senses">
                  <li v-for="(sense, si) in entry.senses" :key="si" class="gt-wc-sense">
                    <span v-if="sense.parts_of_speech.length" class="gt-wc-sense-pos">{{ sense.parts_of_speech.join(', ') }}</span>
                    {{ sense.english_definitions.join('; ') }}
                    <span v-if="sense.info.length" class="gt-wc-sense-info">（{{ sense.info.join(', ') }}）</span>
                  </li>
                </ol>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>

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
const TRANS_CACHE_TTL = 3 * 24 * 60 * 60 * 1000

/* 移动端底部抽屉的三个档位。peek 与 CSS 里的 --gt-sheet-peek 保持一致 */
const SHEET_PEEK_PX = 64
const SHEET_SNAPS = { peek: `${SHEET_PEEK_PX}px`, half: '50dvh', full: '88dvh' }
const SHEET_ORDER = ['peek', 'half', 'full']

// ── Kuromoji (CDN lazy-load, singleton) ───────────────────────────────────────

let _kuromojiTokenizer = null
let _kuromojiPromise = null

function loadKuromoji() {
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

// POS → highlight color
const POS_COLOR = {
  '名詞':     '#60a5fa',  // blue
  '動詞':     '#4ade80',  // green
  '形容詞':   '#fb923c',  // orange
  '形容動詞': '#fbbf24',  // yellow
  '副詞':     '#c084fc',  // purple
  '接続詞':   '#f472b6',  // pink
  '感動詞':   '#f87171',  // red
  '助詞':     '#22d3ee',  // cyan
  '助動詞':   '#34d399',  // emerald
  '連体詞':   '#a3e635',  // lime
}

function hasKanji(str) {
  return /[一-鿿㐀-䶿]/.test(str)
}

function toHiragana(katakana) {
  return katakana.replace(/[ァ-ヶ]/g, ch => String.fromCharCode(ch.charCodeAt(0) - 0x60))
}

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

// Returns true if text fits, false if still overflowing at minSize
function fitTextToBox(el, minSize = 1) {
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
      autoTranslate: false,
      configPanelExpanded: true,
      /* 移动端底部抽屉：peek 只留把手（图片占满整屏）→ half → full */
      sheetState: 'peek',
      sheetDragging: false,
      sheetDragH: null,
      selectedBoxIdx: null,
      ocrSource: 'google',
      lastOcrSource: null,
      expandedBboxes: {},
      renderTick: 0,
      transTextRefs: {},

      // Toasts
      toasts: [],
      toastCounter: 0,

      // Thumbnail lazy load
      loadedThumbPages: {},

      // Study mode
      studyMode: false,
      kuromojiLoading: false,
      studyTokens: {},
      wordCard: null,
    }
  },

  computed: {
    totalPages() {
      return this.galleryImages.length
    },
    /** 抽屉高度：拖拽中用像素跟手，松手后落到档位 */
    sheetHeight() {
      if (this.sheetDragH != null) return `${this.sheetDragH}px`
      return SHEET_SNAPS[this.sheetState] || SHEET_SNAPS.peek
    },
  },

  watch: {
    renderTick() {
      if (this.showTranslation && Object.keys(this.transTextRefs).length) {
        this.expandedBboxes = {}
        this.$nextTick(() => this.applyTextFit())
      }
    },
    showTranslation(val) {
      this.expandedBboxes = {}
      if (!val) {
        this.transTextRefs = {}
        return
      }
      this.$nextTick(() => this.applyTextFit())
    },
    ocrResults(newVal) {
      if (this.studyMode) {
        if (newVal.length) this.analyzeAllResults()
        else this.studyTokens = {}
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
    this._thumbObserver?.disconnect()
  },

  methods: {
    // ── 移动端底部抽屉 ─────────────────────────────────────────────────────────

    /** 各档位换算成像素，用于拖拽吸附 */
    sheetSnapPixels() {
      const vh = window.innerHeight
      return { peek: SHEET_PEEK_PX, half: vh * 0.5, full: vh * 0.88 }
    },

    setSheet(state) {
      this.sheetState = state
      this.sheetDragH = null
      // 高度变化会改变图片可用区域，OCR 框需要重算
      this.$nextTick(() => { this.renderTick++ })
    },

    cycleSheet() {
      const next = SHEET_ORDER[(SHEET_ORDER.indexOf(this.sheetState) + 1) % SHEET_ORDER.length]
      this.setSheet(next)
    },

    onSheetPointerDown(e) {
      // 桌面端没有抽屉
      if (window.innerWidth > 767) return
      const el = this.$refs.sidebarRef
      if (!el) return
      const startY = e.clientY
      const startH = el.getBoundingClientRect().height
      let moved = 0

      const onMove = ev => {
        moved = Math.max(moved, Math.abs(ev.clientY - startY))
        if (moved < 4) return
        this.sheetDragging = true
        const max = window.innerHeight * 0.88
        this.sheetDragH = Math.min(max, Math.max(SHEET_PEEK_PX, startH - (ev.clientY - startY)))
      }

      const onUp = () => {
        window.removeEventListener('pointermove', onMove)
        window.removeEventListener('pointerup', onUp)
        window.removeEventListener('pointercancel', onUp)
        if (moved < 4) {
          // 视为点击：在三档之间轮转
          this.sheetDragging = false
          this.cycleSheet()
          return
        }
        const h = this.sheetDragH ?? startH
        const snaps = this.sheetSnapPixels()
        const nearest = SHEET_ORDER.reduce((best, k) =>
          Math.abs(snaps[k] - h) < Math.abs(snaps[best] - h) ? k : best, 'peek')
        this.sheetDragging = false
        this.setSheet(nearest)
      }

      window.addEventListener('pointermove', onMove)
      window.addEventListener('pointerup', onUp)
      window.addEventListener('pointercancel', onUp)
    },

    /** 点击图片上的 OCR 框：移动端顺带把抽屉抬起来并滚到对应条目 */
    onBoxClick(i) {
      const next = this.selectedBoxIdx === i ? null : i
      this.selectedBoxIdx = next
      if (next == null || window.innerWidth > 767) return
      if (this.sheetState === 'peek') this.setSheet('half')
      this.$nextTick(() => {
        const el = this.$refs.sidebarRef?.querySelector(`.gt-result-item[data-idx="${next}"]`)
        el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
      })
    },

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
          loadKuromoji().catch(() => {}) // preload dict while user browses/waits for OCR
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
          // Compute sprite count and max offset for thumbnail rendering
          const spriteMeta = {}
          for (const img of this.galleryImages) {
            const prev = spriteMeta[img.thumbSprite] || { count: 0, maxOffset: 0 }
            spriteMeta[img.thumbSprite] = {
              count: prev.count + 1,
              maxOffset: Math.max(prev.maxOffset, -img.thumbX),
            }
          }
          for (const img of this.galleryImages) {
            const meta = spriteMeta[img.thumbSprite] || { count: 1, maxOffset: 0 }
            img.spriteN = meta.count
            img.spriteMaxOffset = meta.maxOffset
          }
          // Load the initial page
          const targetPage = Math.min(Math.max(this.currentPage, 1), data.total)
          this.loadedThumbPages = {}
          this.$nextTick(() => this.setupThumbObserver())
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
      this.$router.replace({
        name: 'GalleryTranslate',
        params: { gid: this.gid },
        query: { token: this.token, page: String(pageNum) },
      })
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
        const cached = this.loadPageCache(pageNum)
        if (cached) {
          this.ocrResults = cached.ocrResults
          this.lastOcrSource = cached.lastOcrSource
          this.expandedBboxes = {}
          this.showToast(`已从缓存恢复 ${cached.ocrResults.length} 条结果`, 'info', 2000)
        } else if (this.autoTranslate) {
          await this.$nextTick()
          await this.performOcrAndTranslate()
        }
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

    async performOcrAndTranslate() {
      await this.performOcr()
      if (this.ocrResults.length) await this.performTranslate()
    },

    async getImageBase64() {
      const res = await fetch(this.imageUrl)
      if (!res.ok) throw new Error(`Failed to fetch image: HTTP ${res.status}`)
      const buf = await res.arrayBuffer()
      const bytes = new Uint8Array(buf)
      let binary = ''
      for (const b of bytes) binary += String.fromCharCode(b)
      return btoa(binary)
    },

    async performOcr() {
      if (!this.imageUrl) return
      this.ocrProcessing = true
      this.ocrResults = []
      this.selectedBoxIdx = null
      this.showToast('正在 OCR 识别...', 'info')
      try {
        const imageBase64 = await this.getImageBase64()
        const res = await fetch(`${API_BASE}/api/trans-ocr`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            password: sessionStorage.getItem(SESSION_KEY),
            imageBase64,
            ocrSource: this.ocrSource,
          }),
        })
        const data = await res.json()
        if (res.status === 401) {
          this.handleAuthError()
          return
        }
        if (data.error) throw new Error(data.error)

        const isVision = data.source === 'vision' || data.source === 'ocrspace'
        this.lastOcrSource = data.source
        this.expandedBboxes = {}
        this.ocrResults = mergeOcrResults(
          data.results,
          isVision ? 1.2 : 1.05,
          isVision ? 40 : 10,
        ).map((r, i) => ({ ...r, _id: `${Date.now()}_${i}` }))
        this.savePageCache()
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
        this.savePageCache()
        this.showToast('翻译完成', 'success')
        this.$nextTick(() => this.applyTextFit())
      } catch (e) {
        this.showToast('翻译失败: ' + e.message, 'error')
      } finally {
        this.translating = false
      }
    },

    deleteResult(i) {
      const id = this.ocrResults[i]._id
      this.ocrResults.splice(i, 1)
      delete this.transTextRefs[id]
      if (this.selectedBoxIdx === i) this.selectedBoxIdx = null
      else if (this.selectedBoxIdx > i) this.selectedBoxIdx--
      this.savePageCache()
    },

    clearResults() {
      try { localStorage.removeItem(this.cacheKey(this.currentPage)) } catch {}
      this.ocrResults = []
      this.selectedBoxIdx = null
      this.transTextRefs = {}
      this.expandedBboxes = {}
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
      const isVision = this.lastOcrSource === 'vision' || this.lastOcrSource === 'ocrspace'
      requestAnimationFrame(async () => {
        for (const [id, el] of Object.entries(this.transTextRefs)) {
          if (!el) continue
          if (!isVision) { fitTextToBox(el); continue }
          // Vision: try to fit at min 10px, expand bbox reactively if needed
          for (let step = 0; step <= 10; step++) {
            const currentEl = this.transTextRefs[id]
            if (!currentEl) break
            if (fitTextToBox(currentEl, 10)) break
            if (step === 10) break
            const result = this.ocrResults.find(r => r._id === id)
            if (!result) break
            const [bx1, by1, bx2, by2] = this.expandedBboxes[id] || result.bbox
            this.expandedBboxes = { ...this.expandedBboxes, [id]: [bx1 - 15, by1 - 15, bx2 + 15, by2 + 15] }
            await this.$nextTick()
          }
        }
      })
    },

    // ── Box positioning ───────────────────────────────────────────────────────

    getBoxStyle(result, index) {
      const img = this.$refs.imgRef
      const cont = this.$refs.containerRef
      if (!img || !cont || !img.naturalWidth) return { display: 'none' }
      const ir = img.getBoundingClientRect()
      const cr = cont.getBoundingClientRect()
      const sx = img.clientWidth / img.naturalWidth
      const sy = img.clientHeight / img.naturalHeight
      const [x1, y1, x2, y2] = this.expandedBboxes[result._id] || result.bbox
      return {
        position: 'absolute',
        left: Math.round(ir.left - cr.left + x1 * sx) + 'px',
        top: Math.round(ir.top - cr.top + y1 * sy) + 'px',
        width: Math.round((x2 - x1) * sx) + 'px',
        height: Math.round((y2 - y1) * sy) + 'px',
        zIndex: this.selectedBoxIdx === index ? 20 : 10,
      }
    },

    // ── Thumbnail lazy load ───────────────────────────────────────────────────

    setupThumbObserver() {
      this._thumbObserver?.disconnect()
      const strip = this.$refs.stripRef
      if (!strip) return
      this._thumbObserver = new IntersectionObserver((entries) => {
        const batch = {}
        for (const entry of entries) {
          if (entry.isIntersecting) {
            batch[entry.target.dataset.page] = true
            this._thumbObserver.unobserve(entry.target)
          }
        }
        if (Object.keys(batch).length) {
          this.loadedThumbPages = { ...this.loadedThumbPages, ...batch }
        }
      }, { root: strip, rootMargin: '0px 150px' })

      strip.querySelectorAll('.gt-thumb').forEach(el => {
        if (!this.loadedThumbPages[el.dataset.page]) {
          this._thumbObserver.observe(el)
        }
      })
    },

    // ── Thumbnail rendering ───────────────────────────────────────────────────

    thumbCellStyle(img) {
      return { aspectRatio: `${img.thumbW} / ${img.thumbH}`, height: '72px' }
    },

    thumbInnerStyle(img) {
      if (!this.loadedThumbPages[img.pageNum]) return { width: '100%', height: '100%' }
      const N = img.spriteN || 1
      const maxOffset = img.spriteMaxOffset || 0
      const posX = maxOffset > 0 ? (-img.thumbX / maxOffset) * 100 : 0
      return {
        backgroundImage: `url(${img.thumbSprite})`,
        backgroundSize: `${N * 100}% auto`,
        backgroundPosition: `${posX}% 0`,
        backgroundRepeat: 'no-repeat',
        width: '100%',
        height: '100%',
      }
    },

    // ── Study mode ────────────────────────────────────────────────────────────

    async toggleStudyMode() {
      this.studyMode = !this.studyMode
      if (!this.studyMode) { this.wordCard = null; return }
      if (this.ocrResults.length) await this.analyzeAllResults()
    },

    async analyzeAllResults() {
      if (this.kuromojiLoading) return
      this.kuromojiLoading = true
      if (!_kuromojiTokenizer) this.showToast('正在加载分词词典（约 8MB，首次较慢）...', 'info', 12000)
      try {
        const tokenizer = await loadKuromoji()
        const tokens = {}
        for (const result of this.ocrResults) {
          tokens[result._id] = tokenizer.tokenize(result.text)
        }
        this.studyTokens = tokens
      } catch (e) {
        this.showToast('kuromoji 加载失败: ' + e.message, 'error')
        this.studyMode = false
      } finally {
        this.kuromojiLoading = false
      }
    },

    isClickableToken(token) {
      // Skip whitespace and pure symbols
      if (!token.surface_form.trim()) return false
      if (token.pos === '記号') return false
      return true
    },

    isContentWord(token) {
      if (!POS_COLOR[token.pos]) return false
      const detail = token.pos_detail_1
      if (detail === '非自立' || detail === '接尾') return false
      return true
    },

    getTokenStyle(token) {
      if (!this.isClickableToken(token)) return { color: 'color-mix(in srgb, var(--text-color) 65%, transparent)' }
      const color = POS_COLOR[token.pos]
      const detail = token.pos_detail_1
      const isDependent = detail === '非自立' || detail === '接尾'
      if (isDependent || !color) {
        return { color: 'color-mix(in srgb, var(--text-color) 65%, transparent)', cursor: 'pointer', borderBottom: '1px dotted rgba(156,163,175,0.6)' }
      }
      return { color, cursor: 'pointer', borderBottom: `1px dotted ${color}99` }
    },

    async onTokenClick(token) {
      if (!this.isClickableToken(token)) return
      const word = token.basic_form && token.basic_form !== '*'
        ? token.basic_form : token.surface_form
      this.wordCard = { token, word, entries: null, loading: true, error: null }
      try {
        const res = await fetch(`${API_BASE}/api/jmdict-lookup?word=${encodeURIComponent(word)}`)
        const data = await res.json()
        if (data.error) throw new Error(data.error)
        this.wordCard = { ...this.wordCard, entries: data.results, loading: false }
      } catch (e) {
        this.wordCard = { ...this.wordCard, entries: [], loading: false, error: e.message }
      }
    },

    getPosColor(pos) {
      return POS_COLOR[pos] || '#6b7280'
    },

    hasKanji,
    toHiragana,

    // ── Translation cache ─────────────────────────────────────────────────────

    cacheKey(pageNum) {
      return `trans_cache_${this.gid}_p${pageNum}`
    },

    savePageCache() {
      if (!this.ocrResults.length) return
      try {
        localStorage.setItem(this.cacheKey(this.currentPage), JSON.stringify({
          ocrResults: this.ocrResults,
          lastOcrSource: this.lastOcrSource,
          ts: Date.now(),
        }))
      } catch {}
    },

    loadPageCache(pageNum) {
      try {
        const raw = localStorage.getItem(this.cacheKey(pageNum))
        if (!raw) return null
        const entry = JSON.parse(raw)
        if (Date.now() - entry.ts > TRANS_CACHE_TTL) {
          localStorage.removeItem(this.cacheKey(pageNum))
          return null
        }
        return entry
      } catch { return null }
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
  height: 44px;
  width: 22px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--muted-color);
  font-size: 14px;
  cursor: pointer;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}
.gt-strip-nav:hover:not(:disabled) {
  color: var(--text-color);
  border-color: var(--muted-color);
  background: var(--hover-bg);
}
.gt-strip-nav:disabled { opacity: 0.25; cursor: default; }

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
  border: 1.5px solid rgba(148, 163, 184, 0.42);
  background: rgba(148, 163, 184, 0.05);
  border-radius: 2px;
  cursor: pointer;
  pointer-events: all;
  overflow: hidden;
  display: flex;
  align-items: stretch;
  transition: border-color 0.1s, background 0.1s, box-shadow 0.1s;
}
.gt-ocr-box:hover {
  border-color: color-mix(in srgb, var(--primary-color) 68%, white 32%);
  background: color-mix(in srgb, var(--primary-color) 12%, transparent);
}
.gt-box-selected {
  border-color: var(--primary-color) !important;
  background: color-mix(in srgb, var(--primary-color) 16%, transparent) !important;
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--primary-color) 36%, transparent);
}
.gt-box-hidden { border-color: transparent !important; background: transparent !important; box-shadow: none !important; }

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

.gt-config-panel {
  padding: 10px 16px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.gt-config-panel-collapsed {
  gap: 0;
}

.gt-config-toggle {
  height: 28px;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--text-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.gt-config-toggle-icon {
  color: var(--muted-color);
  transition: transform 0.18s ease;
}

.gt-config-toggle-icon.is-open {
  transform: rotate(180deg);
}

.gt-config-panel button {
  -webkit-tap-highlight-color: transparent;
}

.gt-config-panel button:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

.gt-cfg-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.gt-cfg-key {
  font-size: 11px;
  font-weight: 500;
  color: var(--muted-color);
  letter-spacing: 0.04em;
  width: 32px;
  flex-shrink: 0;
}

/* Segmented control (OCR source) */
.gt-seg-ctrl {
  display: flex;
  background: var(--bg-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 2px;
  gap: 2px;
}

.gt-seg-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  height: 22px;
  padding: 0 10px;
  font-size: 12px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--muted-color);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.gt-seg-btn.active {
  background: var(--surface-color);
  color: var(--text-color);
  box-shadow: none;
}

.gt-seg-btn:not(.active):hover { color: var(--text-color); }

.gt-seg-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.gt-seg-dot.google { background: #4285f4; }
.gt-seg-dot.paddle { background: #2ba776; }
.gt-seg-dot.ocrspace { background: #f97316; }

/* Chip toggles (显示) */
.gt-chip-group {
  display: flex;
  gap: 6px;
}

.gt-chip {
  height: 24px;
  padding: 0 12px;
  font-size: 12px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: transparent;
  color: var(--muted-color);
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}

.gt-chip:hover { color: var(--text-color); border-color: var(--muted-color); }

.gt-chip.active {
  background: color-mix(in srgb, var(--primary-color) 15%, transparent);
  border-color: transparent;
  color: var(--primary-color);
}

/* Clear button */
.gt-clear-btn {
  margin-left: auto;
  height: 24px;
  padding: 0 10px;
  font-size: 12px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--muted-color);
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}

.gt-clear-btn:hover:not(:disabled) {
  background: rgba(248, 113, 113, 0.1);
  border-color: rgba(248, 113, 113, 0.35);
  color: rgb(248, 113, 113);
}

.gt-clear-btn:disabled { opacity: 0.3; cursor: default; }

.gt-switch-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.gt-switch {
  width: 38px;
  height: 22px;
  padding: 2px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: var(--surface-color);
  cursor: pointer;
  transition: background 0.18s ease, border-color 0.18s ease, opacity 0.18s ease;
}

.gt-switch.active {
  background: color-mix(in srgb, var(--primary-color) 78%, white 22%);
  border-color: var(--primary-color);
}

.gt-switch:disabled {
  opacity: 0.5;
  cursor: default;
}

.gt-switch-thumb {
  display: block;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.22);
  transform: translateX(0);
  transition: transform 0.18s ease;
}

.gt-switch.active .gt-switch-thumb {
  transform: translateX(16px);
}

.gt-switch-label {
  font-size: 12px;
  color: var(--text-color);
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
}

.gt-result-del {
  margin-left: auto;
  width: 18px;
  height: 18px;
  padding: 0;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--muted-color);
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  flex-shrink: 0;
}

.gt-result-del:hover {
  background: rgba(248, 113, 113, 0.15);
  color: rgb(248, 113, 113);
}

.gt-result-orig {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: color-mix(in srgb, var(--text-color) 65%, transparent);
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

/* ── Study mode ──────────────────────────────────────────────────────────────── */

.gt-pos-legend {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: 6px;
}

.gt-pos-dot {
  position: relative;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--dot-color);
  opacity: 0.75;
  cursor: default;
  flex-shrink: 0;
}

.gt-pos-dot::before {
  content: '';
  position: absolute;
  inset: -5px;
}

.gt-pos-dot::after {
  content: attr(data-pos);
  position: absolute;
  bottom: calc(100% + 7px);
  left: 50%;
  transform: translateX(-50%);
  background: var(--row-bg);
  border: 1px solid var(--border-color);
  color: var(--text-color);
  font-size: 10px;
  white-space: nowrap;
  padding: 2px 6px;
  border-radius: 4px;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.12s;
  z-index: 50;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
}

.gt-pos-dot:hover { opacity: 1; }
.gt-pos-dot:hover::after { opacity: 1; }

.gt-token-line {
  display: flex;
  flex-wrap: wrap;
  gap: 1px 2px;
  line-height: 2.6;
  padding: 0;
}

.gt-token ruby { ruby-align: center; }

.gt-token rt {
  font-size: 0.6em;
  opacity: 0.6;
  letter-spacing: 0;
  font-style: normal;
}

.gt-token {
  font-size: 12px;
  padding: 0 1px;
  border-radius: 2px;
  transition: background 0.1s;
  user-select: none;
}

.gt-token[style*="cursor: pointer"]:hover {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 2px;
}

/* ── Word card ───────────────────────────────────────────────────────────────── */

.gt-wc-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  z-index: 400;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.gt-wc-panel {
  background: var(--row-bg);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  width: 100%;
  max-width: 460px;
  max-height: 72vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.5);
  overflow: hidden;
}

.gt-wc-header {
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--border-color);
  position: relative;
  flex-shrink: 0;
}

.gt-wc-title-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
  padding-right: 28px;
}

.gt-wc-surface {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-color);
  line-height: 1.2;
}

.gt-wc-kana {
  font-size: 15px;
  color: var(--muted-color);
}

.gt-wc-base-form {
  font-size: 12px;
  color: var(--muted-color);
}

.gt-wc-meta-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.gt-wc-pos-badge {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid;
}

.gt-wc-conj {
  font-size: 11px;
  color: var(--muted-color);
  background: var(--surface-color);
  padding: 2px 7px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
}

.gt-wc-close {
  position: absolute;
  top: 14px;
  right: 14px;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--muted-color);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, color 0.15s;
}
.gt-wc-close:hover { background: var(--hover-bg); color: var(--text-color); }

.gt-wc-body {
  overflow-y: auto;
  flex: 1;
  scrollbar-width: thin;
  scrollbar-color: var(--scrollbar-thumb) transparent;
}

.gt-wc-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px;
  color: var(--muted-color);
  font-size: 13px;
}

.gt-wc-err { color: #f87171; }

.gt-wc-entries {
  padding: 8px 0;
}

.gt-wc-entry {
  padding: 12px 20px;
  border-bottom: 1px solid var(--border-color);
}
.gt-wc-entry:last-child { border-bottom: none; }

.gt-wc-entry-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.gt-wc-entry-word {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-color);
}

.gt-wc-entry-reading {
  font-size: 13px;
  color: var(--muted-color);
}

.gt-wc-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
}

.gt-wc-common {
  background: rgba(74, 222, 128, 0.12);
  color: #4ade80;
  border: 1px solid rgba(74, 222, 128, 0.3);
}

.gt-wc-jlpt {
  background: rgba(167, 139, 250, 0.12);
  color: #a78bfa;
  border: 1px solid rgba(167, 139, 250, 0.3);
}

.gt-wc-senses {
  margin: 0;
  padding: 0 0 0 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.gt-wc-sense {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-color);
}

.gt-wc-sense-pos {
  display: inline-block;
  font-size: 10px;
  font-weight: 500;
  color: var(--primary-color);
  background: color-mix(in srgb, var(--primary-color) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--primary-color) 25%, transparent);
  border-radius: 3px;
  padding: 0 5px;
  margin-right: 5px;
  vertical-align: middle;
}

.gt-wc-sense-info {
  font-size: 11px;
  color: var(--muted-color);
  margin-left: 4px;
}

/* Word card transition */
.gt-wc-enter-active { transition: opacity 0.15s, transform 0.15s; }
.gt-wc-leave-active { transition: opacity 0.12s, transform 0.12s; }
.gt-wc-enter-from, .gt-wc-leave-to { opacity: 0; transform: scale(0.96); }

@media (max-width: 900px) {
  .gt-sidebar { width: 45%; }
}

/* 宽屏没有抽屉，抽屉把手只在移动端出现 */
.gt-sheet-handle { display: none; }

/* 移动端：图片区吃掉除头栏外的整屏，结果列表收成底部抽屉。
   此前是 52% 固定分屏 —— 竖版漫画页在半屏高的框里按高度收缩，
   两侧留白、字小到读不动，而下半屏大多时候是空的「点击 OCR 开始识别」。
   现在默认只留一条把手（56px），需要对照译文时再把抽屉拉起来。 */
@media (max-width: 767px) {
  .gt-workbench {
    height: 100dvh;
    overflow: hidden;
    --gt-sheet-peek: 64px;
    --gt-sheet-safe: calc(var(--gt-sheet-peek) + env(safe-area-inset-bottom, 0px));
  }

  .gt-body {
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
    position: relative;
  }

  .gt-image-panel {
    flex: 1 1 auto;
    min-height: 0;
    overflow: hidden;
    /* 给抽屉把手让出位置，图片因此永远不会被压在把手底下 */
    padding-bottom: var(--gt-sheet-safe);
  }

  .gt-page-img {
    max-width: 100%;
    max-height: 100%;
    width: auto;
    height: auto;
    object-fit: contain;
    box-shadow: none;
  }

  /* ── 底部抽屉 ── */
  .gt-sidebar {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    width: 100%;
    height: var(--gt-sheet-h, var(--gt-sheet-peek));
    max-height: 88dvh;
    z-index: 6;
    border-left: none;
    border-top: 1px solid var(--border-color);
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
    box-shadow: 0 -8px 28px rgba(0, 0, 0, 0.32);
    padding-bottom: env(safe-area-inset-bottom, 0px);
    overflow-y: auto;
    overscroll-behavior: contain;
    transition: height var(--dur-base) var(--ease-out);
  }

  .gt-sidebar.is-peek { overflow: hidden; }
  .gt-sidebar.is-dragging { transition: none; }

  .gt-sheet-handle {
    display: block;
    box-sizing: border-box;
    height: var(--gt-sheet-peek);
    position: sticky;
    top: 0;
    z-index: 4;
    background: var(--row-bg);
    border-bottom: 1px solid var(--border-color);
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
    padding: 5px 8px 0;
    cursor: grab;
    touch-action: none;
    user-select: none;
    -webkit-user-select: none;
  }

  .gt-sidebar.is-dragging .gt-sheet-handle { cursor: grabbing; }

  .gt-sheet-grip {
    display: block;
    width: 36px;
    height: 4px;
    margin: 0 auto 6px;
    border-radius: 2px;
    background: var(--border-color);
  }

  .gt-sheet-row {
    display: grid;
    grid-template-columns: var(--tap-target) 1fr var(--tap-target);
    align-items: center;
  }

  .gt-sheet-label {
    text-align: center;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
  }

  .gt-sheet-count {
    display: inline-block;
    margin-left: 6px;
    padding: 0 6px;
    border-radius: 999px;
    background: var(--primary-soft-bg);
    color: var(--primary-on-soft);
    font-size: 11px;
    line-height: 18px;
  }

  .gt-sheet-nav {
    min-width: var(--tap-target);
    min-height: var(--tap-target);
    padding: 0;
    border: none;
    background: transparent;
    color: var(--text-color);
    font-size: 20px;
    line-height: 1;
    cursor: pointer;
  }

  .gt-sheet-nav:disabled { color: var(--faint-color); cursor: default; }

  .gt-header { min-height: var(--tap-target); }
  .gt-back-btn { min-width: var(--tap-target); min-height: var(--tap-target); }
}

</style>
