import { onBeforeUnmount, onMounted } from 'vue'

export function useTouchScrollIndicator() {
  const touch = matchMedia('(hover: none) and (pointer: coarse) and (forced-colors: none)')
  const indicator = document.createElement('span')
  indicator.className = 'touch-scroll-indicator'
  indicator.setAttribute('aria-hidden', 'true')
  let hideTimer: ReturnType<typeof setTimeout> | undefined

  function hide() {
    clearTimeout(hideTimer)
    indicator.removeAttribute('data-scrolling')
  }

  function onScroll(event: Event) {
    const area = event.target === document ? document.scrollingElement : event.target
    if (!(area instanceof HTMLElement) || !area.matches('.touch-scroll-area, html.admin-active')) return

    const { clientHeight, scrollHeight, scrollTop } = area
    const scrollRange = scrollHeight - clientHeight
    if (scrollRange <= 0) return hide()

    const isViewport = area === document.scrollingElement
    const bounds = area.getBoundingClientRect()
    const top = isViewport ? 0 : Math.max(0, bounds.top + area.clientTop)
    const bottom = isViewport ? clientHeight : Math.min(innerHeight, bounds.top + area.clientTop + clientHeight)
    const height = bottom - top
    if (height <= 0) return hide()

    const thumbHeight = Math.min(height, Math.max(32, height * clientHeight / scrollHeight))
    const progress = Math.min(1, Math.max(0, scrollTop / scrollRange))
    const right = isViewport ? 0 : innerWidth - bounds.left - area.clientLeft - area.clientWidth

    // A modal dialog is in the top layer, so its indicator must be inside it.
    const host = area.closest('dialog[open]') ?? document.body
    if (indicator.parentElement !== host) host.append(indicator)
    indicator.style.blockSize = `${thumbHeight}px`
    indicator.style.top = `${top + (height - thumbHeight) * progress}px`
    indicator.style.right = `${Math.max(0, right) + 2}px`
    indicator.setAttribute('data-scrolling', '')
    clearTimeout(hideTimer)
    hideTimer = setTimeout(hide, 650)
  }

  function updateListener() {
    document.removeEventListener('scroll', onScroll, true)
    hide()
    if (touch.matches) document.addEventListener('scroll', onScroll, { capture: true, passive: true })
  }

  onMounted(() => {
    if (!CSS.supports('scrollbar-width', 'none')) return
    document.body.append(indicator)
    touch.addEventListener('change', updateListener)
    updateListener()
  })

  onBeforeUnmount(() => {
    touch.removeEventListener('change', updateListener)
    document.removeEventListener('scroll', onScroll, true)
    hide()
    indicator.remove()
  })

  return hide
}
