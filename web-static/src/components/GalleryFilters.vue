<script setup>
import { ref, computed } from 'vue'
import Popover from 'primevue/popover'
import AppIcon from './ui/AppIcon.vue'
import GallerySearchInput from './GallerySearchInput.vue'
import { exTypeList, exTypeDotColors } from '@/utils/galleryUtils'
import { parseQuery, parsedTerms, removeQueryTerm } from '@/utils/gallerySearch'

const props = defineProps({
  query: {type:String, required:true}, types: {type:Array, required:true},
  counts: Object, totals: Object, submitting:Boolean, label: {type:String, default:'搜索画廊'},
  profile: {type:String, default:'gallery'}, debounce: {type:Number, default:220},
  sort: {type:String, default:'default'}, fav: {type:String, default:''},
  favCounts: Object, enableSort: {type:Boolean, default:false},
})
const emit = defineEmits(['change','submit','update:sort','update:fav'])
const SORT_OPTIONS = [
  { value: 'default', label: '默认收藏顺序' },
  { value: 'posted_desc', label: '最新发布' },
  { value: 'posted_asc', label: '最早发布' },
  { value: 'rating_desc', label: '评分最高' },
  { value: 'pages_desc', label: '页数最多' },
  { value: 'pages_asc', label: '页数最少' },
]
const favOptions = computed(() =>
  Object.entries(props.favCounts || {})
    .filter(([name]) => name)
    .sort((a, b) => b[1] - a[1])
)
const categoryPopover = ref(), categoryOpen = ref(false), searchInputRef = ref()
const searchQuery = computed({ get: () => props.query, set: value => emit('change', value, props.types) })
const activeTypes = computed(() => props.types)
const activeTerms = computed(() => parsedTerms(parseQuery(props.query)))
const isFiltered = computed(() => activeTypes.value.length || activeTerms.value.length || Boolean(props.fav) || (props.enableSort && props.sort !== 'default'))
const categoryLabel = computed(() => {
  const [first,...others] = props.types
  return others.length ? `${first} +${others.length}` : first || '分类'
})
const categoryOptions = computed(() => {
  const names = new Set([...exTypeList.map(t=>t.name), ...Object.keys(props.totals || {})])
  return Array.from(names, name => ({
    name, color:exTypeDotColors[name] || 'var(--faint-color)',
    count:props.counts ? props.counts[name] || 0 : null,
    total:props.totals?.[name] || 0, checked:props.types.includes(name)
  })).sort((a,b)=>b.total-a.total)
})
function toggleType(type) {
  emit('change', searchInputRef.value.currentText(), props.types.includes(type) ? props.types.filter(t=>t!==type) : [...props.types,type])
}
function removeTerm(term) { searchQuery.value = removeQueryTerm(props.query,term) }
function clearAll() {
  searchInputRef.value?.reset()
  emit('change','',[])
  if (props.fav) emit('update:fav', '')
  if (props.enableSort && props.sort !== 'default') emit('update:sort', 'default')
}
</script>
<template>
        <div class="home-filter-panel">
          <GallerySearchInput ref="searchInputRef" v-model="searchQuery" :label="label" :profile="profile" :debounce="debounce" :search-button="profile === 'live'" :submitting="submitting" @search-click="value => emit('submit',value,types)">
            <template #actions>
            <button
              class="home-filter-btn"
              :class="{ 'is-on': activeTypes.length }"
              type="button"
              aria-haspopup="dialog"
              :aria-expanded="categoryOpen"
              :title="activeTypes.length ? `已选 ${activeTypes.length} 个分类` : '按分类筛选'"
              @click="categoryPopover.toggle($event)"
            >
              <span
                v-if="activeTypes.length"
                class="home-type-dot"
                :style="{ background: exTypeDotColors[activeTypes[0]] }"
              ></span>
              <AppIcon name="filter" :size="20" v-else />
              {{ categoryLabel }}
              <span class="home-filter-caret" aria-hidden="true"><AppIcon name="chevron-down" :size="18" /></span>
            </button>
            </template>
          </GallerySearchInput>

          <div v-if="enableSort || favOptions.length" class="home-refine-row">
            <label v-if="enableSort" class="home-refine-field">
              <span class="home-refine-label">排序</span>
              <select class="home-refine-select" :value="sort" aria-label="排序方式" @change="emit('update:sort', $event.target.value)">
                <option v-for="opt in SORT_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </label>
            <label v-if="favOptions.length" class="home-refine-field">
              <span class="home-refine-label">收藏夹</span>
              <select class="home-refine-select" :value="fav" aria-label="按收藏夹筛选" @change="emit('update:fav', $event.target.value)">
                <option value="">全部收藏夹</option>
                <option v-for="[name, count] in favOptions" :key="name" :value="name">{{ name }} ({{ count }})</option>
              </select>
            </label>
          </div>

          <!-- 当前生效的筛选条件：逐项可移除 -->
          <div v-if="isFiltered" class="home-active-filters">
            <button v-if="fav" class="home-filter-chip" type="button" :title="`移除收藏夹：${fav}`" @click="emit('update:fav', '')">
              ♥ {{ fav }}
              <span class="chip-x" aria-hidden="true"><AppIcon name="close" :size="18" /></span>
            </button>

            <button
              v-for="term in activeTerms"
              :key="`t-${term.raw}`"
              class="home-filter-chip"
              :class="{ 'is-exclude': term.mode === 'exclude', 'is-or': term.mode === 'or' }"
              type="button"
              :title="`移除条件：${term.raw}`"
              @click="removeTerm(term)"
            >
              <span v-if="term.mode === 'exclude'" class="chip-sign">−</span>
              <span v-else-if="term.mode === 'or'" class="chip-sign">或</span>
              {{ term.raw.replace(/^[-~]/, '') }}
              <span class="chip-x" aria-hidden="true"><AppIcon name="close" :size="18" /></span>
            </button>
            <button
              v-for="type in activeTypes"
              :key="`c-${type}`"
              class="home-filter-chip is-category"
              type="button"
              :title="`移除分类：${type}`"
              @click="toggleType(type)"
            >
              <span class="home-type-dot" :style="{ background: exTypeDotColors[type] }"></span>
              {{ type }}
              <span class="chip-x" aria-hidden="true"><AppIcon name="close" :size="18" /></span>
            </button>
            <button class="home-clear-all" type="button" @click="clearAll">全部清除</button>
          </div>
        </div>
      <Popover ref="categoryPopover" class="category-popover" @show="categoryOpen = true" @hide="categoryOpen = false">
        <div class="category-panel">
          <div class="category-panel-head">
            <span class="category-panel-title">按分类筛选</span>
            <button
              v-if="activeTypes.length"
              class="category-reset"
              type="button"
              @click="emit('change',searchInputRef.currentText(),[])"
            >清除</button>
          </div>
          <ul class="category-list">
            <li v-for="opt in categoryOptions" :key="opt.name">
              <label class="category-row" :class="{ 'is-empty': opt.count === 0 && !opt.checked }">
                <input
                  type="checkbox"
                  class="category-check"
                  :checked="opt.checked"
                  :disabled="opt.count === 0 && !opt.checked"
                  @change="toggleType(opt.name)"
                />
                <span class="home-type-dot" :style="{ background: opt.color }"></span>
                <span class="category-name">{{ opt.name }}</span>
                <span v-if="opt.count != null" class="category-count">{{ opt.count }}</span>
              </label>
            </li>
          </ul>
        </div>
      </Popover>
</template>
