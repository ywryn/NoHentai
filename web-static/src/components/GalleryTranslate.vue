<template>
  <!-- Password Dialog -->
  <AccessPassword v-if="!passwordVerified" prefix="translate" label="翻译访问密码"
    v-model="passwordInput" :password-loading="passwordLoading" :password-error="passwordError"
    @verify="verifyPassword()" @back="$router.back()" />

  <!-- Main Workbench -->
  <div v-else class="gt-workbench" :style="{ '--gt-sheet-h': sheetHeight }">
    <!-- Header -->
    <header v-show="!comparing" class="gt-header">
      <button class="gt-back-btn" aria-label="返回详情" @click="$router.back()"><AppIcon name="arrow-left" :size="18" /></button>

      <div class="gt-header-info">
        <span v-if="totalPages" class="gt-header-pages">{{ currentPage }} / {{ totalPages }}</span>
      </div>

      <div class="gt-header-actions">
        <RouterLink v-if="imageReady && ocrResults.length && !ocrProcessing && !translating" class="gt-btn" :to="{ query: { ...$route.query, view: 'compare' } }">排版对比</RouterLink>
        <button v-if="ocrResults.length" class="gt-btn gt-view-toggle" type="button" :aria-pressed="showTranslation" @click="showTranslation = !showTranslation">{{ showTranslation ? '显示原图' : '显示译文' }}</button>
        <button class="gt-btn gt-btn-primary" type="button"
          :disabled="!imageReady || imageError || imageLoading || ocrProcessing || translating || imagesLoading"
          @click="missingCount ? retranslateMissing() : performOcrAndTranslate()"
        >{{ ocrProcessing ? '识别中' : translating ? '翻译中' : missingCount ? `补译 ${missingCount} 条` : ocrResults.length ? '重新识别' : '识别并翻译' }}</button>
      </div>
      <!-- 两步流水线的进度条：替代原来一条接一条的 toast -->
      <div v-if="ocrProcessing || translating" class="gt-progress" :class="{ 'is-step2': translating }" aria-hidden="true"></div>
    </header>

    <!-- Main body -->
    <LayoutCompare v-if="comparing" :image="imageReady ? $refs.imgRef : null" :results="ocrResults" :page="currentPage" :error="imageError || imagesError" />
    <div v-show="!comparing" class="gt-body">
      <!-- Image panel -->
      <div
        class="gt-image-panel"
        ref="containerRef"
        :class="{ 'is-zoomed': zoom.scale > 1 }"
        @pointerdown="onStagePointerDown"
        @wheel="onStageWheel"
      >
        <div v-if="!imageError && !imageReady && (imagesLoading || imageLoading || imageUrl)" class="gt-image-placeholder gt-image-loading">
          <ImageLoadProgress :stage="imageLoading || imageUrl ? 'image' : 'list'" />
        </div>
        <div v-if="imageError" class="gt-image-placeholder gt-image-error" role="alert"><span>{{ imageError }}</span><button class="gt-btn" @pointerdown.stop @click.stop="retryCurrentImage()">重新加载图片</button></div>
        <!-- 缩放层：图片与 OCR 框同在一个 transform 下，捏合 / 双击放大时框随图一起走 -->
        <div v-else-if="imageUrl" v-show="imageReady" class="gt-stage" :class="{ 'is-sliding': pageSliding }" :style="stageStyle">
          <img
            ref="imgRef"
            :key="imageUrl"
            :src="imageUrl"
            class="gt-page-img"
            alt="manga page"
            crossorigin="anonymous"
            draggable="false"
            @load="onImageLoad"
            @error="onImageError"
          />
          <!-- OCR boxes overlay -->
          <div v-if="imageReady && ocrResults.length && renderTick >= 0" class="gt-boxes-layer">
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
              role="button"
              tabindex="0"
              :aria-label="`第 ${i + 1} 条识别结果`"
              @keydown.enter.prevent="onBoxClick(i)"
              @keydown.space.prevent="onBoxClick(i)"
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
        <div v-else-if="!imageLoading && !imagesLoading" class="gt-image-placeholder gt-image-empty">
          <div class="gt-empty-icon">📖</div>
          <p>从右侧选择页面</p>
        </div>

      </div>

      <!-- Sidebar（移动端为底部抽屉） -->
      <div
        ref="sidebarRef"
        class="gt-sidebar visible-scrollbar"
        :class="[`is-${sheetState}`, { 'is-dragging': sheetDragging }]"
      >
        <!-- 移动端抽屉把手：收起时只占一条，图片区因此能拿到整屏 -->
        <div
          class="gt-sheet-handle"
          @pointerdown="onSheetPointerDown"
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
            ><AppIcon name="chevron-left" :size="18" /></button>
            <button type="button" class="gt-sheet-label" aria-label="识别结果面板" :aria-expanded="sheetState !== 'peek'" @pointerdown.stop @click="cycleSheet">
              识别结果
              <span v-if="ocrResults.length" class="gt-sheet-count">{{ ocrResults.length }}</span>
            </button>
            <button
              class="gt-sheet-nav"
              type="button"
              :disabled="currentPage >= totalPages"
              aria-label="下一页"
              @pointerdown.stop
              @click.stop="nextPage"
            ><AppIcon name="chevron-right" :size="18" /></button>
          </div>
        </div>

        <!-- Thumbnail strip inside sidebar -->
        <div class="gt-strip" v-if="galleryImages.length">
          <button class="gt-strip-nav" aria-label="上一页缩略图" :disabled="currentPage <= 1" @click="prevPage"><AppIcon name="chevron-left" :size="18" /></button>
          <div class="gt-strip-scroll visible-scrollbar" ref="stripRef">
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
          <button class="gt-strip-nav" aria-label="下一页缩略图" :disabled="currentPage >= totalPages" @click="nextPage"><AppIcon name="chevron-right" :size="18" /></button>
        </div>
        <div v-else-if="imagesLoading" class="gt-strip gt-strip-loading">
          <div class="gt-spinner-sm"></div>
          <span>加载缩略图...</span>
        </div>
        <div v-else-if="imagesError" class="gt-strip gt-strip-error" role="alert"><span>{{ imagesError }}</span><button class="gt-btn" @click="loadGalleryImages">重新加载页面列表</button></div>

        <!-- Config panel -->
        <div class="gt-config-panel" :class="{ 'gt-config-panel-collapsed': !configPanelExpanded }">
          <button class="gt-config-toggle" @click="configPanelExpanded = !configPanelExpanded">
            <span>功能设置</span>
            <span class="gt-config-toggle-icon" :class="{ 'is-open': configPanelExpanded }"><AppIcon name="chevron-up" :size="18" /></span>
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
            <label class="gt-cfg-key" for="gt-translation-engine">翻译</label>
            <select id="gt-translation-engine" class="gt-engine-select" v-model="translationEngine" :disabled="ocrProcessing || translating">
              <option value="model">模型翻译</option>
              <option value="google">Google 翻译 API</option>
            </select>
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
            <span class="gt-glossary-hint">按画廊保存，仅模型翻译使用术语表</span>
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
          <AppIcon name="search" :size="36" />
          <p>{{ imageUrl ? '点击 OCR 开始识别' : '请先选择页面' }}</p>
        </div>

        <div v-else class="gt-results-list">
          <article
            v-for="(result, i) in ocrResults"
            :key="result._id"
            class="gt-result-item"
            :data-idx="i"
            :class="{ 'gt-result-selected': selectedBoxIdx === i }"
            @click="onResultClick(i)"
          >
            <div class="gt-result-meta">
              <button type="button" class="gt-result-idx" :aria-label="`查看第 ${i + 1} 条识别结果`" :aria-pressed="selectedBoxIdx === i" @click.stop="onResultClick(i)">{{ i + 1 }}</button>
              <span v-if="result.confidence < 0.8" class="gt-result-conf" :title="`识别置信度 ${(result.confidence * 100).toFixed(0)}%`">待核对</span>

              <span v-if="result.translation" class="gt-done-mark"><AppIcon name="check" :size="14" /></span>
              <button class="gt-result-del" @click.stop="deleteResult(i)" :aria-label="`删除第 ${i + 1} 条识别结果`" title="删除"><AppIcon name="close" :size="18" /></button>
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
                aria-label="编辑译文"
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
                <button class="gt-result-edit-btn" type="button" title="编辑译文" aria-label="编辑译文" @click.stop="startEdit(i)"><AppIcon name="edit" :size="16" /></button>
              </div>
              <p v-if="result.translation && result.alt" class="gt-result-alt">备选：{{ result.alt }}</p>
              <p v-else-if="!result.translation && ocrResults.some(r => r.translation)" class="gt-result-missing">
                未翻译
                <button class="gt-link-btn" type="button" @click.stop="startEdit(i)">手动填写</button>
              </p>
            </template>
          </article>
        </div>
      </div>
    </div>

    <!-- 移动端：点框后浮在抽屉把手上方的气泡卡，不用拉抽屉就能读原文 + 译文 -->
    <Transition name="gt-bc">
      <div v-if="!comparing && bubbleCard != null && ocrResults[bubbleCard]" class="gt-bubble-card" role="dialog" aria-label="对白详情">
        <div class="gt-bc-head">
          <button class="gt-bc-nav" type="button" :disabled="bubbleCard <= 0" aria-label="上一条" @click="stepBubble(-1)"><AppIcon name="chevron-left" :size="18" /></button>
          <span class="gt-bc-pos">{{ bubbleCard + 1 }} / {{ ocrResults.length }}</span>
          <button class="gt-bc-nav" type="button" :disabled="bubbleCard >= ocrResults.length - 1" aria-label="下一条" @click="stepBubble(1)"><AppIcon name="chevron-right" :size="18" /></button>
          <button class="gt-bc-close" type="button" aria-label="关闭" @click="closeBubble"><AppIcon name="close" :size="18" /></button>
        </div>
        <p class="gt-bc-orig">{{ ocrResults[bubbleCard].text }}</p>
        <p v-if="ocrResults[bubbleCard].translation" class="gt-bc-trans">{{ ocrResults[bubbleCard].translation }}</p>
        <p v-else class="gt-bc-trans gt-bc-pending">尚未翻译</p>
        <button class="gt-bc-edit" type="button" @click="editBubble">{{ ocrResults[bubbleCard].translation ? '编辑译文' : '手动填写' }}</button>
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
              <span v-if="wordCard.word !== wordCard.token.surface_form" class="gt-wc-base-form"><AppIcon name="arrow-right" :size="14" /> {{ wordCard.word }}</span>
            </div>
            <div class="gt-wc-meta-row">
              <span class="gt-wc-pos-badge" :style="{ background: getPosColor(wordCard.token.pos) + '22', color: getPosColor(wordCard.token.pos), borderColor: getPosColor(wordCard.token.pos) + '55' }">
                {{ wordCard.token.pos }}{{ wordCard.token.pos_detail_1 && wordCard.token.pos_detail_1 !== '*' ? '・' + wordCard.token.pos_detail_1 : '' }}
              </span>
              <span v-if="wordCard.token.conjugated_form && wordCard.token.conjugated_form !== '*'" class="gt-wc-conj">{{ wordCard.token.conjugated_form }}</span>
            </div>
            <button class="gt-wc-close" aria-label="关闭词语详情" @click="wordCard = null"><AppIcon name="close" :size="18" /></button>
          </div>

          <div class="gt-wc-body visible-scrollbar">
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
        <button class="gt-toast-close" aria-label="关闭通知" @click="removeToast(toast.id)"><AppIcon name="close" :size="18" /></button>
      </div>
    </div>
  </div>
</template>

<script>
import { defineAsyncComponent, markRaw } from 'vue'
import { useReader } from '@/composables/useReader'
import AccessPassword from './AccessPassword.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import ImageLoadProgress from '@/components/ui/ImageLoadProgress.vue'
import {readTranslationResponse,scaleOcrResults} from '@/utils/translationApi'
import { loadGallery } from '@/composables/useGalleryData'
import { loadPageDraft, savePageDraft, clearPageDraft, validOcrResults } from '@/composables/useTranslateDrafts'
import { VERTICAL_ASPECT, POS_COLOR, loadKuromoji, hasKanji, toHiragana, mergeOcrResults, fitTextToBox, boxOrientation } from '@/utils/translateHelpers'

const API_BASE = import.meta.env.VITE_API_BASE || ''

const TRANS_CACHE_TTL = 3 * 24 * 60 * 60 * 1000
/* 每画廊术语表：{ 原文: 译文 }，随翻译请求一起送给模型 */
const TRANSLATION_ENGINE_KEY = 'trans_engine'
const GLOSSARY_KEY_PREFIX = 'trans_glossary_'
const KIND_LABEL = { dialogue: '对白', narration: '旁白', sfx: '拟声' }

/* 移动端底部抽屉的三个档位。peek 与 CSS 里的 --gt-sheet-peek 保持一致 */
const SHEET_PEEK_PX = 64
const SHEET_SNAPS = { peek: `${SHEET_PEEK_PX}px`, half: '50dvh', full: '88dvh' }
const SHEET_ORDER = ['peek', 'half', 'full']

/* 译文叠加层：字号地板（CSS px）以下不再硬塞，改显示序号徽标 */
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

function savedTranslationEngine() {
  try {
    if (localStorage.getItem(TRANSLATION_ENGINE_KEY) === 'google') return 'google'
  } catch {}
  return 'model'
}


// ── Component ─────────────────────────────────────────────────────────────────

export default {
  components: { LayoutCompare: defineAsyncComponent(() => import('./LayoutCompare.vue')), AppIcon, ImageLoadProgress, AccessPassword },
  name: 'GalleryTranslate',
  props: { live: Boolean },

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

      // Current page
      currentPage: 1,
      imageUrl: null,
      imageLoading: false,
      imageReady: false,
      imageError: null,
      imageAutoRetried: false,
      imageRequestId: 0,
      processingGeneration: 0,
      imageVersion: null,

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
      translationEngine: savedTranslationEngine(),
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
    thumbnailSprites() {
      const sprites = new Map()
      for (const img of this.galleryImages) {
        if (!img.thumbSprite) continue
        const meta = sprites.get(img.thumbSprite) || { count: 0, maxOffset: 0 }
        meta.count++
        meta.maxOffset = Math.max(meta.maxOffset, -img.thumbX)
        sprites.set(img.thumbSprite, meta)
      }
      return sprites
    },
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
    comparing() { return this.$route.query.view === 'compare' },
    stageStyle() {
      const { scale, tx, ty } = this.zoom
      const ox = tx + this.pageOffset
      if (scale === 1 && !ox && !ty) return null
      return { transform: `translate(${ox}px, ${ty}px) scale(${scale})` }
    },
  },

  watch: {
    translationEngine(engine) {
      try { localStorage.setItem(TRANSLATION_ENGINE_KEY, engine) } catch {}
    },
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

    fetch(`${import.meta.env.BASE_URL}data/translate-config.json`, { cache: 'no-cache' })
      .then(r => { if (!r.ok) throw new Error(); return r.json() })
      .then(config => { if (['google', 'paddle', 'ocrspace'].includes(config.defaultOcr)) this.ocrSource = config.defaultOcr })
      .catch(() => {})

    this.loadGlossary()
    if (this.live) {
      this.imageReader = markRaw(useReader(String(this.$route.query.site || '')))
      this.passwordVerified = true
      this.loadGalleryImages()
      return
    } else {
      this.imageReader = markRaw(useReader())
    }
    loadGallery(this.gid).then(result => {
      this.galleryMeta = result.gallery
    }).catch(() => { this.galleryMeta = null })

    sessionStorage.removeItem('trans_password')
    this.verifyPassword(true)
  },

  mounted() {
    this._ro = new ResizeObserver(() => { this.renderTick++ })
    if (this.$refs.containerRef) this._ro.observe(this.$refs.containerRef)
  },

  beforeUnmount() {
    this.imageRequestId++
    this.releasePageImage()
    this._prefetchController?.abort()
    this._disposed = true
    this.processingGeneration++
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
      if (!isMobile()) { this.$nextTick(() => this.$refs.sidebarRef?.querySelector('.gt-result-selected')?.scrollIntoView({ block: 'nearest', behavior: prefersReducedMotion() ? 'instant' : 'smooth' })); return }
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

    editBubble() {
      const index = this.bubbleCard
      if (index == null) return
      this.bubbleCard = null
      this.setSheet('full')
      this.startEdit(index)
      this.$nextTick(() => this.$refs.sidebarRef?.querySelector(`.gt-result-item[data-idx="${index}"]`)?.scrollIntoView({ block: 'nearest' }))
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

    async verifyPassword(probe = false) {
      const silent = probe === true
      if (!silent && !this.passwordInput) return
      this.passwordLoading = true
      this.passwordError = ''
      try {
        const res = await fetch(`${API_BASE}/api/trans-verify`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(silent ? {} : { password: this.passwordInput }),
        })
        if (res.ok) {
          this.passwordInput = ''
          this.passwordVerified = true
          this.$nextTick(() => {
            if (this.$refs.containerRef) this._ro?.observe(this.$refs.containerRef)
          })
          this.loadGalleryImages()
        } else {
          if (!silent) this.passwordError = '密码错误'
        }
      } catch {
        this.passwordError = '验证失败，请检查网络'
      } finally {
        this.passwordLoading = false
      }
    },

    // ── Gallery images ────────────────────────────────────────────────────────

    async loadGalleryImages() {
      if (this.imagesLoading) return
      if (!this.token) {
        this.imagesError = '缺少 token 参数'
        return
      }
      this.imagesLoading = true
      this.imagesError = null
      try {
        const reader = this.imageReader
        await reader.init(this.gid, this.token, this.currentPage, false)
        if (this._disposed) return
        if (reader.initError.value) throw new Error(reader.initError.value)
        this.galleryImages = reader.pages.value
        if (this.live) this.galleryMeta = { title: reader.galleryTitle.value }
        this.loadedThumbPages = {}
        this.$nextTick(() => this.setupThumbObserver())
        this.goToPage(Math.min(Math.max(this.currentPage, 1), this.totalPages))
      } catch (e) {
        this.imagesError = e.message
      } finally {
        this.imagesLoading = false
      }
    },

    // ── Page navigation ───────────────────────────────────────────────────────

    releasePageImage() {
      this._imageController?.abort()
      if (this.imageUrl) URL.revokeObjectURL(this.imageUrl)
      this.imageUrl = null
      this.imageVersion = null
    },

    async goToPage(pageNum, refresh = false) {
      const requestId = ++this.imageRequestId
      this.processingGeneration++
      this.ocrProcessing = false
      this.translating = false
      this.imageAutoRetried = refresh
      this.currentPage = pageNum
      this.resetZoom()
      this.bubbleCard = null
      // 不是由 turnPage 发起的切页（缩略图 / 预取等待）就不带过场
      if (this._enterFrom == null) this.finishSlide()
      this.$router.replace({
        name: this.live ? 'LiveTranslate' : 'GalleryTranslate',
        params: { gid: this.gid },
        query: { ...this.$route.query, token: this.token, page: String(pageNum) },
      })
      this.ocrResults = []
      this.selectedBoxIdx = null
      this.imageReady = false
      this.releasePageImage()
      const controller = new AbortController()
      this._imageController = controller
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

      try {
        const data = await this.imageReader.loadPageImage(pageNum, { refresh, signal: controller.signal })
        if (requestId !== this.imageRequestId) return
        if (this._prefetchPage && this._prefetchPage !== pageNum) this._prefetchController?.abort()
        this.imageUrl = URL.createObjectURL(data.blob)
        this.imageVersion = data.version
        // 这一页正在后台预取的话，等它写完缓存再读
        if (this._prefetch?.[pageNum]) {
          this.imageLoading = false
          this.ocrProcessing = true
          try { await this._prefetch[pageNum] } finally {
            if (requestId === this.imageRequestId) this.ocrProcessing = false
          }
          if (requestId !== this.imageRequestId) return
        }
        const cached = this.loadPageCache(pageNum)
        if (cached) {
          this.ocrResults = cached.ocrResults
          this.lastOcrSource = cached.lastOcrSource
          this.expandedBboxes = {}
          this.unfitBoxes = {}
          this.$nextTick(() => this.applyTextFit())
          this.maybePrefetchNext()
        } else if (this.autoTranslate && !this.comparing) {
          await this.$nextTick()
          await this.performOcrAndTranslate()
        }
      } catch (e) {
        if (requestId !== this.imageRequestId) return
        this.imageError = `图片加载失败: ${e.message}`
        this.finishSlide()
      } finally {
        if (requestId === this.imageRequestId) this.imageLoading = false
      }
    },

    onImageError(event) {
      if (event.currentTarget.src !== this.imageUrl) return
      this.imageReady = false
      this.imageLoading = false
      if (!this.imageAutoRetried) {
        this.imageAutoRetried = true
        this.retryCurrentImage()
      } else {
        this.imageError = '图片加载失败，请重试或稍后再试'
        this.finishSlide()
      }
    },

    retryCurrentImage() {
      return this.goToPage(this.currentPage, true)
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

    onImageLoad(event) {
      if (event.currentTarget.src !== this.imageUrl) return
      this.imageReady = true
      this.renderTick++
      if (this._enterFrom != null) {
        this._enterFrom = null
        this.animateOffset(0)
      }
    },

    // ── OCR ───────────────────────────────────────────────────────────────────

    async performOcrAndTranslate() {
      const pageRequest = this.imageRequestId
      const applied = await this.performOcr()
      if (!applied) return
      if (this.ocrResults.length) await this.performTranslate()
      if (pageRequest === this.imageRequestId) this.maybePrefetchNext()
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
     * base64 后再涨 1/3；缩图能降低上传耗时与 OCR 服务负担，通常只有 300–500KB，
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
        body: JSON.stringify(body),
      })
      return readTranslationResponse(res)
    },

    /** 对一张已解码的图片跑 OCR → 合并，返回带 _id 的结果数组与来源。纯函数式，不碰 UI 状态 */
    async ocrImage(img, ocrSource) {
      const { b64, scale } = await this.getOcrPayload(img)
      const data = await this.postTrans('trans-ocr', { imageBase64: b64, ocrSource })
      const raw = scaleOcrResults(data,scale)
      const blockLevel = data.source === 'vision' || data.source === 'ocrspace'
      const stamp = Date.now()
      const results = mergeOcrResults(raw, { blockLevel }).map((r, i) => ({ ...r, _id: `${stamp}_${i}` }))
      return { results, source: data.source }
    },

    /**
     * 翻译一组文本，返回与输入等长的数组，每项 { t, kind, alt } 或 null（模型漏译）。
     * 此前漏译会被回填成原文，界面上看起来像「翻译了但还是日文」。
     */
    async translateTexts(texts, engine = this.translationEngine) {
      const data = await this.postTrans('trans-translate', {
        texts,
        engine,
        ...(engine === 'model' ? this.buildTranslateContext() : {}),
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
        translationSource: item?.source,
        kind: item?.kind ?? result.kind ?? null,
        alt: item?.alt ?? null,
      }
    },

    buildTranslateContext() {
      const ctx = {}
      if (this.galleryMeta) {
        ctx.context = { title: this.galleryMeta.title_jpn || this.galleryMeta.title }
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
      this.ocrResults = this.ocrResults.map((r, idx) => idx === i ? { ...r, translationSource: null, translation: text || null, edited: !!text } : r)
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
      const generation = ++this.processingGeneration
      const pageNum = this.currentPage
      try {
        const items = await this.translateTexts(idxs.map(i => this.ocrResults[i].text))
        if (this.currentPage !== pageNum || generation !== this.processingGeneration) return
        const byIdx = new Map(idxs.map((i, k) => [i, items[k]]))
        this.ocrResults = this.ocrResults.map((r, i) => byIdx.has(i) && byIdx.get(i) ? this.applyTranslation(r, byIdx.get(i)) : r)
        this.savePageCache()
        this.$nextTick(() => this.applyTextFit())
      } catch (e) {
        if (generation !== this.processingGeneration) return
        if (e.auth) { this.handleAuthError(); return }
        this.showToast('补译失败: ' + e.message, 'error')
      } finally {
        if (generation === this.processingGeneration) this.translating = false
      }
    },

    async performOcr() {
      if (!this.imageUrl) return false
      const generation = ++this.processingGeneration
      const pageNum = this.currentPage
      const ocrSource = this.ocrSource
      this.ocrProcessing = true
      this.ocrResults = []
      this.selectedBoxIdx = null
      this.bubbleCard = null
      try {
        const img = await this.ensureImageDecoded(this.$refs.imgRef)
        if (generation !== this.processingGeneration) return false
        const { results, source } = await this.ocrImage(img, ocrSource)
        if (generation !== this.processingGeneration || pageNum !== this.currentPage) return false
        this.lastOcrSource = source
        this.expandedBboxes = {}
        this.unfitBoxes = {}
        this.ocrResults = results
        this.writePageCache(pageNum, results, source)
        if (!results.length) this.showToast('未识别到文字', 'info')
        return true
      } catch (e) {
        if (generation !== this.processingGeneration) return false
        if (e.auth) { this.handleAuthError(); return false }
        this.showToast('OCR 失败: ' + e.message, 'error')
        return false
      } finally {
        if (generation === this.processingGeneration) this.ocrProcessing = false
      }
    },

    // ── Translate ─────────────────────────────────────────────────────────────

    async performTranslate() {
      if (!this.ocrResults.length) return
      this.translating = true
      const generation = ++this.processingGeneration
      const pageNum = this.currentPage
      try {
        const translations = await this.translateTexts(this.ocrResults.map(r => r.text))
        // 翻译期间用户可能已翻页
        if (this.currentPage !== pageNum || generation !== this.processingGeneration) return
        this.ocrResults = this.ocrResults.map((r, i) => this.applyTranslation(r, translations[i]))
        this.savePageCache()
        const missing = translations.filter(t => !t).length
        if (missing) this.showToast(`翻译完成，${missing} 条未返回译文`, 'info')
        this.$nextTick(() => this.applyTextFit())
      } catch (e) {
        if (generation !== this.processingGeneration) return
        if (e.auth) { this.handleAuthError(); return }
        this.showToast('翻译失败: ' + e.message, 'error')
      } finally {
        if (generation === this.processingGeneration) this.translating = false
      }
    },

    // ── 下一页预取 ────────────────────────────────────────────────────────────

    /** 自动模式下，当前页出结果后就在后台把下一页 OCR + 翻译好写进缓存，翻页零等待 */
    maybePrefetchNext() {
      if (!this.autoTranslate || this.comparing) return
      const next = this.currentPage + 1
      if (next > this.totalPages) return
      if (!this._prefetch) this._prefetch = {}
      if (this._prefetch[next]) return
      if (this._prefetchController) return
      const controller = new AbortController()
      this._prefetchController = controller
      this._prefetchPage = next
      this._prefetch[next] = this.prefetchPage(next, controller.signal).catch(() => {}).finally(() => {
        delete this._prefetch[next]
        this._prefetchController = null
        this._prefetchPage = null
      })
    },

    async prefetchPage(pageNum, signal) {
      const engine = this.translationEngine
      const { blob, version } = await this.imageReader.loadPageImage(pageNum, { background: true, signal })
      if (this.loadPageCache(pageNum, version)) return
      const img = new Image()
      const url = URL.createObjectURL(blob)
      try {
        img.src = url
        await img.decode()
        if (signal.aborted) return
        const { results, source } = await this.ocrImage(img, this.ocrSource)
        if (signal.aborted) return
        let translated = results
        if (results.length) {
          const translations = await this.translateTexts(results.map(r => r.text), engine)
          translated = results.map((r, i) => this.applyTranslation(r, translations[i]))
        }
        if (!signal.aborted && engine === this.translationEngine && !this.loadPageCache(pageNum, version)) {
          this.writePageCache(pageNum, translated, source, version)
        }
      } finally {
        URL.revokeObjectURL(url)
      }
    },

    deleteResult(i) {
      const id = this.ocrResults[i]._id
      this.ocrResults.splice(i, 1)
      if (this.bubbleCard != null) this.bubbleCard = null
      delete this.transTextRefs[id]
      if (this.selectedBoxIdx === i) this.selectedBoxIdx = null
      else if (this.selectedBoxIdx > i) this.selectedBoxIdx--
      if (this.ocrResults.length) this.savePageCache()
      else this.clearPageCache()
    },

    clearResults() {
      this.processingGeneration++
      this.ocrProcessing = false
      this.translating = false
      this.clearPageCache()
      this.ocrResults = []
      this.selectedBoxIdx = null
      this.transTextRefs = {}
      this.expandedBboxes = {}
      this.unfitBoxes = {}
    },

    handleAuthError() {
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
          const numbers = Object.keys(batch).map(Number)
          void this.imageReader.loadThumbnails(Math.min(...numbers), Math.max(...numbers))
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
      if (!img.thumbSprite || !this.loadedThumbPages[img.pageNum]) return { width: '100%', height: '100%' }
      const { count: N, maxOffset } = this.thumbnailSprites.get(img.thumbSprite)
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
      return `trans_cache_${this.live ? (this.$route.query.site || 'live') : 'catalog'}_${this.gid}_p${pageNum}`
    },

    clearPageCache(pageNum = this.currentPage) {
      clearPageDraft(this.cacheKey(pageNum))
      try { localStorage.removeItem(this.cacheKey(pageNum)) } catch {}
    },

    savePageCache() {
      if (!this.ocrResults.length) return
      this.writePageCache(this.currentPage, this.ocrResults, this.lastOcrSource)
    },

    writePageCache(pageNum, ocrResults, lastOcrSource, version = this.imageVersion) {
      if (!version) return
      const key = this.cacheKey(pageNum)
      if (savePageDraft(key, version, ocrResults, lastOcrSource)) {
        try { localStorage.removeItem(key) } catch {}
      }
    },

    loadPageCache(pageNum, version = this.imageVersion) {
      if (!version) return null
      const key = this.cacheKey(pageNum)
      const draft = loadPageDraft(key, version)
      if (draft) return draft
      try {
        const raw = localStorage.getItem(key)
        if (!raw) return null
        const entry = JSON.parse(raw)
        if (Date.now() - entry.ts > TRANS_CACHE_TTL) localStorage.removeItem(key)
        else if (entry.version === version && validOcrResults(entry.ocrResults)) return entry
      } catch {}
      return null
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

<style scoped src="../assets/translationOverlay.css"></style>
<style scoped src="../assets/GalleryTranslate.css"></style>
