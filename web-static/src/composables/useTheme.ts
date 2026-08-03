import { ref, watch } from 'vue'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'theme'
/* 妈妈模式模糊强度：与主题无关，但需要在根元素上有值 */
const MOM_MODE_BLUR = '10px'

const isDark = ref(false)
const theme = ref<Theme>('dark')
/* 用户是否显式选过主题；未选过则跟随系统 */
const hasExplicitChoice = ref(false)

/**
 * 只切换根元素的主题 class，颜色一律交给 style.css 的 CSS 变量。
 * （此前这里还会写 html/body 的内联样式，与 CSS 变量形成双轨，
 *   且内联优先级最高导致主题色无法被覆盖。）
 */
function applyTheme(value: Theme) {
  const html = document.documentElement
  html.style.setProperty('--mom-mode-blur', MOM_MODE_BLUR)
  html.classList.toggle('my-app-dark', value === 'dark')
  html.classList.toggle('my-app-light', value === 'light')
  isDark.value = value === 'dark'
}

const stored = localStorage.getItem(STORAGE_KEY) as Theme | null
if (stored === 'light' || stored === 'dark') {
  hasExplicitChoice.value = true
  theme.value = stored
} else {
  /* 首次访问跟随系统，而非硬编码深色 */
  theme.value = window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}
applyTheme(theme.value)

/* 用户没有显式选择时，跟随系统偏好实时切换 */
window.matchMedia?.('(prefers-color-scheme: light)')?.addEventListener?.('change', e => {
  if (hasExplicitChoice.value) return
  theme.value = e.matches ? 'light' : 'dark'
})

watch(theme, value => {
  applyTheme(value)
  if (hasExplicitChoice.value) localStorage.setItem(STORAGE_KEY, value)
})

export const useTheme = () => {
  const setTheme = (next: Theme) => {
    const first = !hasExplicitChoice.value
    hasExplicitChoice.value = true
    if (theme.value === next) {
      if (first) localStorage.setItem(STORAGE_KEY, next)
      return
    }
    theme.value = next
  }

  const toggleTheme = () => setTheme(theme.value === 'light' ? 'dark' : 'light')

  const getThemeLabel = () => (theme.value === 'light' ? '浅色模式' : '深色模式')

  return { isDark, theme, setTheme, toggleTheme, getThemeLabel }
}
