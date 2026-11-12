<script setup>
import AppIcon from '@/components/ui/AppIcon.vue'
import { ref, computed, watch, onBeforeUnmount, getCurrentInstance, nextTick } from 'vue'
import { applySuggestion, SEARCH_SYNTAX_HELP, BOOK_SEARCH_FIELDS } from '@/utils/gallerySearch'
import { useSearchSuggestions } from '@/composables/useSearchSuggestions'
const props = defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, default: '搜索画廊' },
  placeholder: { type: String, default: '搜索标题、作者、标签…' },
  profile: { type: String, default: 'gallery' },
  variant: { type: String, default: 'public' },
  help: { type: Boolean, default: true },
  debounce: { type: Number, default: 220 },
})
const emit = defineEmits(['update:modelValue', 'submit'])
const id = `catalog-search-${getCurrentInstance().uid}`
const input = ref(null), text = ref(props.modelValue), caret = ref(text.value.length)
const focused = ref(false), helpOpen = ref(false), composing = ref(false)
const enabled = computed(() => props.profile !== 'plain' && !composing.value)
const { items, highlight, visible, failure, close, move } = useSearchSuggestions(text, caret, enabled, focused)
const syntax = computed(() => props.profile === 'book' ? [...SEARCH_SYNTAX_HELP, ...BOOK_SEARCH_FIELDS] : SEARCH_SYNTAX_HELP)
let timer, blurTimer
watch(() => props.modelValue, value => {
  clearTimeout(timer)
  if (text.value.trim() !== value.trim()) { text.value = value; caret.value = value.length }
})
function commit(submit = false) {
  clearTimeout(timer)
  if (text.value !== props.modelValue) emit('update:modelValue', text.value)
  if (submit) emit('submit', text.value)
}
function readInput(event) {
  text.value = event.target.value
  caret.value = event.target.selectionStart ?? text.value.length
  clearTimeout(timer)
  if (!composing.value) timer = setTimeout(() => commit(), props.debounce)
}
function compositionEnd(event) { composing.value = false; readInput(event) }
function focus() { input.value?.focus() }
function reset(value = '') { clearTimeout(timer); text.value = value; caret.value = value.length; close() }
function clear() { reset(); commit(); focus() }
function choose(item) {
  text.value = applySuggestion(text.value, item, caret.value)
  caret.value = text.value.length
  close(); commit(); focus()
  nextTick(() => input.value?.setSelectionRange(caret.value, caret.value))
}
function example(value) { text.value = value; caret.value = value.length; close(); commit(true); helpOpen.value = false; focus() }
function key(event) {
  if (composing.value || event.isComposing) return
  if (event.key === 'Escape') { close(); helpOpen.value = false; return }
  if (visible.value && ['ArrowDown', 'ArrowUp'].includes(event.key)) { event.preventDefault(); move(event.key === 'ArrowDown' ? 1 : -1) }
  else if (visible.value && highlight.value >= 0 && ['Enter', 'Tab'].includes(event.key)) { event.preventDefault(); choose(items.value[highlight.value]) }
  else if (event.key === 'Enter') { event.preventDefault(); close(); commit(true) }
}
function blur() { blurTimer = setTimeout(() => { focused.value = false; close() }, 130) }
function onFocus() { clearTimeout(blurTimer); focused.value = true }
function selection(event) { caret.value = event.target.selectionStart ?? text.value.length }
onBeforeUnmount(() => { clearTimeout(timer); clearTimeout(blurTimer) })
defineExpose({ focus, clear, reset })
</script>
<template>
  <div class="search-control" :class="`search-control-${variant}`" :data-search-profile="profile">
    <div class="search-control-row">
      <div class="search-control-box">
        <AppIcon name="search" :size="20" class="search-control-icon" />
        <input :id="id" ref="input" :value="text" type="text" inputmode="search" maxlength="2000" :aria-label="label" :placeholder="placeholder"
          role="combobox" aria-autocomplete="list" :aria-controls="`${id}-options`" :aria-expanded="visible"
          :aria-activedescendant="visible && highlight >= 0 ? `${id}-option-${highlight}` : undefined"
          autocomplete="off" spellcheck="false" @input="readInput" @keydown="key" @keyup="selection" @click="selection" @select="selection"
          @compositionstart="composing = true; clearTimeout(timer)" @compositionend="compositionEnd" @focus="onFocus" @blur="blur"/>
        <button v-if="text" type="button" class="search-control-clear" :aria-label="`清空${label}`" @mousedown.prevent @click="clear"><AppIcon name="close" :size="18" /></button>
        <ul v-if="visible" :id="`${id}-options`" class="search-control-suggestions" role="listbox" aria-label="标签建议">
          <li v-for="(item,index) in items" :id="`${id}-option-${index}`" :key="item.tag" role="option" :aria-selected="highlight === index"
            @pointerdown.prevent="choose(item)" @mouseenter="highlight = index">
            <strong>{{item.tag_cn || item.value}}</strong><small>{{item.namespace}}:"{{item.value}}$"</small>
          </li>
        </ul>
      </div>
      <slot name="actions" />
      <button v-if="help && profile !== 'plain'" type="button" class="search-control-help" :aria-expanded="helpOpen" :aria-controls="`${id}-help`" @click="helpOpen = !helpOpen">语法 <span aria-hidden="true">{{helpOpen ? '−' : '＋'}}</span></button>
    </div>
    <small v-if="failure" class="search-control-note" role="status">{{failure}}</small>
    <div v-if="helpOpen && help && profile !== 'plain'" :id="`${id}-help`" class="search-control-syntax">
      <button v-for="item in syntax" :key="item.syntax" type="button" @click="example(item.example)"><code>{{item.syntax}}</code><span>{{item.desc}}</span></button>
    </div>
  </div>
</template>
<style scoped>
.search-control{--search-panel:var(--surface-color);--search-border:var(--border-color);--search-muted:var(--muted-color);--search-text:var(--text-color);--search-accent:var(--primary-color);--search-hover:var(--hover-bg);min-width:0;width:100%}
.search-control-admin{--search-panel:var(--a-panel);--search-border:var(--a-border);--search-muted:var(--a-muted);--search-text:var(--a-text);--search-accent:var(--a-accent);--search-hover:var(--a-soft)}
.search-control-row{display:flex;align-items:stretch;gap:10px;min-width:0}.search-control-box{position:relative;display:flex;align-items:center;gap:9px;min-width:0;flex:1;padding:0 10px;border:1px solid var(--search-border);border-radius:8px;background:var(--search-panel);color:var(--search-muted);min-height:44px;box-sizing:border-box}
.search-control-box:focus-within{border-color:var(--search-accent);outline:2px solid color-mix(in srgb,var(--search-accent) 25%,transparent);outline-offset:1px}.search-control-icon{width:17px;height:17px;flex-shrink:0}
.search-control .search-control-box input{width:100%;min-width:0;min-height:42px;padding:8px 0;border:0;border-radius:0;outline:0;background:transparent;color:var(--search-text);font:inherit;font-size:13px;box-shadow:none;box-sizing:border-box}.search-control-box input::placeholder{color:var(--search-muted)}
.search-control-clear{display:flex;align-items:center;justify-content:center;flex-shrink:0;min-width:30px;min-height:32px;padding:0;border:0;border-radius:6px;background:transparent;color:var(--search-muted);font-size:20px;cursor:pointer;box-shadow:none}.search-control-clear:hover{background:var(--search-hover);color:var(--search-text)}
.search-control-help{display:flex;align-items:center;gap:8px;padding:0 12px;min-height:44px;flex-shrink:0;border:1px solid var(--search-border);border-radius:8px;background:var(--search-panel);color:var(--search-muted);font-size:12px;cursor:pointer;box-shadow:none}.search-control-help[aria-expanded=true]{background:var(--search-hover);color:var(--search-accent)}
.search-control-suggestions{list-style:none;margin:0;position:absolute;top:calc(100% + 6px);left:0;right:0;z-index:35;max-height:300px;overflow:auto;padding:5px;border:1px solid var(--search-border);border-radius:8px;background:var(--search-panel);box-shadow:0 10px 28px #15204125;color:var(--search-text)}
.search-control-suggestions li{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center;padding:9px 10px;border-radius:6px;cursor:pointer}.search-control-suggestions li:hover,.search-control-suggestions li[aria-selected=true]{background:var(--search-hover)}.search-control-suggestions strong{font-size:12px;font-weight:550}.search-control-suggestions small{font-size:10px;color:var(--search-muted);overflow-wrap:anywhere}
.search-control-syntax{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 16px;padding-top:12px}.search-control-syntax button{display:flex;gap:10px;align-items:start;padding:7px 0;text-align:left;border:0;background:none;color:var(--search-muted);font-size:11px;cursor:pointer;box-shadow:none}.search-control-syntax code{color:var(--search-accent);min-width:65px}.search-control-note{display:block;color:var(--search-muted);font-size:11px;margin-top:6px}.search-control button:focus-visible,.search-control [role=option]:focus-visible{outline:2px solid var(--search-accent);outline-offset:2px}
@media(max-width:600px){.search-control-syntax{grid-template-columns:1fr}.search-control-row{gap:6px}.search-control-help{padding:0 9px}}
@media(max-width:600px){
.search-control-row:has(.home-filter-btn,.daily-reset){flex-wrap:wrap}
.search-control-row:has(.home-filter-btn,.daily-reset) .search-control-box{flex-basis:100%}
.search-control .search-control-box input{font-size:16px}
.search-control-clear{min-width:44px;min-height:44px}
.search-control-suggestions li{min-height:44px}
}
</style>
