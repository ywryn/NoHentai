<template>
  <div class="gallery-detail-wrapper">
    <div v-if="galleryData" class="gallery-detail-container">
    <!-- 数据源指示器已移除 -->

    <!-- 左侧封面 -->
    <div class="cover">
      <img :src="galleryData.thumb || galleryData.image || '/placeholder.png'" alt="Cover" />
      <div class="category">
        <span>{{ getDisplayCategory() }}</span>
      </div>
    </div>

    <!-- 右侧信息 -->
    <div class="details">
      <h3 class="title">
        {{ getDisplayTitle() }}
        <br />
        <small v-if="galleryData.title_jpn">{{ galleryData.title_jpn }}</small>
      </h3>

      <div class="info-tags">
        <!-- EX 数据信息列表 -->
        <ul v-if="provider === 'ex'" class="info-list">
          <li><strong>Uploader:</strong> {{ galleryData.uploader }}</li>
          <li><strong>Posted:</strong> {{ formatDate(galleryData.posted) }}</li>
          <li><strong>File Size:</strong> {{ formatFileSize(galleryData.filesize) }}</li>
          <li><strong>Length:</strong> {{ galleryData.filecount }} pages</li>
          <li>
            <strong>Rating:</strong>
            <span style="display:inline-flex;align-items:center;">
              <Rating v-model="galleryData.rating" readonly style="margin: 0 10px;" />
              {{ galleryData.rating }}
            </span>
          </li>
          <li>
            <strong>Link:</strong>
            <a :href="`https://exhentai.org/g/${itemId}/${galleryData.token}`" target="_blank">
              https://exhentai.org/g/{{ itemId }}/{{ galleryData.token }}
            </a>
          </li>
        </ul>


        <Divider layout="vertical" class="detail-separator" />

        <!-- EX Tags -->
        <div v-if="provider === 'ex'" class="tags">
          <ToggleSwitch v-model="isChinese" :onLabel="'中文'" :offLabel="'英文'" class="language-toggle" />
          <div v-for="(tags, group) in groupedTags" :key="group" class="tag-group">
            <strong>{{ group }}</strong>:
            <Tag
              v-for="(tag, index) in tags"
              :key="index"
              :value="isChinese ? (tag.tag_cn || tag.value) : tag.value"
              class="tag"
              severity="secondary"
            />
          </div>
        </div>

      </div>
    </div>
    </div>

    <!-- EX Torrents Section -->
  <section v-if="provider === 'ex' && galleryData.torrents?.length" class="torrents">
    <h4>Torrent Downloads</h4>
    <div class="torrent-table-wrapper">
      <table class="torrent-table">
        <thead>
          <tr>
            <th style="width: 40%;">Name</th>
            <th style="width: 15%;">Size</th>
            <th style="width: 15%;">Torrent Size</th>
            <th style="width: 15%;">Added</th>
            <th style="width: 15%;">Torrent Download</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(torrent, index) in galleryData.torrents" :key="index">
            <td>{{ torrent.name }}</td>
            <td>{{ formatFileSize(Number(torrent.fsize)) }}</td>
            <td>{{ formatFileSize(Number(torrent.tsize)) }}</td>
            <td>{{ formatDate(Number(torrent.added)) }}</td>
            <td>
              <a :href="`https://exhentai.org/torrent/${itemId}/${torrent.hash}.torrent`" target="_blank">Torrent</a>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>


  <!-- 静态版本移除 Gallery Preview 部分 -->
  <!-- <section class="thumbnail-gallery">
    <h4>Gallery Preview</h4>
    <p class="preview-disabled">静态版本暂不支持图片预览功能</p>
  </section> -->
    <div v-else-if="loading" class="loading">Loading...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
  </div>
</template>

<script>
import Divider from "primevue/divider";
import Tag from "primevue/tag";
import Rating from "primevue/rating";
import ToggleSwitch from "primevue/toggleswitch";

export default {
  name: "GalleryDetail",
  components: { Divider, Tag, Rating, ToggleSwitch },
  data() {
    return {
      itemId: null,
provider: 'ex', // 只支持ExHentai数据源
      galleryData: null,
      isChinese: true,
      loading: true,
      error: null,
      // 静态版本移除缩略图相关数据
      allGalleries: [], // 存储所有画廊数据
      translationData: null, // 标签翻译数据
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
      this.initializeFromRoute();
      if (this.itemId) {
        this.fetchGalleryData();
      }
    }
  },
  methods: {
    initializeFromRoute() {
      // 只支持ExHentai路由格式：/gallery/:gid
      const params = this.$route.params;
      
      this.provider = 'ex';
      this.itemId = params.gid;
    },

    async fetchGalleryData() {
      this.loading = true;
      this.error = null;
      
      try {
        // 加载静态 JSON 数据
        const [galleriesResponse, translationsResponse] = await Promise.all([
          fetch('/data/galleries.json'),
          fetch('/data/translations.json')
        ]);
        
        this.allGalleries = await galleriesResponse.json();
        this.translationData = await translationsResponse.json();
        
        // 查找对应的画廊数据
        const gallery = this.allGalleries.find(item => 
          item.gid && item.gid.toString() === this.itemId.toString()
        );
        
        if (gallery) {
          // 处理标签翻译
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
    
    // 标签翻译函数
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
        } catch (error) {
          // 解析错误，跳过该标签
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
      const date = new Date(timestamp * 1000);
      return date.toISOString().replace("T", " ").split(".")[0];
    },


    formatFileSize(bytes) {
      if (bytes === 0) return "0 B";
      const sizes = ["B", "KB", "MB", "GB", "TB"];
      const i = Math.floor(Math.log(bytes) / Math.log(1024));
      return (bytes / Math.pow(1024, i)).toFixed(2) + " " + sizes[i];
    },

    formatNumber(num) {
      if (!num) return '0';
      return parseInt(num).toLocaleString();
    },

    // 静态版本移除缩略图相关方法
    // loadThumbnails, openReader, handlePageJump 等方法已移除


  },
  computed: {
    groupedTags() {
      if (this.provider !== 'ex' || !this.galleryData?.tags) {
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

    // 静态版本移除分页相关计算属性
    // visiblePageLinks, hasMorePages 已移除
  },
};
</script>

<style src="../assets/GalleryDetail.css"></style>
