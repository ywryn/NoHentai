<script setup>
import { computed } from 'vue'

/**
 * 命名空间标签排行表。
 *
 * 原实现把「原始英文标签 / 中文翻译 / 标签介绍」全塞进 v-tooltip，
 * 触屏设备完全拿不到这些信息 —— 移动端用户看到的只是一列没有解释的
 * 中文词。这里把原始标签直接排进第二行常显，介绍改为可展开，
 * 并让整行成为跳回首页按该标签搜索的入口。
 */
const props = defineProps({
  namespace: { type: String, required: true },
  title: { type: String, required: true },
  rows: { type: Array, default: () => [] },
})

const items = computed(() =>
  props.rows.map(row => {
    const bare = row.tag.replace(new RegExp(`^${props.namespace}:`), '')
    return {
      key: row.tag,
      label: row.tag_cn || bare,
      original: bare,
      /* 有翻译时才需要额外显示原文，否则重复 */
      showOriginal: Boolean(row.tag_cn) && row.tag_cn !== bare,
      intro: row.intro || '',
      count: row.count,
      to: { path: '/', query: { q: `${props.namespace}:"${bare}$"` } },
    }
  })
)

const maxCount = computed(() => Math.max(1, ...items.value.map(i => i.count)))
</script>

<template>
  <section class="data-panel bottom-section">
    <div class="panel-header">
      <div>
        <div class="panel-eyebrow">命名空间</div>
        <h2 class="section-title">{{ title }}</h2>
      </div>
    </div>

    <ul class="tag-rank-list">
      <li v-for="item in items" :key="item.key">
        <RouterLink class="tag-rank-row" :to="item.to" :title="item.intro || undefined">
          <span class="tag-rank-body">
            <span class="tag-rank-label">{{ item.label }}</span>
            <span v-if="item.showOriginal" class="tag-rank-original">{{ item.original }}</span>
          </span>
          <span class="tag-rank-count">{{ item.count }}</span>
          <!-- 占比条：让排行的量级差异不必逐个读数字 -->
          <span class="tag-rank-bar" :style="{ width: `${(item.count / maxCount) * 100}%` }" aria-hidden="true"></span>
        </RouterLink>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.tag-rank-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.tag-rank-row {
  position: relative;
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 7px 10px;
  border-radius: var(--radius-sm);
  text-decoration: none;
  color: inherit;
  overflow: hidden;
  min-height: var(--tap-target);
  box-sizing: border-box;
  transition: background-color var(--dur-fast) var(--ease-out);
}

.tag-rank-row:hover {
  background: var(--row-hover-bg);
  color: inherit;
}

.tag-rank-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
  align-self: center;
}

.tag-rank-label {
  font-size: 13px;
  color: var(--title-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag-rank-original {
  font-size: 11px;
  color: var(--muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag-rank-count {
  font-size: 12px;
  font-weight: 700;
  color: var(--muted-color);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
  align-self: center;
}

.tag-rank-bar {
  position: absolute;
  left: 0;
  bottom: 0;
  height: 2px;
  background: var(--primary-color);
  opacity: 0.45;
  border-radius: 0 2px 2px 0;
}
</style>
