import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

interface Point { x: number; y: number }
interface Picture { src: string; x: number; y: number; width: number; height: number; scale: number }

export function useReaderZoom(singleTap: (target: HTMLElement) => void) {
  const picture = ref<Picture | null>(null)
  let start: Point | null = null
  let origin: Point | null = null
  let pointer = -1
  let moved = false
  let pending: {point:Point; image:HTMLImageElement; timer:number} | null = null
  let suppressClickUntil = 0

  function cancelTap() {
    if (pending) window.clearTimeout(pending.timer)
    pending = null
  }
  function reset() { cancelTap(); picture.value = null; start = null; pointer = -1 }
  function constrain(value: number, extent: number, viewport: number) {
    return extent <= viewport ? (viewport - extent) / 2 : Math.min(0, Math.max(viewport - extent, value))
  }
  function imageRect(image: HTMLImageElement) {
    const rect = image.getBoundingClientRect()
    const fit = Math.min(rect.width / image.naturalWidth, rect.height / image.naturalHeight)
    const width = image.naturalWidth * fit, height = image.naturalHeight * fit
    return {width, height, left:rect.left + (rect.width-width)/2, top:rect.top + (rect.height-height)/2}
  }
  function zoom(image: HTMLImageElement, point: Point) {
    const rect = imageRect(image)
    const old = picture.value || {src:image.currentSrc, x:rect.left, y:rect.top, width:rect.width, height:rect.height, scale:1}
    if (old.scale === 3) { reset(); return }
    const scale = old.scale === 1 ? 2 : 3
    const factor = scale / old.scale
    const next = {...old, scale,
      x:constrain(point.x - (point.x - old.x) * factor, old.width * scale, innerWidth),
      y:constrain(point.y - (point.y - old.y) * factor, old.height * scale, innerHeight)}
    picture.value = next
    if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) nextTick(() => {
      const frame = (p: Picture) => ({transform:`translate(${p.x}px,${p.y}px) scale(${p.scale})`})
      document.querySelector('.reader-zoom img')?.animate([frame(old), frame(next)], {duration:180, easing:'ease-out'})
    })
  }
  function down(e: PointerEvent) {
    if (!(e.target as HTMLElement).closest('.book-view,.scroll-view,.reader-zoom')) return
    if (e.pointerType !== 'touch' || (e.target as HTMLElement).closest('button, input, .thumb-sidebar')) return
    if (!e.isPrimary) { start = null; cancelTap(); return }
    start = {x:e.clientX,y:e.clientY}; pointer = e.pointerId; moved = false
    origin = picture.value ? {x:picture.value.x, y:picture.value.y} : null
    if (origin) (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  }
  function move(e: PointerEvent) {
    if (!start || e.pointerId !== pointer) return
    const dx = e.clientX - start.x, dy = e.clientY - start.y
    if (Math.hypot(dx,dy) > 9) { moved = true; cancelTap() }
    const p = picture.value
    if (moved && p && origin) {
      p.x = constrain(origin.x + dx, p.width*p.scale, innerWidth)
      p.y = constrain(origin.y + dy, p.height*p.scale, innerHeight)
    }
  }
  function up(e: PointerEvent) {
    if (!start || pointer !== e.pointerId) return
    move(e); start = null
    const target = e.target as HTMLElement
    const image = picture.value ? document.querySelector<HTMLImageElement>('.reader-zoom img') :
      Array.from(document.querySelectorAll<HTMLImageElement>('.gr-content .pi-img')).find(img => {
        const r = imageRect(img)
        return r.width && e.clientX >= r.left && e.clientX <= r.left + r.width && e.clientY >= r.top && e.clientY <= r.top + r.height
      })
    if (!image) return
    e.stopPropagation()
    suppressClickUntil = performance.now() + 500
    if (moved) return
    const point = {x:e.clientX,y:e.clientY}
    if (pending && pending.image === image && Math.hypot(point.x-pending.point.x, point.y-pending.point.y) < 32) {
      cancelTap(); zoom(image, point); return
    }
    cancelTap()
    pending = {point, image, timer:window.setTimeout(() => {
      pending = null
      if (!picture.value && target.isConnected) singleTap(target)
    }, 275)}
  }
  function click(e: MouseEvent) {
    if (e.detail && performance.now() < suppressClickUntil && !(e.target as HTMLElement).closest('button')) {
      e.preventDefault(); e.stopPropagation()
    }
  }
  function cancel() { start = null; cancelTap() }
  onMounted(() => window.addEventListener('resize', reset))
  onBeforeUnmount(() => { reset(); window.removeEventListener('resize', reset) })
  return {picture, down, move, up, click, cancel, reset}
}
