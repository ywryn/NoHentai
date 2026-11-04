import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { activeToken } from '@/utils/gallerySearch'
import { loadTagSuggestions } from '@/composables/useGalleryData'

// One lifecycle for every search box: cancel obsolete replies, reset selection,
// and expose an active option only while its popup is visible.
export function useSearchSuggestions(text, caret, enabled, focused) {
  const items = ref([]), highlight = ref(-1), dismissed = ref(false), failure = ref('')
  const visible = computed(() => focused.value && !dismissed.value && items.value.length > 0)
  let timer, controller, sequence = 0
  function cancel() {
    clearTimeout(timer); controller?.abort(); sequence++
    items.value = []; highlight.value = -1; failure.value = ''
  }
  watch([text, caret, enabled, focused], () => {
    cancel(); dismissed.value = false
    if (!enabled.value || !focused.value) return
    const token = activeToken(text.value, caret.value).text
    if (token.length < 2 || token.includes('$') || /^[-~]/.test(token)) return
    const ticket = sequence
    controller = new AbortController()
    const request = controller
    timer = setTimeout(async () => {
      try {
        const result = await loadTagSuggestions(token, request.signal)
        if (ticket !== sequence || request.signal.aborted) return
        items.value = result.items; highlight.value = -1
      } catch (error) {
        if (ticket === sequence && error.name !== 'AbortError') failure.value = '补全暂不可用，仍可直接搜索'
      }
    }, 150)
  })
  function close() { dismissed.value = true; highlight.value = -1 }
  function move(direction) {
    if (!visible.value) return
    highlight.value = highlight.value < 0
      ? direction > 0 ? 0 : items.value.length - 1
      : (highlight.value + direction + items.value.length) % items.value.length
  }
  onBeforeUnmount(cancel)
  return { items, highlight, visible, failure, close, move, cancel }
}
