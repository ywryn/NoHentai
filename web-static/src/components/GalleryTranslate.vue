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
          {{ ocrProcessing ? '识别中 1/2' : translating ? '翻译中 2/2' : '翻译' }}
        </button>
      </div>
      <!-- 两步流水线的进度条：替代原来一条接一条的 toast -->
      <div v-if="ocrProcessing || translating" class="gt-progress" :class="{ 'is-step2': translating }" aria-hidden="true"></div>
    </header>

    <!-- Main body -->
    <div class="gt-body">
      <!-- Image panel -->
      <div
        class="gt-image-panel"
        ref="containerRef"
        :class="{ 'is-zoomed': zoom.scale > 1 }"
        @pointerdown="onStagePointerDown"
        @wheel="onStageWheel"
      >
        <div v-if="imageLoading" class="gt-image-placeholder">
          <div class="gt-spinner"></div>
          <span>加载图片...</span>
        </div>
        <div v-else-if="imageError" class="gt-image-placeholder gt-image-error">{{ imageError }}</div>
        <!-- 缩放层：图片与 OCR 框同在一个 transform 下，捏合 / 双击放大时框随图一起走 -->
        <div v-else-if="imageUrl" class="gt-stage" :class="{ 'is-sliding': pageSliding }" :style="stageStyle">
          <img
            ref="imgRef"
            :src="imageUrl"
            class="gt-page-img"
            alt="manga page"
            crossorigin="anonymous"
            draggable="false"
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
                'gt-box-has-badge': showTranslation && result.translation && unfitBoxes[result._id],
              }"
              :style="getBoxStyle(result, i)"
              :title="result.translation || result.text"
              @click="onBoxClick(i)"
            >
              <!-- 放得下就直接叠译文（高瘦框走竖排），放不下退化成序号徽标，避免 3px 的字糊成黑块 -->
              <span
                v-if="showTranslation && result.translation && !unfitBoxes[result._id]"
                class="gt-box-trans-text"
                :class="{ 'gt-box-vertical': isVerticalBox(result), 'gt-box-sfx': result.kind === 'sfx' }"
                :ref="el => setTransTextRef(el, result._id)"
              >{{ result.translation }}</span>
              <span
                v-else-if="showTranslation && result.translation"
                class="gt-box-badge"
              >{{ i + 1 }}</span>
            </div>
          </div>
        </div>
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
          <!-- 术语表：与「显示」行同款 chip，展开后编辑区独占一行 -->
          <div class="gt-cfg-row">
            <span class="gt-cfg-key">术语</span>
            <div class="gt-chip-group">
              <button
                class="gt-chip gt-chip-count"
                :class="{ active: glossaryOpen }"
                type="button"
                :aria-expanded="glossaryOpen"
                @click="glossaryOpen = !glossaryOpen"
              >
                术语表<span class="gt-chip-badge">{{ Object.keys(glossary).length }}</span>
              </button>
            </div>
          </div>
          <div v-if="glossaryOpen" class="gt-glossary">
            <textarea
              v-model="glossaryText"
              class="gt-edit-input gt-glossary-input"
              rows="4"
              placeholder="每行一条：原文=译文&#10;例：お姉ちゃん=姐姐"
              spellcheck="false"
              @blur="commitGlossary"
            ></textarea>
            <span class="gt-glossary-hint">按画廊保存，随每次翻译一起提交给模型</span>
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

        <!-- 移动端把手上已有标题与条数，这一行只在有「补译」按钮时才显示 -->
        <div class="gt-sidebar-hdr" :class="{ 'gt-sidebar-hdr-plain': !(missingCount && missingCount < ocrResults.length) }">
          <span class="gt-sidebar-title">识别结果</span>
          <span v-if="ocrResults.length" class="gt-count-badge">{{ ocrResults.length }}</span>
          <span v-if="ocrResults.some(r => r.translation) && !missingCount" class="gt-translated-badge">已翻译</span>
          <button
            v-else-if="missingCount && missingCount < ocrResults.length"
            class="gt-chip gt-retranslate"
            type="button"
            :disabled="translating"
            @click="retranslateMissing"
          >{{ translating ? '补译中…' : `补译 ${missingCount} 条` }}</button>
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
            @click="onResultClick(i)"
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
            <!-- 译文：点 ✎ 内联编辑；模型漏译时明确标出而不是悄悄回填原文 -->
            <div v-if="editingIdx === i" class="gt-result-edit" @click.stop>
              <textarea
                ref="editInput"
                v-model="editingText"
                class="gt-edit-input"
                rows="2"
                @keydown.enter.exact.prevent="commitEdit"
                @keydown.esc.prevent="cancelEdit"
              ></textarea>
              <div class="gt-edit-actions">
                <button class="gt-chip" type="button" @click="cancelEdit">取消</button>
                <button class="gt-chip active" type="button" @click="commitEdit">保存</button>
              </div>
            </div>
            <template v-else>
              <div v-if="result.translation" class="gt-result-trans-row">
                <p class="gt-result-trans">
                  <span v-if="result.kind && result.kind !== 'dialogue'" class="gt-kind-tag">{{ kindLabel(result.kind) }}</span>{{ result.translation }}
                </p>
                <button class="gt-result-edit-btn" type="button" title="编辑译文" aria-label="编辑译文" @click.stop="startEdit(i)">✎</button>
              </div>
              <p v-if="result.translation && result.alt" class="gt-result-alt">备选：{{ result.alt }}</p>
              <p v-else-if="!result.translation && ocrResults.some(r => r.translation)" class="gt-result-missing">
                未翻译
                <button class="gt-link-btn" type="button" @click.stop="startEdit(i)">手动填写</button>
              </p>
            </template>
          </div>
        </div>
      </div>
    </div>

    <!-- 移动端：点框后浮在抽屉把手上方的气泡卡，不用拉抽屉就能读原文 + 译文 -->
    <Transition name="gt-bc">
      <div v-if="bubbleCard != null && ocrResults[bubbleCard]" class="gt-bubble-card" role="dialog" aria-label="对白详情">
        <div class="gt-bc-head">
          <button class="gt-bc-nav" type="button" :disabled="bubbleCard <= 0" aria-label="上一条" @click="stepBubble(-1)">‹</button>
          <span class="gt-bc-pos">{{ bubbleCard + 1 }} / {{ ocrResults.length }}</span>
          <button class="gt-bc-nav" type="button" :disabled="bubbleCard >= ocrResults.length - 1" aria-label="下一条" @click="stepBubble(1)">›</button>
          <button class="gt-bc-close" type="button" aria-label="关闭" @click="closeBubble">×</button>
        </div>
        <p class="gt-bc-orig">{{ ocrResults[bubbleCard].text }}</p>
        <p v-if="ocrResults[bubbleCard].translation" class="gt-bc-trans">{{ ocrResults[bubbleCard].translation }}</p>
        <p v-else class="gt-bc-trans gt-bc-pending">尚未翻译</p>
        <p v-if="ocrResults[bubbleCard].alt" class="gt-bc-alt">备选：{{ ocrResults[bubbleCard].alt }}</p>
      </div>
    </Transition>

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
import { loadGalleries } from '@/composables/useGalleryData'

const API_BASE = import.meta.env.VITE_API_BASE || 'https://no-hentai.vercel.app'
const SESSION_KEY = 'trans_password'
const TRANS_CACHE_TTL = 3 * 24 * 60 * 60 * 1000
/* 每画廊术语表：{ 原文: 译文 }，随翻译请求一起送给模型 */
const GLOSSARY_KEY_PREFIX = 'trans_glossary_'
const KIND_LABEL = { dialogue: '对白', narration: '旁白', sfx: '拟声' }

/* 移动端底部抽屉的三个档位。peek 与 CSS 里的 --gt-sheet-peek 保持一致 */
const SHEET_PEEK_PX = 64
const SHEET_SNAPS = { peek: `${SHEET_PEEK_PX}px`, half: '50dvh', full: '88dvh' }
const SHEET_ORDER = ['peek', 'half', 'full']

/* 译文叠加层：高宽比超过此值的框按竖排渲染；字号地板（CSS px）以下不再硬塞，改显示序号徽标 */
const VERTICAL_ASPECT = 1.6
const MIN_OVERLAY_FONT_PX = 11
const MAX_BOX_EXPAND_STEPS = 6

/* 图片缩放层 */
const ZOOM_MAX = 5
const ZOOM_DBLTAP = 2.5
const SWIPE_MIN_X = 60
const SWIPE_MAX_Y = 50
/* 边缘点击区：与阅读器 BookView 一致的 30 / 40 / 30 */
const EDGE_ZONE = 0.3
/* 翻页滑动动效时长（ms），与 --dur-base 对齐 */
const SLIDE_MS = 200

/** 阅读方向沿用阅读器设置（reader-settings.bookDirection），默认 RTL；两个页面的翻页手势因此一致 */
function readBookDirection() {
  try {
    const s = JSON.parse(localStorage.getItem('reader-settings') || '{}')
    return s.bookDirection === 'ltr' ? 'ltr' : 'rtl'
  } catch { return 'rtl' }
}

const prefersReducedMotion = () =>
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

const isMobile = () => window.innerWidth <= 767

/* 送去 OCR 的图片：长边缩到此值、JPEG 质量 */
const OCR_MAX_EDGE = 1800
const OCR_JPEG_QUALITY = 0.88

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
  /** 两个框边缘之间的空隙（相交为 0）。此前用中心距，对高瘦的竖排列几乎永远超阈值 */
  gapTo(r) {
    const dx = Math.max(0, r.x0 - this.x1, this.x0 - r.x1)
    const dy = Math.max(0, r.y0 - this.y1, this.y0 - r.y1)
    return Math.hypot(dx, dy)
  }
  /** 四周各外扩 px 像素（绝对值，不随框大小变化） */
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

/** 单个框的排版方向：日漫对白绝大多数是高瘦的竖排框 */
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

/**
 * 把 OCR 的碎片框合并成对白块，并整理成漫画阅读顺序。
 * 阈值全部按「单行字号」(所有框短边的中位数 m) 折算，因此 1000px 与 2400px 的扫图表现一致；
 * 此前 maxDistance 写死 10/40 像素，对高清扫图几乎永远合不上，对小图又过度合并。
 * `blockLevel` (Google Vision / OCR.Space 已按段落分块) 时放宽阈值。
 */
function mergeOcrResults(items, { blockLevel = false, confidenceThreshold = 0.7 } = {}) {
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
      // 组内方向：竖排按 x 从右到左拼行，横排（旁白 / 拟声 / 标题）按 y 从上到下
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
        // 日文行间不加空格：空格会让 LLM 与 kuromoji 都在错误位置断词
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
      /* 手机抽屉里设置默认收起，拉开时先看到的是识别结果 */
      configPanelExpanded: !isMobile(),
      /* 图片缩放 / 平移（transform-origin 0 0） */
      zoom: { scale: 1, tx: 0, ty: 0 },
      /* 翻页横向位移：拖动中跟手，松手后动画到 ±宽度（滑出）或 0（回弹 / 滑入） */
      pageOffset: 0,
      pageSliding: false,
      bookDirection: readBookDirection(),
      /* 移动端点框弹出的气泡卡：当前条目下标 */
      bubbleCard: null,
      /* 移动端底部抽屉：peek 只留把手（图片占满整屏）→ half → full */
      sheetState: 'peek',
      sheetDragging: false,
      sheetDragH: null,
      selectedBoxIdx: null,
      ocrSource: 'google',
      lastOcrSource: null,
      expandedBboxes: {},
      /* 字号压到地板仍放不下的框 → 只显示序号徽标 */
      unfitBoxes: {},
      renderTick: 0,
      transTextRefs: {},

      // Toasts
      toasts: [],
      toastCounter: 0,

      // Thumbnail lazy load
      loadedThumbPages: {},

      // 作品元数据（标题 / 标签），作为翻译上下文
      galleryMeta: null,
      // 术语表
      glossary: {},
      glossaryText: '',
      glossaryOpen: false,
      // 译文内联编辑
      editingIdx: null,
      editingText: '',

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
    missingCount() {
      return this.ocrResults.filter(r => !r.translation).length
    },
    /** 抽屉高度：拖拽中用像素跟手，松手后落到档位 */
    sheetHeight() {
      if (this.sheetDragH != null) return `${this.sheetDragH}px`
      return SHEET_SNAPS[this.sheetState] || SHEET_SNAPS.peek
    },
    stageStyle() {
      const { scale, tx, ty } = this.zoom
      const ox = tx + this.pageOffset
      if (scale === 1 && !ox && !ty) return null
      return { transform: `translate(${ox}px, ${ty}px) scale(${scale})` }
    },
  },

  watch: {
    renderTick() {
      if (this.showTranslation && this.ocrResults.some(r => r.translation)) {
        this.expandedBboxes = {}
        this.unfitBoxes = {}
        this.$nextTick(() => this.applyTextFit())
      }
    },
    showTranslation(val) {
      this.expandedBboxes = {}
      this.unfitBoxes = {}
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

    this.loadGlossary()
    loadGalleries().then(list => {
      this.galleryMeta = list.find(g => String(g.gid) === String(this.gid)) || null
    })

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
    window.removeEventListener('pointermove', this.onStagePointerMove)
    window.removeEventListener('pointerup', this.onStagePointerUp)
    window.removeEventListener('pointercancel', this.onStagePointerUp)
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

    /** 点击图片上的 OCR 框：桌面端高亮列表条目；移动端弹气泡卡（抽屉收到 peek 免得盖住卡） */
    onBoxClick(i) {
      if (this._suppressClickUntil && Date.now() < this._suppressClickUntil) return
      const next = this.selectedBoxIdx === i ? null : i
      this.selectedBoxIdx = next
      if (!isMobile()) return
      if (next == null) { this.bubbleCard = null; return }
      this.bubbleCard = next
      if (this.sheetState !== 'peek') this.setSheet('peek')
    },

    /** 列表里点条目：移动端若抽屉全开则降到半开，让高亮的框露出来 */
    onResultClick(i) {
      this.selectedBoxIdx = this.selectedBoxIdx === i ? null : i
      if (!isMobile()) return
      if (this.selectedBoxIdx != null && this.sheetState === 'full') this.setSheet('half')
    },

    stepBubble(delta) {
      if (this.bubbleCard == null) return
      const next = this.bubbleCard + delta
      if (next < 0 || next >= this.ocrResults.length) return
      this.bubbleCard = next
      this.selectedBoxIdx = next
    },

    closeBubble() {
      this.bubbleCard = null
      this.selectedBoxIdx = null
    },

    // ── 图片缩放 / 平移 / 滑动翻页 ────────────────────────────────────────────

    resetZoom() {
      this.zoom = { scale: 1, tx: 0, ty: 0 }
    },

    /** 把平移量限制在「图片至少有一半留在视口内」的范围 */
    clampZoom(z) {
      const cont = this.$refs.containerRef
      if (!cont) return z
      const w = cont.clientWidth, h = cont.clientHeight
      const minTx = -w * (z.scale - 0.5), maxTx = w * 0.5
      const minTy = -h * (z.scale - 0.5), maxTy = h * 0.5
      return {
        scale: z.scale,
        tx: Math.min(maxTx, Math.max(minTx, z.tx)),
        ty: Math.min(maxTy, Math.max(minTy, z.ty)),
      }
    },

    /** 以视口内一点 (px, py) 为锚缩放到 scale：锚点下的图片内容保持不动 */
    zoomAt(px, py, scale) {
      const s = Math.min(ZOOM_MAX, Math.max(1, scale))
      const { scale: s0, tx, ty } = this.zoom
      const nx = px - (px - tx) * (s / s0)
      const ny = py - (py - ty) * (s / s0)
      this.zoom = s === 1 ? { scale: 1, tx: 0, ty: 0 } : this.clampZoom({ scale: s, tx: nx, ty: ny })
    },

    /** 视口坐标 → 相对图片区左上角 */
    stagePoint(e) {
      const r = this.$refs.containerRef.getBoundingClientRect()
      return { x: e.clientX - r.left, y: e.clientY - r.top }
    },

    onStageWheel(e) {
      if (!(e.ctrlKey || e.metaKey)) return
      e.preventDefault()
      const p = this.stagePoint(e)
      this.zoomAt(p.x, p.y, this.zoom.scale * (e.deltaY < 0 ? 1.15 : 1 / 1.15))
    },

    onStagePointerDown(e) {
      if (e.pointerType === 'mouse' && e.button !== 0) return
      if (!this.imageUrl) return
      if (!this._ptrs) this._ptrs = new Map()
      const ptrs = this._ptrs
      ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY })

      if (ptrs.size === 1) {
        this._gesture = {
          kind: 'single', startX: e.clientX, startY: e.clientY, t: Date.now(),
          tx: this.zoom.tx, ty: this.zoom.ty, moved: 0,
        }
      } else if (ptrs.size === 2) {
        const [a, b] = [...ptrs.values()]
        const mid = this.stagePoint({ clientX: (a.x + b.x) / 2, clientY: (a.y + b.y) / 2 })
        this._gesture = {
          kind: 'pinch', dist: Math.hypot(a.x - b.x, a.y - b.y), scale: this.zoom.scale,
          mid, tx: this.zoom.tx, ty: this.zoom.ty, moved: 99,
        }
      }

      if (ptrs.size === 1) {
        window.addEventListener('pointermove', this.onStagePointerMove)
        window.addEventListener('pointerup', this.onStagePointerUp)
        window.addEventListener('pointercancel', this.onStagePointerUp)
      }
    },

    onStagePointerMove(e) {
      const ptrs = this._ptrs
      const g = this._gesture
      if (!ptrs?.has(e.pointerId) || !g) return
      ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY })

      if (g.kind === 'pinch' && ptrs.size >= 2) {
        const [a, b] = [...ptrs.values()]
        const dist = Math.hypot(a.x - b.x, a.y - b.y)
        const s = Math.min(ZOOM_MAX, Math.max(1, g.scale * dist / g.dist))
        const mid = this.stagePoint({ clientX: (a.x + b.x) / 2, clientY: (a.y + b.y) / 2 })
        // 起始中点下的内容跟着当前中点走
        const nx = mid.x - (g.mid.x - g.tx) * (s / g.scale)
        const ny = mid.y - (g.mid.y - g.ty) * (s / g.scale)
        this.zoom = s === 1 ? { scale: 1, tx: 0, ty: 0 } : this.clampZoom({ scale: s, tx: nx, ty: ny })
        return
      }

      if (g.kind === 'single') {
        const dx = e.clientX - g.startX, dy = e.clientY - g.startY
        g.moved = Math.max(g.moved, Math.abs(dx), Math.abs(dy))
        if (this.zoom.scale > 1 && g.moved > 4) {
          this.zoom = this.clampZoom({ scale: this.zoom.scale, tx: g.tx + dx, ty: g.ty + dy })
          return
        }
        // 未缩放：横向拖动时页面跟手；一旦判定为横向就锁定，避免和抽屉 / 纵向手势打架
        if (this.zoom.scale === 1 && !this.pageSliding) {
          if (!g.swiping && g.moved > 8 && Math.abs(dx) > Math.abs(dy) * 1.2) g.swiping = true
          if (g.swiping) {
            // 到头了给阻尼，提示没有更多页
            const canGo = this.canTurnBySwipe(dx)
            this.pageOffset = canGo ? dx : dx * 0.3
          }
        }
      }
    },

    /** 横向位移 dx 对应的翻页方向是否还有页可翻 */
    canTurnBySwipe(dx) {
      const delta = this.swipeDelta(dx)
      const target = this.currentPage + delta
      return target >= 1 && target <= this.totalPages
    },

    /**
     * 把「手指向左 / 向右」换算成页码增量，规则与阅读器 BookView 完全一致：
     * 向左滑 ≡ 点右侧区，RTL 下是上一页；向右滑 ≡ 点左侧区，RTL 下是下一页。
     */
    swipeDelta(dx) {
      const rtl = this.bookDirection === 'rtl'
      const tapRight = dx < 0
      return (rtl ? !tapRight : tapRight) ? 1 : -1
    },

    onStagePointerUp(e) {
      const ptrs = this._ptrs
      const g = this._gesture
      if (!ptrs) return
      ptrs.delete(e.pointerId)
      if (ptrs.size > 0) {
        // 捏合中松开一指：剩下那指从当前位置开始平移，不要跳
        const [rest] = [...ptrs.values()]
        this._gesture = { kind: 'single', startX: rest.x, startY: rest.y, t: Date.now(), tx: this.zoom.tx, ty: this.zoom.ty, moved: 99 }
        return
      }
      window.removeEventListener('pointermove', this.onStagePointerMove)
      window.removeEventListener('pointerup', this.onStagePointerUp)
      window.removeEventListener('pointercancel', this.onStagePointerUp)
      this._gesture = null
      if (!g || g.kind !== 'single') return

      const dx = e.clientX - g.startX, dy = e.clientY - g.startY
      const dt = Date.now() - g.t
      // 拖动过就不算点击，免得平移 / 滑动结束时误触框
      if (g.moved >= 6) this._suppressClickUntil = Date.now() + 350

      // 未缩放时的横向滑动：过阈值就顺着手势滑出翻页，否则回弹
      if (g.swiping) {
        const w = this.$refs.containerRef?.clientWidth || window.innerWidth
        const fast = Math.abs(dx) >= SWIPE_MIN_X && Math.abs(dy) <= SWIPE_MAX_Y && dt < 600
        const far = Math.abs(dx) >= w * 0.3
        if ((fast || far) && this.canTurnBySwipe(dx)) {
          this.turnPage(this.swipeDelta(dx), dx < 0 ? 'left' : 'right')
        } else {
          this.animateOffset(0)
        }
        return
      }

      if (g.moved < 6) {
        // 左右 30% 边缘区：单击直接翻页（与阅读器一致），不参与双击缩放；框上的点击交给框自己
        if (this.zoom.scale === 1 && !e.target.closest?.('.gt-ocr-box') && this.bubbleCard == null) {
          const p = this.stagePoint(e)
          const w = this.$refs.containerRef?.clientWidth || 1
          if (p.x < w * EDGE_ZONE) { this.onEdgeTap('left'); return }
          if (p.x > w * (1 - EDGE_ZONE)) { this.onEdgeTap('right'); return }
        }

        // 中间区双击 / 双击轻点：在点击处放大，已放大则复位
        const now = Date.now()
        const last = this._lastTap
        if (last && now - last.t < 300 && Math.hypot(e.clientX - last.x, e.clientY - last.y) < 30) {
          this._lastTap = null
          this._suppressClickUntil = now + 350
          const p = this.stagePoint(e)
          this.zoomAt(p.x, p.y, this.zoom.scale > 1 ? 1 : ZOOM_DBLTAP)
        } else {
          this._lastTap = { t: now, x: e.clientX, y: e.clientY }
        }
      }
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
      this.resetZoom()
      this.bubbleCard = null
      // 不是由 turnPage 发起的切页（缩略图 / 预取等待）就不带过场
      if (this._enterFrom == null) this.finishSlide()
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
        this.finishSlide()
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
        // 这一页正在后台预取的话，等它写完缓存再读
        if (this._prefetch?.[pageNum]) {
          this.imageLoading = false
          this.ocrProcessing = true
          try { await this._prefetch[pageNum] } finally { this.ocrProcessing = false }
          if (this.currentPage !== pageNum) return
        }
        const cached = this.loadPageCache(pageNum)
        if (cached) {
          this.ocrResults = cached.ocrResults
          this.lastOcrSource = cached.lastOcrSource
          this.expandedBboxes = {}
          this.unfitBoxes = {}
          this.$nextTick(() => this.applyTextFit())
          this.maybePrefetchNext()
        } else if (this.autoTranslate) {
          await this.$nextTick()
          await this.performOcrAndTranslate()
        }
      } catch (e) {
        this.imageError = `图片加载失败: ${e.message}`
        this.finishSlide()
      } finally {
        this.imageLoading = false
      }
    },

    /** 结束 / 取消翻页过场，位移归零 */
    finishSlide() {
      this._enterFrom = null
      this.pageOffset = 0
      this.pageSliding = false
    },

    /* ‹ › 按钮与把手：按页码顺序翻，滑动方向按阅读方向推算，让画面运动方向与手势一致 */
    prevPage() {
      if (this.currentPage > 1) this.turnPage(-1)
    },

    nextPage() {
      if (this.currentPage < this.totalPages) this.turnPage(1)
    },

    /** 点击左 / 右边缘区：RTL 左侧是下一页，与阅读器 onClickLeft/Right 一致 */
    onEdgeTap(side) {
      const rtl = this.bookDirection === 'rtl'
      const delta = (side === 'left') === rtl ? 1 : -1
      const target = this.currentPage + delta
      if (target < 1 || target > this.totalPages) return
      this._suppressClickUntil = Date.now() + 350
      // 点左侧 ≈ 向右滑（把左边的页拉进来），画面向右走
      this.turnPage(delta, side === 'left' ? 'right' : 'left')
    },

    /**
     * 带过场的翻页：当前页向 outDir 滑出 → 切页 → 新页从另一侧滑入。
     * outDir 不传时按阅读方向推算；reduced-motion 或页面不可见时直接切换。
     */
    turnPage(delta, outDir) {
      const target = this.currentPage + delta
      if (target < 1 || target > this.totalPages || this.pageSliding) return
      if (!outDir) {
        const rtl = this.bookDirection === 'rtl'
        // RTL 里下一页在左边：当前页往右退开；LTR 相反
        outDir = (delta > 0) === rtl ? 'right' : 'left'
      }
      if (prefersReducedMotion() || !this.imageUrl) {
        this.pageOffset = 0
        this.goToPage(target)
        return
      }
      const w = this.$refs.containerRef?.clientWidth || window.innerWidth
      const out = outDir === 'left' ? -w : w
      this.pageSliding = true
      this.animateOffset(out, () => {
        // 新页从对侧进场：先无动画放到对侧，图片加载完再滑到 0
        this._enterFrom = -out
        this.pageOffset = -out
        this.goToPage(target)
      })
    },

    /** 把 pageOffset 动画到 target，完成后回调（transition 由 .is-sliding 提供） */
    animateOffset(target, done) {
      this.pageSliding = true
      requestAnimationFrame(() => {
        this.pageOffset = target
        setTimeout(() => {
          if (!done) this.pageSliding = false
          done?.()
        }, SLIDE_MS + 20)
      })
    },

    onImageLoad() {
      this.renderTick++
      if (this._enterFrom != null) {
        this._enterFrom = null
        this.animateOffset(0)
      }
    },

    // ── OCR ───────────────────────────────────────────────────────────────────

    async performOcrAndTranslate() {
      await this.performOcr()
      if (this.ocrResults.length) await this.performTranslate()
      this.maybePrefetchNext()
    },

    /** 等 <img> 解码完成（autoTranslate 时 OCR 往往先于图片加载完被触发） */
    async ensureImageDecoded(img) {
      if (!img) throw new Error('图片尚未就绪')
      if (img.complete && img.naturalWidth) return img
      await img.decode()
      return img
    },

    /**
     * 把图片缩到长边 ≤ OCR_MAX_EDGE 再转 JPEG base64。
     * 原来是把原图整个 fetch 回来逐字节拼 base64：3MB 扫图在手机上要几百毫秒，
     * base64 后再涨 1/3 就撞上 Vercel 4.5MB 请求体上限。缩图后通常只有 300–500KB，
     * 且 OCR 的 bbox 乘回 scale 即可还原到原图坐标。代理返回了 ACAO: * ，canvas 不会被污染；
     * 万一被污染（toDataURL 抛 SecurityError）就退回旧的 fetch 路径。
     */
    async getOcrPayload(img) {
      try {
        const longEdge = Math.max(img.naturalWidth, img.naturalHeight)
        const ratio = Math.min(1, OCR_MAX_EDGE / longEdge)
        const w = Math.max(1, Math.round(img.naturalWidth * ratio))
        const h = Math.max(1, Math.round(img.naturalHeight * ratio))
        const canvas = document.createElement('canvas')
        canvas.width = w
        canvas.height = h
        canvas.getContext('2d').drawImage(img, 0, 0, w, h)
        const dataUrl = canvas.toDataURL('image/jpeg', OCR_JPEG_QUALITY)
        return { b64: dataUrl.slice(dataUrl.indexOf(',') + 1), scale: 1 / ratio }
      } catch {
        return { b64: await this.fetchImageBase64(img.src), scale: 1 }
      }
    },

    async fetchImageBase64(url) {
      const res = await fetch(url)
      if (!res.ok) throw new Error(`Failed to fetch image: HTTP ${res.status}`)
      const bytes = new Uint8Array(await res.arrayBuffer())
      const chunks = []
      for (let i = 0; i < bytes.length; i += 0x8000) {
        chunks.push(String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000)))
      }
      return btoa(chunks.join(''))
    },

    async postTrans(endpoint, body) {
      const res = await fetch(`${API_BASE}/api/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: sessionStorage.getItem(SESSION_KEY), ...body }),
      })
      const data = await res.json().catch(() => ({}))
      if (res.status === 401) {
        const err = new Error('密码已失效')
        err.auth = true
        throw err
      }
      if (data.error) throw new Error(data.error)
      return data
    },

    /** 对一张已解码的图片跑 OCR → 合并，返回带 _id 的结果数组与来源。纯函数式，不碰 UI 状态 */
    async ocrImage(img, ocrSource) {
      const { b64, scale } = await this.getOcrPayload(img)
      const data = await this.postTrans('trans-ocr', { imageBase64: b64, ocrSource })
      const raw = scale === 1 ? data.results : data.results.map(r => ({
        ...r,
        bbox: r.bbox.map(v => v * scale),
        polygon: r.polygon ? r.polygon.map(([x, y]) => [x * scale, y * scale]) : null,
      }))
      const blockLevel = data.source === 'vision' || data.source === 'ocrspace'
      const stamp = Date.now()
      const results = mergeOcrResults(raw, { blockLevel }).map((r, i) => ({ ...r, _id: `${stamp}_${i}` }))
      return { results, source: data.source }
    },

    /**
     * 翻译一组文本，返回与输入等长的数组，每项 { t, kind, alt } 或 null（模型漏译）。
     * 此前漏译会被回填成原文，界面上看起来像「翻译了但还是日文」。
     */
    async translateTexts(texts, pageNum) {
      const data = await this.postTrans('trans-translate', {
        texts,
        ...this.buildTranslateContext(pageNum),
      })
      return texts.map((_, i) => {
        const item = data.translations?.[i]
        if (!item) return null
        return typeof item === 'string' ? { t: item, kind: 'dialogue', alt: null } : item
      })
    },

    /** 把译文项写回结果：translation 字符串 + kind + alt */
    applyTranslation(result, item) {
      return {
        ...result,
        translation: item?.t ?? null,
        kind: item?.kind ?? result.kind ?? null,
        alt: item?.alt ?? null,
      }
    },

    /**
     * 翻译上下文：作品标题 / 标签让模型把握题材与口吻，上一页的对照保证人名称谓一致，
     * 术语表由用户在设置里维护。
     */
    buildTranslateContext(pageNum) {
      const ctx = {}
      if (this.galleryMeta) {
        ctx.context = {
          title: this.galleryMeta.title_jpn || this.galleryMeta.title,
          tags: (this.galleryMeta.tags || []).filter(t => !/^language:/.test(t)),
        }
      }
      const prev = pageNum > 1 ? this.loadPageCache(pageNum - 1) : null
      if (prev?.ocrResults?.length) {
        ctx.previous = prev.ocrResults
          .filter(r => r.translation)
          .slice(-12)
          .map(r => [r.text, r.translation])
      }
      if (Object.keys(this.glossary).length) ctx.glossary = this.glossary
      return ctx
    },

    // ── 术语表 ────────────────────────────────────────────────────────────────

    glossaryKey() {
      return `${GLOSSARY_KEY_PREFIX}${this.gid}`
    },

    loadGlossary() {
      try {
        const raw = localStorage.getItem(this.glossaryKey())
        this.glossary = raw ? JSON.parse(raw) : {}
      } catch { this.glossary = {} }
      this.glossaryText = Object.entries(this.glossary).map(([k, v]) => `${k}=${v}`).join('\n')
    },

    /** 文本框格式：每行「原文=译文」 */
    commitGlossary() {
      const next = {}
      for (const line of this.glossaryText.split('\n')) {
        const idx = line.indexOf('=')
        if (idx <= 0) continue
        const k = line.slice(0, idx).trim(), v = line.slice(idx + 1).trim()
        if (k && v) next[k] = v
      }
      this.glossary = next
      try { localStorage.setItem(this.glossaryKey(), JSON.stringify(next)) } catch {}
    },

    // ── 译文编辑 / 补译 ───────────────────────────────────────────────────────

    startEdit(i) {
      this.editingIdx = i
      this.editingText = this.ocrResults[i].translation || ''
      this.$nextTick(() => this.$refs.editInput?.[0]?.focus())
    },

    commitEdit() {
      const i = this.editingIdx
      if (i == null) return
      const text = this.editingText.trim()
      this.editingIdx = null
      if (!this.ocrResults[i]) return
      this.ocrResults = this.ocrResults.map((r, idx) => idx === i ? { ...r, translation: text || null, edited: !!text } : r)
      this.unfitBoxes = {}
      this.savePageCache()
      this.$nextTick(() => this.applyTextFit())
    },

    cancelEdit() {
      this.editingIdx = null
    },

    /** 只把没有译文的条目再送一次 */
    async retranslateMissing() {
      const idxs = this.ocrResults.map((r, i) => (r.translation ? -1 : i)).filter(i => i >= 0)
      if (!idxs.length || this.translating) return
      this.translating = true
      const pageNum = this.currentPage
      try {
        const items = await this.translateTexts(idxs.map(i => this.ocrResults[i].text), pageNum)
        if (this.currentPage !== pageNum) return
        const byIdx = new Map(idxs.map((i, k) => [i, items[k]]))
        this.ocrResults = this.ocrResults.map((r, i) => byIdx.has(i) && byIdx.get(i) ? this.applyTranslation(r, byIdx.get(i)) : r)
        this.savePageCache()
        this.$nextTick(() => this.applyTextFit())
      } catch (e) {
        if (e.auth) { this.handleAuthError(); return }
        this.showToast('补译失败: ' + e.message, 'error')
      } finally {
        this.translating = false
      }
    },

    async performOcr() {
      if (!this.imageUrl) return
      this.ocrProcessing = true
      this.ocrResults = []
      this.selectedBoxIdx = null
      this.bubbleCard = null
      try {
        const img = await this.ensureImageDecoded(this.$refs.imgRef)
        const { results, source } = await this.ocrImage(img, this.ocrSource)
        this.lastOcrSource = source
        this.expandedBboxes = {}
        this.unfitBoxes = {}
        this.ocrResults = results
        this.savePageCache()
        if (!results.length) this.showToast('未识别到文字', 'info')
      } catch (e) {
        if (e.auth) { this.handleAuthError(); return }
        this.showToast('OCR 失败: ' + e.message, 'error')
      } finally {
        this.ocrProcessing = false
      }
    },

    // ── Translate ─────────────────────────────────────────────────────────────

    async performTranslate() {
      if (!this.ocrResults.length) return
      this.translating = true
      const pageNum = this.currentPage
      try {
        const translations = await this.translateTexts(this.ocrResults.map(r => r.text), pageNum)
        // 翻译期间用户可能已翻页
        if (this.currentPage !== pageNum) return
        this.ocrResults = this.ocrResults.map((r, i) => this.applyTranslation(r, translations[i]))
        this.savePageCache()
        const missing = translations.filter(t => !t).length
        if (missing) this.showToast(`翻译完成，${missing} 条未返回译文`, 'info')
        this.$nextTick(() => this.applyTextFit())
      } catch (e) {
        if (e.auth) { this.handleAuthError(); return }
        this.showToast('翻译失败: ' + e.message, 'error')
      } finally {
        this.translating = false
      }
    },

    // ── 下一页预取 ────────────────────────────────────────────────────────────

    /** 自动模式下，当前页出结果后就在后台把下一页 OCR + 翻译好写进缓存，翻页零等待 */
    maybePrefetchNext() {
      if (!this.autoTranslate) return
      const next = this.currentPage + 1
      if (next > this.totalPages) return
      if (this.loadPageCache(next)) return
      if (!this._prefetch) this._prefetch = {}
      if (this._prefetch[next]) return
      const task = this.prefetchPage(next).catch(() => {}).finally(() => { delete this._prefetch[next] })
      this._prefetch[next] = task
    },

    async prefetchPage(pageNum) {
      const meta = this.galleryImages[pageNum - 1]
      if (!meta?.pageUrl) return
      const res = await fetch(`${API_BASE}/api/image-url?pageUrl=${encodeURIComponent(meta.pageUrl)}`)
      const data = await res.json()
      if (data.error) throw new Error(data.error)
      const img = new Image()
      img.crossOrigin = 'anonymous'
      img.src = `${API_BASE}/api/image-proxy?imageUrl=${encodeURIComponent(data.imageUrl)}`
      await img.decode()
      const { results, source } = await this.ocrImage(img, this.ocrSource)
      let translated = results
      if (results.length) {
        const translations = await this.translateTexts(results.map(r => r.text), pageNum)
        translated = results.map((r, i) => this.applyTranslation(r, translations[i]))
      }
      this.writePageCache(pageNum, translated, source)
    },

    deleteResult(i) {
      const id = this.ocrResults[i]._id
      this.ocrResults.splice(i, 1)
      if (this.bubbleCard != null) this.bubbleCard = null
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
      this.unfitBoxes = {}
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

    /** 译文是否按竖排渲染：优先用合并阶段判出的方向，旧缓存没有该字段时按框形状判 */
    isVerticalBox(result) {
      if (result.orientation) return result.orientation === 'vertical'
      return boxOrientation(this.expandedBboxes[result._id] || result.bbox) === 'vertical'
    },

    /**
     * 让每条译文在框内放得下：字号不低于 MIN_OVERLAY_FONT_PX（屏幕像素），
     * 放不下就把框四周各外扩 12 屏幕像素（换算回图片坐标）再试，最多 MAX_BOX_EXPAND_STEPS 次，
     * 仍不行则标记 unfit，模板改渲染序号徽标。
     */
    applyTextFit() {
      requestAnimationFrame(async () => {
        const img = this.$refs.imgRef
        const stepImg = 12 / (this.imageFrame()?.s || 1)
        for (const id of Object.keys(this.transTextRefs)) {
          for (let step = 0; ; step++) {
            const el = this.transTextRefs[id]
            if (!el) break
            if (fitTextToBox(el, MIN_OVERLAY_FONT_PX)) break
            if (step >= MAX_BOX_EXPAND_STEPS) {
              this.unfitBoxes = { ...this.unfitBoxes, [id]: true }
              break
            }
            const result = this.ocrResults.find(r => r._id === id)
            if (!result) break
            const [bx1, by1, bx2, by2] = this.expandedBboxes[id] || result.bbox
            // 外扩后若越过图片边缘就整体平移回来，译文不会被裁掉半截
            let nx1 = bx1 - stepImg, ny1 = by1 - stepImg, nx2 = bx2 + stepImg, ny2 = by2 + stepImg
            const iw = img?.naturalWidth || Infinity, ih = img?.naturalHeight || Infinity
            if (nx1 < 0) { nx2 -= nx1; nx1 = 0 }
            if (ny1 < 0) { ny2 -= ny1; ny1 = 0 }
            if (nx2 > iw) { nx1 = Math.max(0, nx1 - (nx2 - iw)); nx2 = iw }
            if (ny2 > ih) { ny1 = Math.max(0, ny1 - (ny2 - ih)); ny2 = ih }
            this.expandedBboxes = { ...this.expandedBboxes, [id]: [nx1, ny1, nx2, ny2] }
            await this.$nextTick()
          }
        }
      })
    },

    // ── Box positioning ───────────────────────────────────────────────────────

    /**
     * 图片实际绘制区域（相对 .gt-stage）。<img> 的盒子可能比画面大（object-fit: contain 会在盒内留白），
     * 直接用 clientWidth 换算会让框整体偏移，所以按原图宽高比自己算绘制区域。
     */
    imageFrame() {
      const img = this.$refs.imgRef
      if (!img || !img.naturalWidth) return null
      const cw = img.clientWidth, ch = img.clientHeight
      const s = Math.min(cw / img.naturalWidth, ch / img.naturalHeight)
      const rw = img.naturalWidth * s, rh = img.naturalHeight * s
      return { s, x: img.offsetLeft + (cw - rw) / 2, y: img.offsetTop + (ch - rh) / 2 }
    },

    /* 框的位置相对缩放层（.gt-stage）计算：offsetLeft/Top 与 clientWidth 都不受 transform 影响，
       所以缩放 / 平移时无需重算，框天然跟着图片走 */
    getBoxStyle(result, index) {
      const f = this.imageFrame()
      if (!f) return { display: 'none' }
      const [x1, y1, x2, y2] = this.expandedBboxes[result._id] || result.bbox
      return {
        position: 'absolute',
        left: Math.round(f.x + x1 * f.s) + 'px',
        top: Math.round(f.y + y1 * f.s) + 'px',
        width: Math.round((x2 - x1) * f.s) + 'px',
        height: Math.round((y2 - y1) * f.s) + 'px',
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

    kindLabel(kind) {
      return KIND_LABEL[kind] || ''
    },

    hasKanji,
    toHiragana,

    // ── Translation cache ─────────────────────────────────────────────────────

    cacheKey(pageNum) {
      return `trans_cache_${this.gid}_p${pageNum}`
    },

    savePageCache() {
      if (!this.ocrResults.length) return
      this.writePageCache(this.currentPage, this.ocrResults, this.lastOcrSource)
    },

    writePageCache(pageNum, ocrResults, lastOcrSource) {
      try {
        localStorage.setItem(this.cacheKey(pageNum), JSON.stringify({ ocrResults, lastOcrSource, ts: Date.now() }))
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
  transition: border-color var(--dur-fast) var(--ease-out);
}
.gt-pwd-input:focus { border-color: var(--primary-color); }
.gt-pwd-input:disabled { opacity: 0.5; }

.gt-pwd-error {
  margin: 0;
  font-size: 12px;
  color: var(--danger-color);
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
  transition: color var(--dur-fast);
}
.gt-pwd-back:hover { color: var(--text-color); }

/* ── Header ──────────────────────────────────────────────────────────────────── */

.gt-header {
  position: relative;
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

.gt-progress {
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 2px;
  background: color-mix(in srgb, var(--primary-color) 25%, transparent);
  overflow: hidden;
}
.gt-progress::after {
  content: '';
  position: absolute;
  inset: 0;
  width: 50%;
  background: var(--primary-color);
  transform: translateX(-100%);
  animation: gt-progress-slide 1.2s var(--ease-in-out) infinite;
}
.gt-progress.is-step2 { background: color-mix(in srgb, var(--primary-color) 50%, transparent); }
@keyframes gt-progress-slide {
  to { transform: translateX(200%); }
}
@media (prefers-reduced-motion: reduce) {
  .gt-progress::after { animation: none; transform: none; width: 100%; opacity: 0.6; }
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
  transition: color var(--dur-fast), background var(--dur-fast);
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
  transition: background var(--dur-fast), color var(--dur-fast), border-color var(--dur-fast), opacity var(--dur-fast);
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
  color: var(--danger-color);
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
  transition: color var(--dur-fast), border-color var(--dur-fast), background var(--dur-fast);
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
  transition: border-color var(--dur-fast), transform var(--dur-fast);
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
  /* OCR 框带内联 z-index: 10/20。没有这行的话 .gt-image-panel 只是 position: relative、
     z-index: auto，不构成层叠上下文，那些框会跑到根层叠上下文里去比高低，
     于是盖住 z-index: 6 的底部抽屉 —— 图片被正常遮挡，气泡却浮在抽屉之上。
     这里显式建一个层叠上下文，把框关在图片区内部。 */
  z-index: 0;
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

.gt-image-error { color: var(--danger-color); }

.gt-image-empty { text-align: center; }

.gt-empty-icon { font-size: 40px; }

/* 缩放层：撑满图片区，图片在其中居中；transform 作用在它身上 */
.gt-stage {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  transform-origin: 0 0;
  will-change: transform;
  /* 捏合 / 平移 / 滑动翻页全部自己处理，浏览器别再插手 */
  touch-action: none;
}

/* 翻页过场：拖动中无过渡（跟手），松手后 200ms 滑出 / 回弹 / 滑入 */
.gt-stage.is-sliding { transition: transform var(--dur-base) var(--ease-out); }

/* 图片加载失败 / 错误态的图片区也要能点边缘翻页，光标提示一下 */
.gt-image-panel:not(.is-zoomed) { cursor: default; }

.gt-image-panel.is-zoomed { cursor: grab; }
.gt-image-panel.is-zoomed:active { cursor: grabbing; }

.gt-page-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  display: block;
  user-select: none;
  -webkit-user-drag: none;
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
  transition: border-color var(--dur-fast), background var(--dur-fast), box-shadow var(--dur-fast);
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

/* 高瘦的对白框按竖排渲染：横排中文塞进 30×150 的框只能一列单字，竖排才是漫画本来的样子 */
.gt-box-trans-text.gt-box-vertical {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  letter-spacing: 0.04em;
}

/* 放不下译文的框：只留一个序号徽标，点击后在列表 / 气泡卡里看全文 */
.gt-ocr-box.gt-box-has-badge { overflow: visible; }

.gt-box-badge {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  min-width: 20px;
  height: 20px;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--primary-color);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  line-height: 20px;
  text-align: center;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.35);
  pointer-events: none;
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
  transition: transform var(--dur-base) var(--ease-out);
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
  transition: background var(--dur-fast), color var(--dur-fast);
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
  transition: background var(--dur-fast), color var(--dur-fast), border-color var(--dur-fast);
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
  transition: background var(--dur-fast), color var(--dur-fast), border-color var(--dur-fast);
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
  transition: background var(--dur-base) var(--ease-out), border-color var(--dur-base) var(--ease-out), opacity var(--dur-base) var(--ease-out);
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
  transition: transform var(--dur-base) var(--ease-out);
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
  color: var(--success-color);
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
  transition: border-color var(--dur-fast), background var(--dur-fast);
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
  color: var(--success-color);
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
  transition: background var(--dur-fast), color var(--dur-fast);
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

.gt-result-trans-row {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border-color);
}

.gt-result-trans {
  flex: 1;
  min-width: 0;
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--primary-color);
  word-break: break-all;
}

.gt-kind-tag {
  display: inline-block;
  margin-right: 5px;
  padding: 0 5px;
  border-radius: 4px;
  background: var(--primary-soft-bg);
  border: 1px solid var(--primary-soft-border);
  color: var(--primary-on-soft);
  font-size: 10px;
  line-height: 16px;
  vertical-align: 1px;
}

.gt-result-edit-btn {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  padding: 0;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--muted-color);
  font-size: 13px;
  cursor: pointer;
  opacity: 0;
  transition: opacity var(--dur-fast) var(--ease-out), background var(--dur-fast) var(--ease-out), color var(--dur-fast) var(--ease-out);
}
.gt-result-item:hover .gt-result-edit-btn,
.gt-result-selected .gt-result-edit-btn,
.gt-result-edit-btn:focus-visible { opacity: 1; }
.gt-result-edit-btn:hover { background: var(--hover-bg); color: var(--text-color); }
@media (hover: none) { .gt-result-edit-btn { opacity: 1; } }

.gt-result-alt {
  margin: 4px 0 0;
  font-size: 11px;
  line-height: 1.5;
  color: var(--muted-color);
}

.gt-result-missing {
  margin: 8px 0 0;
  padding-top: 8px;
  border-top: 1px dashed var(--border-color);
  font-size: 11px;
  color: var(--muted-color);
  display: flex;
  gap: 8px;
  align-items: center;
}

.gt-link-btn {
  padding: 0;
  border: none;
  background: none;
  color: var(--primary-color);
  font-size: inherit;
  font-family: inherit;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.gt-result-edit {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.gt-edit-input {
  width: 100%;
  box-sizing: border-box;
  padding: 6px 8px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-color);
  color: var(--text-color);
  font: inherit;
  font-size: 13px;
  line-height: 1.5;
  resize: vertical;
}
.gt-edit-input:focus { border-color: var(--primary-color); }

.gt-edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
}

.gt-retranslate { margin-left: auto; }

.gt-chip-count {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.gt-chip-badge {
  min-width: 16px;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--surface-color);
  color: var(--muted-color);
  font-size: 10px;
  font-weight: 600;
  line-height: 16px;
  text-align: center;
}
.gt-chip.active .gt-chip-badge {
  background: color-mix(in srgb, var(--primary-color) 22%, transparent);
  color: var(--primary-color);
}

/* 展开的术语编辑区：与 key 列对齐（32px + 10px gap） */
.gt-glossary {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-left: 42px;
}
.gt-glossary-input { font-size: 12px; line-height: 1.6; }
.gt-glossary-hint { font-size: 11px; color: var(--muted-color); }

@media (max-width: 767px) {
  .gt-glossary { margin-left: 0; }
}

/* 拟声词：不压黑底，半透明底 + 加粗，与对白区分 */
.gt-box-trans-text.gt-box-sfx {
  background: rgba(0, 0, 0, 0.45);
  font-weight: 700;
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
  animation: gt-toast-in var(--dur-base) ease;
}

.gt-toast span { flex: 1; }

.gt-toast-success { border-color: rgba(74, 222, 128, 0.35); color: var(--success-color); }
.gt-toast-error   { border-color: rgba(248, 113, 113, 0.35); color: var(--danger-color); }
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
  color: var(--success-color);
  border-color: rgba(74, 222, 128, 0.35);
  background: rgba(74, 222, 128, 0.08);
}
.gt-source-e-hentai .gt-source-dot { background: var(--success-color); }
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
  transition: opacity var(--dur-fast);
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
  transition: background var(--dur-fast);
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
  transition: background var(--dur-fast), color var(--dur-fast);
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

.gt-wc-err { color: var(--danger-color); }

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
  color: var(--success-color);
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
.gt-wc-enter-active { transition: opacity var(--dur-fast), transform var(--dur-fast); }
.gt-wc-leave-active { transition: opacity var(--dur-fast), transform var(--dur-fast); }
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
  .gt-header-actions .gt-btn { min-height: var(--tap-target); }

  /* 抽屉内容重排：把手 → 识别结果 → 功能设置 → 缩略图条（只在全开时给）。
     此前缩略图 + 展开的设置占掉前 ~220px，半开时只露得出一两条结果。 */
  .gt-sheet-handle { order: -1; }
  .gt-sidebar-hdr { order: 0; }
  .gt-sidebar-hdr-plain { display: none; }
  .gt-sidebar-hdr .gt-sidebar-title, .gt-sidebar-hdr .gt-count-badge { display: none; }
  .gt-sidebar-empty, .gt-results-list { order: 1; }
  .gt-config-panel { order: 2; border-top: 1px solid var(--border-color); }
  .gt-strip { order: 3; }
  .gt-sidebar:not(.is-full) .gt-strip { display: none; }

  /* ── 气泡卡：浮在抽屉把手上方 ── */
  .gt-bubble-card {
    position: fixed;
    left: 12px;
    right: 12px;
    bottom: calc(var(--gt-sheet-safe) + 10px);
    z-index: 7;
    max-height: 42dvh;
    overflow-y: auto;
    padding: 10px 14px 12px;
    border-radius: var(--radius-lg);
    background: var(--row-bg);
    border: 1px solid var(--border-color);
    box-shadow: 0 8px 28px rgba(0, 0, 0, 0.32);
  }

  .gt-bc-head {
    display: grid;
    grid-template-columns: var(--tap-target) 1fr var(--tap-target) var(--tap-target);
    align-items: center;
    margin: -6px -8px 2px;
  }

  .gt-bc-pos {
    text-align: center;
    font-size: 12px;
    color: var(--muted-color);
  }

  .gt-bc-nav, .gt-bc-close {
    min-width: var(--tap-target);
    min-height: var(--tap-target);
    border: none;
    background: transparent;
    color: var(--text-color);
    font-size: 20px;
    line-height: 1;
    cursor: pointer;
  }
  .gt-bc-nav:disabled { color: var(--faint-color); }

  .gt-bc-orig {
    margin: 0 0 6px;
    font-size: 13px;
    line-height: 1.5;
    color: var(--muted-color);
  }

  .gt-bc-trans {
    margin: 0;
    font-size: 16px;
    line-height: 1.5;
    color: var(--text-color);
  }
  .gt-bc-pending { color: var(--faint-color); font-style: italic; }
  .gt-bc-alt { margin: 6px 0 0; font-size: 12px; color: var(--muted-color); }

  .gt-bc-enter-active { transition: opacity var(--dur-base) var(--ease-out), transform var(--dur-base) var(--ease-out); }
  .gt-bc-leave-active { transition: opacity var(--dur-fast) var(--ease-in-out), transform var(--dur-fast) var(--ease-in-out); }
  .gt-bc-enter-from, .gt-bc-leave-to { opacity: 0; transform: translateY(12px); }
}

/* 桌面端没有气泡卡（侧栏就是详情） */
@media (min-width: 768px) {
  .gt-bubble-card { display: none; }
}

</style>
