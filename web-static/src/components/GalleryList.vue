<script setup>
import Rating from 'primevue/rating'
import { useViewMode } from '@/composables/useViewMode'

defineProps({
  items: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  emptyText: { type: String, default: 'No data' },
})
defineEmits(['click'])

const { viewMode } = useViewMode()
</script>

<template>
  <!-- Cover mode -->
  <div v-if="viewMode === 'cover'" class="vm-cover-grid">
    <div v-if="loading" class="empty-state" style="grid-column:1/-1">Loading…</div>
    <div v-else-if="!items.length" class="empty-state" style="grid-column:1/-1">{{ emptyText }}</div>
    <div
      v-else
      v-for="item in items"
      :key="item.key"
      class="vm-cover-card"
      @click="$emit('click', item)"
    >
      <div class="vm-cover-img">
        <img v-if="item.thumb" :src="item.thumb" loading="lazy" />
        <div v-else class="vm-cover-placeholder">{{ item.title?.[0] }}</div>
      </div>
      <div class="vm-cover-info">
        <div v-if="item.badge" class="vm-cover-meta">
          <span class="gr-badge" :class="item.badgeClass">{{ item.badge }}</span>
          <span v-if="item.pages" class="vm-cover-pages">{{ item.pages }}</span>
        </div>
        <div v-if="item.refId" class="vm-cover-id">{{ item.refId }}</div>
        <div class="vm-cover-title">{{ item.title }}</div>
      </div>
    </div>
  </div>

  <!-- Card mode -->
  <div v-else class="gallery-list">
    <div v-if="loading" class="empty-state">Loading…</div>
    <div v-else-if="!items.length" class="empty-state">{{ emptyText }}</div>
    <article
      v-else
      v-for="item in items"
      :key="item.key"
      class="gallery-row"
      @click="$emit('click', item)"
    >
      <div class="gr-thumb">
        <img v-if="item.thumb" :src="item.thumb" loading="lazy" />
        <div v-else class="gr-thumb-placeholder">{{ item.title?.[0] }}</div>
      </div>
      <div class="gr-body">
        <template v-if="!item.noMeta">
          <div class="gr-top">
            <span v-if="item.badge" class="gr-badge" :class="item.badgeClass">{{ item.badge }}</span>
            <span class="gr-title">{{ item.title }}</span>
          </div>
          <div v-if="item.tags.length" class="gr-tags">
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
        <div v-else>
          <div class="gr-top">
            <span class="gr-title">{{ item.title }}</span>
          </div>
          <div class="vm-card-empty">
            <span>{{ item.noMetaText }}</span>
            <span v-if="item.refId" class="vm-card-id">{{ item.refId }}</span>
          </div>
        </div>
      </div>
    </article>
  </div>
</template>
