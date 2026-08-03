<script setup>
import Rating from 'primevue/rating'
import { RouterLink } from 'vue-router'
import { useViewMode } from '@/composables/useViewMode'

defineProps({
  items: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  emptyText: { type: String, default: '没有匹配的结果' },
  emptyHint: { type: String, default: '' },
  /** 骨架屏条数，与每页条数接近可避免加载完成时的高度跳动 */
  skeletonCount: { type: Number, default: 8 },
})

defineEmits(['click'])

const { viewMode } = useViewMode()

function titleChar(title) {
  if (!title) return ''
  const m = title.match(/[a-zA-Z぀-ヿ㐀-鿿豈-﫿가-힯]/)
  return m ? m[0].toUpperCase() : title[0]
}

/**
 * 条目本质是导航，必须渲染成真链接：
 * 键盘可 Tab 可达、支持 Cmd/中键新标签页打开、悬停显示目标地址。
 * 只有「无匹配元数据」这类不可导航的条目才退回 button。
 */
function tagOf(item) {
  return item.to ? RouterLink : 'button'
}
</script>

<template>
  <!-- ── 封面模式 ─────────────────────────────────────────── -->
  <div v-if="viewMode === 'cover'" class="vm-cover-grid">
    <template v-if="loading">
      <div v-for="n in skeletonCount" :key="`sk${n}`" class="vm-cover-card sk-card" aria-hidden="true">
        <div class="vm-cover-img sk-shimmer"></div>
        <div class="vm-cover-info">
          <div class="sk-shimmer sk-line" style="width: 40%"></div>
          <div class="sk-shimmer sk-line" style="width: 90%"></div>
        </div>
      </div>
    </template>

    <div v-else-if="!items.length" class="empty-state" style="grid-column: 1 / -1">
      <p class="empty-title">{{ emptyText }}</p>
      <p v-if="emptyHint" class="empty-hint">{{ emptyHint }}</p>
    </div>

    <component
      :is="tagOf(item)"
      v-else
      v-for="item in items"
      :key="item.key"
      :to="item.to"
      :type="item.to ? undefined : 'button'"
      class="vm-cover-card"
      @click="$emit('click', item)"
    >
      <div class="vm-cover-img">
        <img v-if="item.thumb" :src="item.thumb" :alt="item.title" loading="lazy" decoding="async" />
        <div v-else class="vm-cover-placeholder" aria-hidden="true">{{ titleChar(item.title) }}</div>
      </div>
      <div class="vm-cover-info">
        <div v-if="item.badge || item.pages" class="vm-cover-meta">
          <span v-if="item.badge" class="gr-badge" :class="item.badgeClass">{{ item.badge }}</span>
          <span v-if="item.pages" class="vm-cover-pages">{{ item.pages }}</span>
        </div>
        <div v-if="item.refId" class="vm-cover-id">{{ item.refId }}</div>
        <div class="vm-cover-title">{{ item.title }}</div>
        <div v-if="item.rating != null || item.date" class="vm-cover-sub">
          <Rating v-if="item.rating != null" :modelValue="item.rating" readonly class="gr-rating" />
          <span v-if="item.date" class="vm-cover-date">{{ item.date }}</span>
        </div>
      </div>
    </component>
  </div>

  <!-- ── 卡片模式 ─────────────────────────────────────────── -->
  <div v-else class="gallery-list">
    <template v-if="loading">
      <div v-for="n in skeletonCount" :key="`sk${n}`" class="gallery-row sk-card" aria-hidden="true">
        <div class="gr-thumb sk-shimmer"></div>
        <div class="gr-body">
          <div class="sk-shimmer sk-line" style="width: 65%"></div>
          <div class="sk-shimmer sk-line" style="width: 42%; height: 8px"></div>
          <div class="sk-shimmer sk-line" style="width: 28%; height: 8px"></div>
        </div>
      </div>
    </template>

    <div v-else-if="!items.length" class="empty-state">
      <p class="empty-title">{{ emptyText }}</p>
      <p v-if="emptyHint" class="empty-hint">{{ emptyHint }}</p>
    </div>

    <component
      :is="tagOf(item)"
      v-else
      v-for="item in items"
      :key="item.key"
      :to="item.to"
      :type="item.to ? undefined : 'button'"
      class="gallery-row"
      @click="$emit('click', item)"
    >
      <div class="gr-thumb">
        <img v-if="item.thumb" :src="item.thumb" :alt="item.title" loading="lazy" decoding="async" />
        <div v-else class="gr-thumb-placeholder" aria-hidden="true">{{ titleChar(item.title) }}</div>
      </div>
      <div class="gr-body">
        <template v-if="!item.noMeta">
          <div class="gr-top">
            <span v-if="item.badge" class="gr-badge" :class="item.badgeClass">{{ item.badge }}</span>
            <span class="gr-title">{{ item.title }}</span>
          </div>
          <!-- 标签行单行渐隐截断，用 title 让被截断的部分仍可读 -->
          <div v-if="item.tags.length" class="gr-tags" :title="item.tags.join(' · ')">
            <span v-for="tag in item.tags" :key="tag" class="gr-tag">{{ tag }}</span>
          </div>
          <div class="gr-meta">
            <Rating v-if="item.rating != null" :modelValue="item.rating" readonly class="gr-rating" />
            <span v-if="item.pages" class="gr-pages">{{ item.pages }}</span>
            <span v-if="item.date" class="gr-date">{{ item.date }}</span>
            <span v-if="item.fav" class="gr-fav">♥ {{ item.fav }}</span>
            <span v-if="item.refId" class="gr-ref-id">{{ item.refId }}</span>
          </div>
        </template>
        <template v-else>
          <div class="gr-top">
            <span class="gr-title">{{ item.title }}</span>
          </div>
          <div class="vm-card-empty">
            <span>{{ item.noMetaText }}</span>
            <span v-if="item.refId" class="vm-card-id">{{ item.refId }}</span>
          </div>
        </template>
      </div>
    </component>
  </div>
</template>

<style scoped>
/* 骨架条目不响应指针，避免加载期误触 */
.sk-card {
  pointer-events: none;
  cursor: default;
}

.sk-card .gr-body,
.sk-card .vm-cover-info {
  gap: 7px;
  padding-top: 3px;
}

.empty-title {
  margin: 0;
  font-size: 14px;
  color: var(--title-color);
}

.empty-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--muted-color);
}

/* 封面模式补齐评分与日期，与卡片模式呈现同一批信息 */
.vm-cover-sub {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
}

.vm-cover-date {
  font-size: 10px;
  color: var(--muted-color);
  margin-left: auto;
}
</style>
