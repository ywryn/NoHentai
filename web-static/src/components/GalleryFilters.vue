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
  fav: {type:Array, default:() => []}, favCounts: Object,
})
const emit = defineEmits(['change','submit','clear','update:fav'])
const favoritePalette = [
  '#4f85c6', '#d37055', '#3a9777', '#9468b7', '#b48326', '#c4628b',
  '#428f9b', '#818d40', '#6d75c5', '#a3765a', '#ba5b66', '#6497ae',
]
const favoriteColors = computed(() => {
  // Assign colors independently of display order and result counts.
  const names = Object.keys(props.favCounts || {}).sort()
  return new Map(names.map((name, index) => [name, favoritePalette[index % favoritePalette.length]]))
})
function favoriteColor(name) { return favoriteColors.value.get(name) || 'var(--faint-color)' }
const favOptions = computed(() =>
  [...new Set([...favoriteColors.value.keys(), ...props.fav])]
    .map(name => ({ name, count: props.favCounts?.[name] ?? 0 }))
    .sort((a, b) => b.count - a.count)
)
const categoryPopover = ref(), categoryOpen = ref(false), searchInputRef = ref()
const favPopover = ref(), favOpen = ref(false)
const searchQuery = computed({ get: () => props.query, set: value => emit('change', value, props.types) })
const activeTypes = computed(() => props.types)
const activeTerms = computed(() => parsedTerms(parseQuery(props.query)))
const isFiltered = computed(() => activeTypes.value.length || activeTerms.value.length || props.fav.length)
const favoriteLabel = computed(() => {
  const [first, ...others] = props.fav
  return others.length ? `${first} +${others.length}` : first || '收藏夹'
})
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
function changeFavorites(values) {
  emit('update:fav', values, searchInputRef.value.currentText())
}
function toggleFavorite(name) {
  changeFavorites(props.fav.includes(name) ? props.fav.filter(value => value !== name) : [...props.fav, name])
}
function clearAll() {
  searchInputRef.value?.reset()
  emit('clear')
}
</script>
<template>
        <div class="home-filter-panel">
          <GallerySearchInput ref="searchInputRef" v-model="searchQuery" :label="label" :profile="profile" :debounce="debounce" :search-button="profile === 'live'" :submitting="submitting" help-in-filter-row @search-click="value => emit('submit',value,types)">
            <template #actions>
            <button
              class="home-filter-btn home-category-trigger"
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
              <span class="home-filter-label">{{ categoryLabel }}</span>
              <span class="home-filter-caret" aria-hidden="true"><AppIcon name="chevron-down" :size="18" /></span>
            </button>
            <button v-if="favOptions.length" type="button" class="home-filter-btn"
              :class="{ 'is-on': fav.length }" aria-haspopup="dialog" :aria-expanded="favOpen"
              :aria-label="fav.length ? `收藏夹：已选 ${fav.length} 个` : '收藏夹'" @click="favPopover.toggle($event)">
              <AppIcon name="folder" :size="14" />
              <span class="home-filter-label">{{ favoriteLabel }}</span>
              <span class="home-filter-caret" aria-hidden="true"><AppIcon name="chevron-down" :size="18" /></span>
            </button>
            </template>
          </GallerySearchInput>

          <!-- 当前生效的筛选条件：逐项可移除 -->
          <div v-if="isFiltered" class="home-active-filters">
            <button v-for="name in fav" :key="name" class="home-filter-chip" type="button" :title="`移除收藏夹：${name}`" @click="toggleFavorite(name)">
              <span class="home-type-dot" aria-hidden="true" :style="{ background: favoriteColor(name) }"></span>
              {{ name }}
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
      <Popover ref="favPopover" class="category-popover" aria-label="按收藏夹筛选" @show="favOpen = true" @hide="favOpen = false">
        <div class="category-panel">
          <div class="category-panel-head">
            <span class="category-panel-title">按收藏夹筛选</span>
            <button v-if="fav.length" type="button" class="category-reset" @click="changeFavorites([])">清除</button>
          </div>
          <ul class="category-list">
            <li v-for="option in favOptions" :key="option.name">
              <label class="category-row">
                <input type="checkbox" class="category-check" :checked="fav.includes(option.name)" @change="toggleFavorite(option.name)" />
                <span class="home-type-dot" aria-hidden="true" :style="{ background: favoriteColor(option.name) }"></span>
                <span class="category-name">{{ option.name }}</span>
                <span class="category-count">{{ option.count }}</span>
              </label>
            </li>
          </ul>
        </div>
      </Popover>
</template>
