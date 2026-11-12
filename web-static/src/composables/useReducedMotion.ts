import { onBeforeUnmount, onMounted, ref } from 'vue'

/** Live OS preference; never overwrite the user's saved reader settings. */
export function useReducedMotion() {
  const query = typeof window === 'undefined' ? null : window.matchMedia('(prefers-reduced-motion: reduce)')
  const reduced = ref(query?.matches ?? false)
  const update = () => { reduced.value = query?.matches ?? false }
  onMounted(() => { update(); query?.addEventListener('change', update) })
  onBeforeUnmount(() => query?.removeEventListener('change', update))
  return reduced
}
