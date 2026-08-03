<template>
  <div class="gallery-detail-wrapper">
    <div v-if="galleryData" class="gallery-detail-page">
      <!-- 单一响应式布局：此前桌面/移动两套完整 DOM 同时存在，
           页面里有两个 <h1>、两组标签面板，读屏会把全部内容读两遍 -->
      <section class="gd-hero">
        <div class="gd-cover-panel">
          <div class="cover-shell">
            <img :src="galleryData.thumb || galleryData.image || '/placeholder.png'" :alt="`${getDisplayTitle()} 封面`" />
          </div>
          <div class="cover-meta">
            <span class="category-badge" :class="categoryClass">{{ getDisplayCategory() }}</span>
            <div class="rating-card">
              <span class="rating-label">评分</span>
              <div class="rating-value">
                <Rating :modelValue="galleryData.rating" readonly />
                <span class="rating-score">{{ galleryData.rating ?? "N/A" }}</span>
              </div>
            </div>
            <dl class="cover-info-list">
              <div class="cover-info-row">
                <dt>发布时间</dt>
                <dd>{{ formatDate(galleryData.posted) || "未知" }}</dd>
              </div>
              <div class="cover-info-row">
                <dt>收藏时间</dt>
                <dd>{{ formatFavDate(galleryData.favTime) }}</dd>
              </div>
            </dl>
            <a class="external-link cover-ext-link" :href="externalLink" @click.prevent="openExHentai">在 ExHentai 打开</a>
          </div>
        </div>

        <div class="gd-main">
          <div class="hero-copy">
            <div class="eyebrow">画廊详情</div>
            <h1 class="title">{{ getDisplayTitle() }}</h1>
            <p v-if="galleryData.title_jpn" class="subtitle">{{ galleryData.title_jpn }}</p>
          </div>

          <div class="stats-grid">
            <article v-for="stat in statsCards" :key="stat.label" class="stat-card">
              <span class="stat-label">{{ stat.label }}</span>
              <strong class="stat-value">{{ stat.value }}</strong>
            </article>
          </div>

          <section class="detail-panel tags-panel">
            <div class="panel-header">
              <div>
                <div class="panel-eyebrow">分类标签</div>
                <h2 class="panel-title">Tags</h2>
              </div>
              <div class="language-toggle-wrap">
                <span class="toggle-copy">{{ isChinese ? "中文" : "English" }}</span>
                <ToggleSwitch v-model="isChinese" class="language-toggle" />
              </div>
            </div>
            <p class="tags-hint">点击标签按它检索，右侧 ⧉ 复制搜索语法</p>
            <div class="tags">
              <div v-for="(tags, group) in groupedTags" :key="group" class="tag-group">
                <strong>{{ group }}</strong>
                <div class="tag-list">
                  <span v-for="(tag, index) in tags" :key="index" class="tag-chip">
                    <RouterLink
                      class="tag-chip-main"
                      :to="tagSearchRoute(tag)"
                      :title="`按 ${tag.value} 检索`"
                    >{{ isChinese ? (tag.tag_cn || tag.value) : tag.value }}</RouterLink>
                    <button
                      class="tag-chip-copy"
                      type="button"
                      :aria-label="`复制 ${tag.value} 的搜索语法`"
                      :title="tagCopyValue === tag.tag ? '已复制' : '复制搜索语法'"
                      @click="copyTag(tag)"
                    >{{ tagCopyValue === tag.tag ? '✓' : '⧉' }}</button>
                  </span>
                </div>
              </div>
            </div>
          </section>
        </div>
      </section>

      <section v-if="galleryData.torrents?.length" class="detail-panel torrents-panel">
        <div class="panel-header">
          <div>
            <div class="panel-eyebrow">下载</div>
            <h2 class="panel-title">Torrents</h2>
          </div>
        </div>
        <div class="torrent-table-wrapper">
          <table class="torrent-table">
            <thead>
              <tr>
                <th class="tt-name">名称</th>
                <th class="tt-size">大小</th>
                <th class="tt-tsize">种子体积</th>
                <th class="tt-added">添加时间</th>
                <th class="tt-dl">下载</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(torrent, index) in galleryData.torrents" :key="index">
                <td class="tt-name">{{ torrent.name }}</td>
                <td class="tt-size">{{ formatFileSize(Number(torrent.fsize)) }}</td>
                <td class="tt-tsize">{{ formatFileSize(Number(torrent.tsize)) }}</td>
                <td class="tt-added">{{ formatDate(Number(torrent.added)) }}</td>
                <td class="tt-dl"><a :href="`https://exhentai.org/torrent/${itemId}/${torrent.hash}.torrent`" target="_blank" rel="noreferrer">种子</a></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- ========== Thumbnail Gallery ========== -->
      <section class="thumb-section">
        <div class="panel-header">
          <div>
            <div class="panel-eyebrow">浏览</div>
            <h2 class="panel-title">页面</h2>
          </div>
          <div class="thumb-header-right">
            <span v-if="thumbSource" class="thumb-source-badge" :class="'thumb-source-' + thumbSource" :title="thumbSource === 'exhentai' ? 'ExHentai' : 'E-Hentai'">
              <span class="thumb-source-dot"></span>{{ thumbSource === 'exhentai' ? 'Ex' : 'E' }}
            </span>
            <span v-if="thumbTotal" class="thumb-total-badge">{{ thumbTotal }} 页</span>
            <button
              v-if="thumbExpanded && galleryData?.token"
              class="translate-btn"
              @click="openTranslate"
              title="打开翻译工作台"
            >翻译</button>
          </div>
        </div>

        <!-- Collapsed: load trigger -->
        <button v-if="!thumbExpanded" class="thumb-load-trigger" @click="loadPages">
          <span class="thumb-load-icon">⊞</span>
          <span>加载页面缩略图</span>
          <span class="thumb-load-arrow">›</span>
        </button>

        <!-- Expanded: thumbnail content -->
        <template v-else>
          <div v-if="thumbLoading" class="thumb-loading">
            <div class="thumb-spinner"></div>
            <span>正在获取缩略图…</span>
          </div>
          <div v-else-if="thumbError === 'exhentai_blocked'" class="thumb-exblocked">
            此画廊为 ExHentai 独占，云服务器 IP 被 Cloudflare 拦截，无法加载缩略图
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
              <button :disabled="thumbPage === 0" @click="prevThumbPage" class="thumb-pager-btn">‹</button>
              <span class="thumb-pager-info">{{ thumbPage + 1 }} / {{ thumbTotalPages }}</span>
              <button :disabled="thumbPage >= thumbTotalPages - 1" @click="nextThumbPage" class="thumb-pager-btn">›</button>
            </div>
          </template>
        </template>
      </section>

    </div>

    <div v-else-if="loading" class="loading">加载中…</div>
    <div v-else-if="error" class="error">{{ error }}</div>
  </div>
</template>

<script>
import Rating from "primevue/rating";
import ToggleSwitch from "primevue/toggleswitch";
import { enrichTags, exTypeClassMap } from '@/utils/galleryUtils';
import { loadGalleries, loadTranslations } from '@/composables/useGalleryData';

const baseUrl = import.meta.env.BASE_URL;
const API_BASE = import.meta.env.VITE_API_BASE || 'https://no-hentai.vercel.app';
const THUMBS_PER_PAGE = 20;

export default {
  name: "GalleryDetail",
  components: { Rating, ToggleSwitch },
  data() {
    return {
      itemId: null,
      galleryData: null,
      isChinese: true,
      loading: true,
      error: null,
      // Thumbnails
      thumbImages: [],
      thumbTotal: 0,
      thumbSource: null,
      thumbLoading: false,
      thumbError: null,
      thumbPage: 0,
      thumbExpanded: false,
      tagCopyValue: null,
      tagCopyTimer: null,
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
      this.thumbSource = null;
      this.thumbPage = 0;
      this.thumbError = null;
      this.thumbExpanded = false;
      this.tagCopyValue = null;
      clearTimeout(this.tagCopyTimer);
      this.tagCopyTimer = null;
      this.initializeFromRoute();
      if (this.itemId) this.fetchGalleryData();
    },
  },
  beforeUnmount() {
    clearTimeout(this.tagCopyTimer);
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
          const [dailyGroups, translations] = await Promise.all([
            fetch(`${baseUrl}data/daily_search.json`).then(r => r.json()),
            loadTranslations(),
          ]);
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
            this.galleryData = {
              ...gallery,
              tags: Array.isArray(gallery.tags) ? enrichTags(gallery.tags, translations) : gallery.tags,
            };
          } else {
            this.error = `未找到 ID 为 ${this.itemId} 的画廊`;
          }
          return;
        }

        const [galleries, translations] = await Promise.all([
          loadGalleries(),
          loadTranslations(),
        ]);

        let gallery = galleries.find(item =>
          item.gid && item.gid.toString() === this.itemId.toString()
        );

        if (!gallery) {
          try {
            const dailyGroups = await fetch(`${baseUrl}data/daily_search.json`).then(r => r.json());
            if (Array.isArray(dailyGroups)) {
              for (const group of dailyGroups) {
                const found = (group.galleries || []).find(item =>
                  item.gid && item.gid.toString() === this.itemId.toString()
                );
                if (found) { gallery = found; break; }
              }
            }
          } catch {}
        }

        if (gallery) {
          this.galleryData = {
            ...gallery,
            tags: Array.isArray(gallery.tags) ? enrichTags(gallery.tags, translations) : gallery.tags,
          };
        } else {
          this.error = `未找到 ID 为 ${this.itemId} 的画廊`;
        }
      } catch (error) {
        console.error("Error fetching gallery data:", error);
        this.error = `画廊数据加载失败：${error.message}`;
      } finally {
        this.loading = false;
      }
    },

    getDisplayTitle() {
      return this.galleryData.title || '未知标题';
    },

    getDisplayCategory() {
      return this.galleryData.category || 'Unknown';
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

    /* 标签 → 首页精确检索 */
    tagSearchRoute(tag) {
      return { path: '/', query: { q: `${tag.namespace}:"${tag.value}$"` } };
    },

    async copyTag(tag) {
      if (!tag?.tag) return;
      try {
        await navigator.clipboard.writeText(`${tag.namespace}:"${tag.value}$"`);
        this.tagCopyValue = tag.tag;
        clearTimeout(this.tagCopyTimer);
        this.tagCopyTimer = setTimeout(() => {
          this.tagCopyValue = null;
          this.tagCopyTimer = null;
        }, 1200);
      } catch (error) {
        console.error('Failed to copy tag:', error);
      }
    },

    loadPages() {
      this.thumbExpanded = true;
      this.fetchThumbnails();
    },

    async fetchThumbnails() {
      if (!this.galleryData?.token) return;
      this.thumbLoading = true;
      this.thumbError = null;
      try {
        const res = await fetch(`${API_BASE}/api/gallery-images?gid=${this.itemId}&token=${this.galleryData.token}`);
        const data = await res.json();
        if (data.error === 'exhentai_blocked') {
          this.thumbError = 'exhentai_blocked';
        } else if (data.error) {
          throw new Error(data.error);
        } else {
          this.thumbImages = data.images.slice(0, data.total);
          this.thumbTotal = data.total;
          this.thumbSource = data.source || null;
          // 计算每个 sprite 的数量和最大偏移，用于百分比定位
          const spriteMeta = {};
          for (const img of this.thumbImages) {
            const prev = spriteMeta[img.thumbSprite] || { count: 0, maxOffset: 0 };
            spriteMeta[img.thumbSprite] = {
              count: prev.count + 1,
              maxOffset: Math.max(prev.maxOffset, -img.thumbX),
            };
          }
          for (const img of this.thumbImages) {
            const meta = spriteMeta[img.thumbSprite] || { count: 1, maxOffset: 0 };
            img.spriteN = meta.count;
            img.spriteMaxOffset = meta.maxOffset;
          }
        }
      } catch (e) {
        this.thumbError = e.message;
      } finally {
        this.thumbLoading = false;
      }
    },

    prevThumbPage() { this.thumbPage-- },
    nextThumbPage() { this.thumbPage++ },

    openExHentai() {
      if (/Android/i.test(navigator.userAgent)) {
        window.location.href = this.externalLink;
      } else {
        window.open(this.externalLink, '_blank', 'noreferrer');
      }
    },

    openReader(pageNum) {
      this.$router.push({
        name: 'GalleryReader',
        params: { gid: this.itemId },
        query: { page: pageNum, token: this.galleryData.token },
      });
    },

    openTranslate() {
      this.$router.push({
        name: 'GalleryTranslate',
        params: { gid: this.itemId },
        query: { token: this.galleryData.token, page: 1 },
      });
    },

    cellStyle(img) {
      return { aspectRatio: `${img.thumbW} / ${img.thumbH}` };
    },

    innerStyle(img) {
      const N = img.spriteN || 1;
      const maxOffset = img.spriteMaxOffset || 0;
      const posX = maxOffset > 0 ? (-img.thumbX / maxOffset) * 100 : 0;
      return {
        backgroundImage: `url(${img.thumbSprite})`,
        backgroundSize: `${N * 100}% auto`,
        backgroundPosition: `${posX}% 0`,
        backgroundRepeat: 'no-repeat',
        width: '100%',
        height: '100%',
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
      return exTypeClassMap[this.getDisplayCategory()] || 'default';
    },
    statsCards() {
      return [
        { label: '页数', value: `${this.galleryData?.filecount || 0} 页` },
        { label: '文件体积', value: this.formatFileSize(this.galleryData?.filesize || 0) },
        { label: '收藏夹', value: this.galleryData?.favCategory || '未分类' },
        { label: '上传者', value: this.galleryData?.uploader || '未知' },
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
