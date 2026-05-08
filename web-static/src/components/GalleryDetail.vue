<template>
  <div class="gallery-detail-wrapper">
    <div v-if="galleryData" class="gallery-detail-page">

      <!-- ========== Desktop Layout (≥720px) ========== -->
      <div class="layout-desktop">
        <section class="gallery-detail-hero">
          <div class="hero-copy">
            <div class="eyebrow">Gallery Detail</div>
            <h1 class="title">{{ getDisplayTitle() }}</h1>
            <p v-if="galleryData.title_jpn" class="subtitle">{{ galleryData.title_jpn }}</p>
          </div>

          <div class="cover-panel">
            <div class="cover-shell">
              <img :src="galleryData.thumb || galleryData.image || '/placeholder.png'" alt="Cover" />
            </div>
            <div class="cover-meta">
              <span class="category-badge" :class="categoryClass">{{ getDisplayCategory() }}</span>
              <div class="rating-card">
                <span class="rating-label">Rating</span>
                <div class="rating-value">
                  <Rating :modelValue="galleryData.rating" readonly />
                  <span class="rating-score">{{ galleryData.rating ?? "N/A" }}</span>
                </div>
              </div>
              <dl class="cover-info-list">
                <div class="cover-info-row">
                  <dt>Posted</dt>
                  <dd>{{ formatDate(galleryData.posted) || "Unknown" }}</dd>
                </div>
                <div class="cover-info-row">
                  <dt>Fav Time</dt>
                  <dd>{{ formatFavDate(galleryData.favTime) }}</dd>
                </div>
              </dl>
              <a class="external-link cover-ext-link" :href="externalLink" target="_blank" rel="noreferrer">Open ExHentai</a>
            </div>
          </div>

          <div class="hero-main">
            <div class="stats-grid">
              <article v-for="stat in statsCards" :key="stat.label" class="stat-card">
                <span class="stat-label">{{ stat.label }}</span>
                <strong class="stat-value">{{ stat.value }}</strong>
              </article>
            </div>
            <div class="detail-grid">
              <section class="detail-panel tags-panel">
                <div class="panel-header">
                  <div>
                    <div class="panel-eyebrow">Taxonomy</div>
                    <h2 class="panel-title">Tags</h2>
                  </div>
                  <div class="language-toggle-wrap">
                    <span class="toggle-copy">{{ isChinese ? "中文" : "English" }}</span>
                    <ToggleSwitch v-model="isChinese" :onLabel="'中文'" :offLabel="'英文'" class="language-toggle" />
                  </div>
                </div>
                <div class="tags">
                  <div v-for="(tags, group) in groupedTags" :key="group" class="tag-group">
                    <strong>{{ group }}</strong>
                    <div class="tag-list">
                      <Tag v-for="(tag, index) in tags" :key="index"
                        :value="isChinese ? (tag.tag_cn || tag.value) : tag.value"
                        class="tag" severity="secondary" />
                    </div>
                  </div>
                </div>
              </section>
            </div>
          </div>
        </section>

        <section v-if="galleryData.torrents?.length" class="detail-panel torrents-panel">
          <div class="panel-header">
            <div>
              <div class="panel-eyebrow">Downloads</div>
              <h2 class="panel-title">Torrent Downloads</h2>
            </div>
          </div>
          <div class="torrent-table-wrapper">
            <table class="torrent-table">
              <thead>
                <tr>
                  <th style="width:40%">Name</th>
                  <th style="width:15%">Size</th>
                  <th style="width:15%">Torrent Size</th>
                  <th style="width:15%">Added</th>
                  <th style="width:15%">Download</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(torrent, index) in galleryData.torrents" :key="index">
                  <td>{{ torrent.name }}</td>
                  <td>{{ formatFileSize(Number(torrent.fsize)) }}</td>
                  <td>{{ formatFileSize(Number(torrent.tsize)) }}</td>
                  <td>{{ formatDate(Number(torrent.added)) }}</td>
                  <td><a :href="`https://exhentai.org/torrent/${itemId}/${torrent.hash}.torrent`" target="_blank" rel="noreferrer">Torrent</a></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <!-- ========== Mobile Layout (<720px) ========== -->
      <div class="layout-mobile">
        <!-- 封面 -->
        <div class="mob-cover">
          <img :src="galleryData.thumb || galleryData.image || '/placeholder.png'" alt="Cover" />
        </div>

        <!-- 标题区 -->
        <div class="mob-header">
          <span class="category-badge" :class="categoryClass">{{ getDisplayCategory() }}</span>
          <h1 class="mob-title">{{ getDisplayTitle() }}</h1>
          <p v-if="galleryData.title_jpn" class="mob-subtitle">{{ galleryData.title_jpn }}</p>
        </div>

        <!-- 评分 + 按钮 -->
        <div class="mob-quick">
          <div class="mob-rating">
            <Rating :modelValue="galleryData.rating" readonly />
            <span class="mob-score">{{ galleryData.rating ?? "N/A" }}</span>
          </div>
          <a class="external-link" :href="externalLink" target="_blank" rel="noreferrer">Open ExHentai</a>
        </div>

        <!-- 基础信息 -->
        <dl class="mob-info-list">
          <div class="mob-info-row">
            <dt>Posted</dt>
            <dd>{{ formatDate(galleryData.posted) || "Unknown" }}</dd>
          </div>
          <div class="mob-info-row">
            <dt>Fav Time</dt>
            <dd>{{ formatFavDate(galleryData.favTime) }}</dd>
          </div>
        </dl>

        <!-- 统计卡片 -->
        <div class="mob-stats">
          <article v-for="stat in statsCards" :key="stat.label" class="mob-stat-card">
            <span class="stat-label">{{ stat.label }}</span>
            <strong class="stat-value">{{ stat.value }}</strong>
          </article>
        </div>

        <!-- 标签 -->
        <div class="detail-panel mob-tags-panel">
          <div class="panel-header">
            <div>
              <div class="panel-eyebrow">Taxonomy</div>
              <h2 class="panel-title">Tags</h2>
            </div>
            <div class="language-toggle-wrap">
              <span class="toggle-copy">{{ isChinese ? "中文" : "English" }}</span>
              <ToggleSwitch v-model="isChinese" :onLabel="'中文'" :offLabel="'英文'" class="language-toggle" />
            </div>
          </div>
          <div class="tags">
            <div v-for="(tags, group) in groupedTags" :key="group" class="tag-group mob-tag-group">
              <strong>{{ group }}</strong>
              <div class="tag-list">
                <Tag v-for="(tag, index) in tags" :key="index"
                  :value="isChinese ? (tag.tag_cn || tag.value) : tag.value"
                  class="tag" severity="secondary" />
              </div>
            </div>
          </div>
        </div>

        <!-- Torrents -->
        <section v-if="galleryData.torrents?.length" class="detail-panel torrents-panel">
          <div class="panel-header">
            <div>
              <div class="panel-eyebrow">Downloads</div>
              <h2 class="panel-title">Torrent Downloads</h2>
            </div>
          </div>
          <div class="torrent-table-wrapper">
            <table class="torrent-table">
              <thead>
                <tr>
                  <th>Name</th><th>Size</th><th>Download</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(torrent, index) in galleryData.torrents" :key="index">
                  <td>{{ torrent.name }}</td>
                  <td>{{ formatFileSize(Number(torrent.fsize)) }}</td>
                  <td><a :href="`https://exhentai.org/torrent/${itemId}/${torrent.hash}.torrent`" target="_blank" rel="noreferrer">Torrent</a></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <!-- ========== Thumbnail Gallery ========== -->
      <section class="thumb-section">
        <div class="panel-header">
          <div>
            <div class="panel-eyebrow">Browse</div>
            <h2 class="panel-title">Pages</h2>
          </div>
          <span v-if="thumbTotal" class="thumb-total-badge">{{ thumbTotal }} pages</span>
        </div>

        <div v-if="thumbLoading" class="thumb-loading">
          <div class="thumb-spinner"></div>
          <span>Loading thumbnails...</span>
        </div>
        <div v-else-if="thumbError" class="thumb-error">{{ thumbError }}</div>
        <template v-else-if="thumbImages.length">
          <div class="thumb-grid">
            <div
              v-for="img in pagedThumbs"
              :key="img.pageNum"
              class="thumb-cell"
              :style="cellStyle(img)"
              :title="`Page ${img.pageNum}`"
              @click="openReader(img.pageNum)"
            >
              <div class="thumb-inner" :style="innerStyle(img)"></div>
              <span class="thumb-page-num">{{ img.pageNum }}</span>
            </div>
          </div>
          <div v-if="thumbTotalPages > 1" class="thumb-paginator">
            <button :disabled="thumbPage === 0" @click="thumbPage--" class="thumb-pager-btn">‹</button>
            <span class="thumb-pager-info">{{ thumbPage + 1 }} / {{ thumbTotalPages }}</span>
            <button :disabled="thumbPage >= thumbTotalPages - 1" @click="thumbPage++" class="thumb-pager-btn">›</button>
          </div>
        </template>
      </section>

    </div>

    <div v-else-if="loading" class="loading">Loading...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
  </div>
</template>

<script>
import Tag from "primevue/tag";
import Rating from "primevue/rating";
import ToggleSwitch from "primevue/toggleswitch";

const baseUrl = import.meta.env.BASE_URL;
const API_BASE = import.meta.env.VITE_API_BASE || 'https://no-hentai.vercel.app';
const THUMBS_PER_PAGE = 20;
const THUMB_DISPLAY_W = 88;

export default {
  name: "GalleryDetail",
  components: { Tag, Rating, ToggleSwitch },
  data() {
    return {
      itemId: null,
      galleryData: null,
      isChinese: true,
      loading: true,
      error: null,
      allGalleries: [],
      translationData: null,
      // Thumbnails
      thumbImages: [],
      thumbTotal: 0,
      thumbLoading: false,
      thumbError: null,
      thumbPage: 0,
    };
  },
  created() {
    this.initializeFromRoute();
    if (this.itemId) {
      this.fetchGalleryData();
    }
  },
  watch: {
    '$route'() {
      this.thumbImages = [];
      this.thumbTotal = 0;
      this.thumbPage = 0;
      this.thumbError = null;
      this.initializeFromRoute();
      if (this.itemId) this.fetchGalleryData();
    },
    galleryData(val) {
      if (val?.token) this.fetchThumbnails();
    },
  },
  methods: {
    initializeFromRoute() {
      const params = this.$route.params;
      this.itemId = params.gid;
    },

    async fetchGalleryData() {
      this.loading = true;
      this.error = null;

      try {
        const source = this.$route.query.source;

        if (source === 'daily') {
          const [dailyResponse, translationsResponse] = await Promise.all([
            fetch(`${baseUrl}data/daily_search.json`),
            fetch(`${baseUrl}data/translations.json`),
          ]);
          this.translationData = await translationsResponse.json();
          const dailyGroups = await dailyResponse.json();
          let gallery = null;
          if (Array.isArray(dailyGroups)) {
            for (const group of dailyGroups) {
              const found = (group.galleries || []).find(item =>
                item.gid && item.gid.toString() === this.itemId.toString()
              );
              if (found) { gallery = found; break; }
            }
          }
          if (gallery) {
            const processedGallery = { ...gallery };
            if (Array.isArray(gallery.tags)) {
              processedGallery.tags = this.enrichTags(gallery.tags);
            }
            this.galleryData = processedGallery;
          } else {
            this.error = `Gallery with ID ${this.itemId} not found`;
          }
          return;
        }

        const [galleriesResponse, translationsResponse, dailyResponse] = await Promise.all([
          fetch(`${baseUrl}data/galleries.json`),
          fetch(`${baseUrl}data/translations.json`),
          fetch(`${baseUrl}data/daily_search.json`),
        ]);

        this.allGalleries = await galleriesResponse.json();
        this.translationData = await translationsResponse.json();

        let gallery = this.allGalleries.find(item =>
          item.gid && item.gid.toString() === this.itemId.toString()
        );

        if (!gallery && dailyResponse.ok) {
          const dailyGroups = await dailyResponse.json();
          if (Array.isArray(dailyGroups)) {
            for (const group of dailyGroups) {
              const found = (group.galleries || []).find(item =>
                item.gid && item.gid.toString() === this.itemId.toString()
              );
              if (found) { gallery = found; break; }
            }
          }
        }

        if (gallery) {
          const processedGallery = { ...gallery };
          if (Array.isArray(gallery.tags)) {
            processedGallery.tags = this.enrichTags(gallery.tags);
          }
          this.galleryData = processedGallery;
        } else {
          this.error = `Gallery with ID ${this.itemId} not found`;
        }
      } catch (error) {
        console.error("Error fetching gallery data:", error);
        this.error = `Failed to load gallery data: ${error.message}`;
      } finally {
        this.loading = false;
      }
    },

    enrichTags(tags) {
      if (!this.translationData || !Array.isArray(tags)) return [];

      const enrichedTags = [];
      for (const tag of tags) {
        if (typeof tag !== 'string' || !tag.includes(':')) continue;

        const [namespace, value] = tag.split(':', 2);
        try {
          const tagDetail = this.translationData.data
            .find(item => item.namespace === namespace)?.data?.[value];

          enrichedTags.push({
            tag: tag,
            namespace: namespace,
            value: value,
            tag_cn: tagDetail?.name || '',
            intro: tagDetail?.intro || '',
            links: tagDetail?.links || ''
          });
        } catch {
          continue;
        }
      }
      return enrichedTags;
    },

    getDisplayTitle() {
      return this.galleryData.title || 'Unknown Title';
    },

    getDisplayCategory() {
      return this.galleryData.category || 'Unknown Category';
    },

    formatDate(timestamp) {
      if (!timestamp) return '';
      const date = new Date(timestamp * 1000);
      return date.toISOString().slice(0, 10);
    },

    formatFavDate(value) {
      if (!value) return 'Unknown';
      const str = String(value);
      const match = str.match(/\d{4}-\d{2}-\d{2}/);
      return match ? match[0] : str;
    },

    async fetchThumbnails() {
      if (!this.galleryData?.token) return;
      this.thumbLoading = true;
      this.thumbError = null;
      try {
        const res = await fetch(`${API_BASE}/api/gallery-images?gid=${this.itemId}&token=${this.galleryData.token}`);
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        this.thumbImages = data.images.slice(0, data.total);
        this.thumbTotal = data.total;
      } catch (e) {
        this.thumbError = e.message;
      } finally {
        this.thumbLoading = false;
      }
    },

    openReader(pageNum) {
      this.$router.push({
        name: 'GalleryReader',
        params: { gid: this.itemId },
        query: { page: pageNum, token: this.galleryData.token },
      });
    },

    cellStyle(img) {
      const scale = THUMB_DISPLAY_W / img.thumbW;
      const displayH = Math.round(img.thumbH * scale);
      return { width: THUMB_DISPLAY_W + 'px', height: displayH + 'px' };
    },

    innerStyle(img) {
      const scale = THUMB_DISPLAY_W / img.thumbW;
      return {
        width: img.thumbW + 'px',
        height: img.thumbH + 'px',
        backgroundImage: `url(${img.thumbSprite})`,
        backgroundPosition: `${img.thumbX}px 0`,
        backgroundRepeat: 'no-repeat',
        transform: `scale(${scale})`,
        transformOrigin: 'top left',
      };
    },

    formatFileSize(bytes) {
      if (!bytes) return "0 B";
      const sizes = ["B", "KB", "MB", "GB", "TB"];
      const i = Math.floor(Math.log(bytes) / Math.log(1024));
      return (bytes / Math.pow(1024, i)).toFixed(2) + " " + sizes[i];
    },
  },
  computed: {
    externalLink() {
      return `https://exhentai.org/g/${this.itemId}/${this.galleryData?.token || ''}`;
    },
    categoryClass() {
      const map = {
        'Doujinshi': 'red',
        'Manga': 'orange',
        'Artist CG': 'yellow',
        'Game CG': 'green',
        'Western': 'gold',
        'Non-H': 'lightblue',
        'Image Set': 'blue',
        'Cosplay': 'purple',
        'Asian Porn': 'pink',
        'Misc': 'gray',
      };
      return map[this.getDisplayCategory()] || 'default';
    },
    statsCards() {
      return [
        { label: 'Length', value: `${this.galleryData?.filecount || 0} pages` },
        { label: 'File Size', value: this.formatFileSize(this.galleryData?.filesize || 0) },
        { label: 'Favorite Category', value: this.galleryData?.favCategory || 'Unknown' },
        { label: 'Uploader', value: this.galleryData?.uploader || 'Unknown' },
      ];
    },
    pagedThumbs() {
      const start = this.thumbPage * THUMBS_PER_PAGE;
      return this.thumbImages.slice(start, start + THUMBS_PER_PAGE);
    },
    thumbTotalPages() {
      return Math.ceil(this.thumbImages.length / THUMBS_PER_PAGE);
    },
    groupedTags() {
      if (!this.galleryData?.tags) {
        return {};
      }

      const groups = {
        language: [],
        artist: [],
        group: [],
        female: [],
        male: [],
        mixed: [],
        other: [],
        cosplayer: [],
        parody: [],
        character: [],
        other_tags: [],
      };

      this.galleryData.tags.forEach(tag => {
        const ns = tag.namespace?.toLowerCase() || 'other_tags';
        (groups[ns] ?? groups.other_tags).push(tag);
      });

      return Object.fromEntries(Object.entries(groups).filter(([, v]) => v.length > 0));
    },
  },
};
</script>

<style src="../assets/GalleryDetail.css"></style>
