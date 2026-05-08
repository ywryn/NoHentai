<template>
  <div class="reader-root">

    <!-- Init loading -->
    <div v-if="initLoading" class="reader-init">
      <div class="reader-spinner"></div>
      <p>Loading gallery...</p>
    </div>

    <!-- Init error -->
    <div v-else-if="initError" class="reader-init reader-init-error">
      <p>{{ initError }}</p>
      <button @click="$router.back()">← Go Back</button>
    </div>

    <template v-else>
      <!-- Top bar -->
      <div class="reader-bar" :class="{ 'reader-bar-hidden': !barVisible }">
        <button class="reader-back-btn" @click="goBack">← Back</button>
        <span class="reader-bar-title">{{ galleryTitle }}</span>
        <span class="reader-bar-counter">{{ currentPage }} / {{ total }}</span>
      </div>

      <!-- Stage -->
      <div
        class="reader-stage"
        @click="handleStageClick"
        @touchstart.passive="handleTouchStart"
        @touchend.passive="handleTouchEnd"
      >
        <!-- Spinner while image loads -->
        <div v-if="imageLoading" class="reader-img-spinner">
          <div class="reader-spinner"></div>
        </div>

        <img
          v-show="!imageLoading && !imageError"
          :src="imageUrl"
          class="reader-img"
        />

        <div v-if="imageError" class="reader-img-error">
          <p>Failed to load image</p>
          <button @click.stop="retryImage">Retry</button>
        </div>

        <!-- Desktop arrows -->
        <button
          v-if="currentPage > 1"
          class="reader-arrow reader-arrow-left"
          @click.stop="prev"
        >‹</button>
        <button
          v-if="currentPage < total"
          class="reader-arrow reader-arrow-right"
          @click.stop="next"
        >›</button>
      </div>

      <!-- Mobile bottom bar -->
      <div class="reader-bottom-bar" :class="{ 'reader-bar-hidden': !barVisible }">
        <button :disabled="currentPage <= 1" @click="prev" class="reader-bottom-btn">‹</button>
        <span>{{ currentPage }} / {{ total }}</span>
        <button :disabled="currentPage >= total" @click="next" class="reader-bottom-btn">›</button>
      </div>
    </template>
  </div>
</template>

<script>
const API_BASE = import.meta.env.VITE_API_BASE || 'https://no-hentai.vercel.app'
const PRELOAD_AHEAD = 2

function preloadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = resolve
    img.onerror = reject
    img.src = url
  })
}

export default {
  name: 'GalleryReader',
  data() {
    return {
      pages: [],
      total: 0,
      galleryTitle: '',
      currentPage: 1,
      imageUrl: '',
      imageLoading: false,
      imageError: false,
      nlParam: null,
      initLoading: true,
      initError: null,
      barVisible: true,
      barTimer: null,
      touchStartX: 0,
      touchStartY: 0,
      swipeDetected: false,
      cache: {},
      loadId: 0,
    }
  },
  computed: {
    gid() { return this.$route.params.gid },
    token() { return this.$route.query.token || '' },
    startPage() { return parseInt(this.$route.query.page) || 1 },
  },
  async created() {
    await this.loadGallery()
    if (!this.initError) this.goTo(this.startPage)
  },
  mounted() {
    window.addEventListener('keydown', this.onKey)
    this.resetBarTimer()
  },
  beforeUnmount() {
    window.removeEventListener('keydown', this.onKey)
    clearTimeout(this.barTimer)
  },
  methods: {
    async loadGallery() {
      try {
        const res = await fetch(`${API_BASE}/api/gallery-images?gid=${this.gid}&token=${this.token}`)
        const data = await res.json()
        if (data.error) throw new Error(data.error)
        this.pages = data.images
        this.total = data.total
      } catch (e) {
        this.initError = e.message
      } finally {
        this.initLoading = false
      }
    },

    async fetchImage(pageNum) {
      if (this.cache[pageNum]) return this.cache[pageNum]
      const pg = this.pages.find(p => p.pageNum === pageNum)
      if (!pg) return null
      const res = await fetch(`${API_BASE}/api/image-url?pageUrl=${encodeURIComponent(pg.pageUrl)}`)
      const data = await res.json()
      if (!data.error) this.cache[pageNum] = data
      return data
    },

    async goTo(pageNum) {
      if (pageNum < 1 || pageNum > this.total) return
      this.currentPage = pageNum
      this.imageLoading = true
      this.imageError = false
      const id = ++this.loadId

      try {
        const data = await this.fetchImage(pageNum)
        if (this.loadId !== id) return  // navigated away while fetching URL

        if (!data?.imageUrl) {
          this.imageError = true
          this.imageLoading = false
          return
        }
        this.nlParam = data.nlParam || null

        // Preload image in JS before handing to template — avoids mid-load src changes
        await preloadImage(data.imageUrl)
        if (this.loadId !== id) return  // navigated away while image was downloading

        this.imageUrl = data.imageUrl
        this.imageLoading = false
      } catch {
        if (this.loadId === id) {
          this.imageError = true
          this.imageLoading = false
        }
      }

      // Prefetch adjacent page URLs (not images) in background
      for (let i = 1; i <= PRELOAD_AHEAD; i++) {
        this.fetchImage(pageNum + i)
        this.fetchImage(pageNum - i)
      }
    },

    prev() { this.goTo(this.currentPage - 1) },
    next() { this.goTo(this.currentPage + 1) },

    onKey(e) {
      if (e.key === 'ArrowLeft' || e.key === 'a') this.prev()
      else if (e.key === 'ArrowRight' || e.key === 'd') this.next()
      else if (e.key === 'Escape') this.goBack()
      this.showBar()
    },

    goBack() {
      this.$router.push(`/gallery/${this.gid}/`)
    },

    handleTouchStart(e) {
      this.touchStartX = e.touches[0].clientX
      this.touchStartY = e.touches[0].clientY
      this.swipeDetected = false
    },

    handleTouchEnd(e) {
      const dx = e.changedTouches[0].clientX - this.touchStartX
      const dy = e.changedTouches[0].clientY - this.touchStartY
      if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy)) {
        this.swipeDetected = true
        if (dx < 0) this.next(); else this.prev()
      }
    },

    handleStageClick(e) {
      if (this.swipeDetected) { this.swipeDetected = false; return }
      const ratio = e.clientX / window.innerWidth
      if (ratio < 0.35) this.prev()
      else if (ratio > 0.65) this.next()
      else this.toggleBar()
    },

    toggleBar() {
      this.barVisible = !this.barVisible
      if (this.barVisible) this.resetBarTimer()
    },

    showBar() {
      this.barVisible = true
      this.resetBarTimer()
    },

    resetBarTimer() {
      clearTimeout(this.barTimer)
      this.barTimer = setTimeout(() => { this.barVisible = false }, 4000)
    },

    async retryImage() {
      const pageNum = this.currentPage
      delete this.cache[pageNum]
      const pg = this.pages.find(p => p.pageNum === pageNum)
      if (!pg) return
      let pageUrl = pg.pageUrl
      if (this.nlParam) pageUrl += (pageUrl.includes('?') ? '&' : '?') + `nl=${this.nlParam}`
      this.imageLoading = true
      this.imageError = false
      const id = ++this.loadId
      try {
        const res = await fetch(`${API_BASE}/api/image-url?pageUrl=${encodeURIComponent(pageUrl)}`)
        const data = await res.json()
        if (this.loadId !== id) return
        this.cache[pageNum] = data
        this.nlParam = data.nlParam
        await preloadImage(data.imageUrl)
        if (this.loadId !== id) return
        this.imageUrl = data.imageUrl
        this.imageLoading = false
      } catch {
        if (this.loadId === id) {
          this.imageError = true
          this.imageLoading = false
        }
      }
    },
  },
}
</script>

<style scoped>
.reader-root {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: #0a0f1a;
  display: flex;
  flex-direction: column;
  user-select: none;
}

/* ── Init states ── */
.reader-init {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #94a3b8;
}
.reader-init-error { color: #f87171; }
.reader-init button {
  padding: 8px 20px;
  background: rgba(148,163,184,0.15);
  border: 1px solid rgba(148,163,184,0.2);
  border-radius: 6px;
  color: #f1f5f9;
  cursor: pointer;
}

/* ── Spinner ── */
.reader-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid rgba(148,163,184,0.2);
  border-top-color: #60a5fa;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Top bar ── */
.reader-bar {
  position: relative;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: linear-gradient(to bottom, rgba(0,0,0,0.8), transparent);
  transition: opacity 0.3s;
}
.reader-bar-hidden { opacity: 0; pointer-events: none; }

.reader-back-btn {
  background: none;
  border: none;
  color: #f1f5f9;
  font-size: 14px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  white-space: nowrap;
  flex-shrink: 0;
}
.reader-back-btn:hover { background: rgba(255,255,255,0.1); }

.reader-bar-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  color: #cbd5e1;
}
.reader-bar-counter {
  font-size: 14px;
  color: #94a3b8;
  white-space: nowrap;
  flex-shrink: 0;
}

/* ── Stage ── */
.reader-stage {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  cursor: pointer;
}

.reader-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  display: block;
  pointer-events: none;
}

.reader-img-spinner {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.reader-img-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #f87171;
}
.reader-img-error button {
  padding: 8px 20px;
  background: rgba(248,113,113,0.15);
  border: 1px solid rgba(248,113,113,0.3);
  border-radius: 6px;
  color: #f87171;
  cursor: pointer;
}

/* ── Desktop arrows ── */
.reader-arrow {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 48px;
  height: 80px;
  background: rgba(0,0,0,0.4);
  border: none;
  border-radius: 6px;
  color: #f1f5f9;
  font-size: 28px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.reader-stage:hover .reader-arrow { opacity: 1; }
.reader-arrow:hover { background: rgba(0,0,0,0.65); }
.reader-arrow-left { left: 12px; }
.reader-arrow-right { right: 12px; }

/* ── Mobile bottom bar ── */
.reader-bottom-bar {
  display: none;
  align-items: center;
  justify-content: space-between;
  padding: 10px 24px;
  background: linear-gradient(to top, rgba(0,0,0,0.8), transparent);
  transition: opacity 0.3s;
  color: #94a3b8;
  font-size: 14px;
}
.reader-bottom-btn {
  background: none;
  border: none;
  color: #f1f5f9;
  font-size: 24px;
  padding: 4px 12px;
  cursor: pointer;
  border-radius: 4px;
}
.reader-bottom-btn:disabled { opacity: 0.25; cursor: default; }
.reader-bottom-btn:not(:disabled):hover { background: rgba(255,255,255,0.1); }

/* ── Mobile breakpoint ── */
@media (max-width: 767px) {
  .reader-arrow { display: none; }
  .reader-bottom-bar { display: flex; }
  .reader-bar-title { display: none; }
}
</style>
