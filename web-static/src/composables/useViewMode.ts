import { ref, watch } from 'vue'

export type ViewMode = 'card' | 'cover'

const viewMode = ref<ViewMode>('card')

const saved = localStorage.getItem('viewMode') as ViewMode
if (saved === 'card' || saved === 'cover') {
  viewMode.value = saved
}

watch(viewMode, (val) => {
  localStorage.setItem('viewMode', val)
})

export const useViewMode = () => {
  const toggleViewMode = () => {
    viewMode.value = viewMode.value === 'card' ? 'cover' : 'card'
  }
  return { viewMode, toggleViewMode }
}
