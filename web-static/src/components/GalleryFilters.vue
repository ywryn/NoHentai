<script setup>
import { ref, computed } from 'vue'
import Popover from 'primevue/popover'
import AppIcon from './ui/AppIcon.vue'
import GallerySearchInput from './GallerySearchInput.vue'
import { exTypeList, exTypeDotColors } from '@/utils/galleryUtils'
import { parseQuery, parsedTerms, removeQueryTerm } from '@/utils/gallerySearch'

const props = defineProps({
  query: {type:String, required:true}, types: {type:Array, required:true},
  counts: Object, totals: Object, label: {type:String, default:'搜索画廊'},
  profile: {type:String, default:'gallery'}, debounce: {type:Number, default:220}
})
const emit = defineEmits(['change'])
const categoryPopover = ref(), categoryOpen = ref(false), searchInputRef = ref()
const searchQuery = computed({ get: () => props.query, set: value => emit('change', value, props.types) })
const activeTypes = computed(() => props.types)
const activeTerms = computed(() => parsedTerms(parseQuery(props.query)))
const isFiltered = computed(() => activeTypes.value.length || activeTerms.value.length)
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
function clearAll() { searchInputRef.value?.reset(); emit('change','',[]) }
</script>
<template>
        <div class="home-filter-panel">
          <GallerySearchInput ref="searchInputRef" v-model="searchQuery" :label="label" :profile="profile" :debounce="debounce">
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

          <!-- 当前生效的筛选条件：逐项可移除 -->
          <div v-if="isFiltered" class="home-active-filters">

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
