<script setup>
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { fitTextToBox, boxOrientation } from '@/utils/translateHelpers'
import { candidateGroups, safeExpansion } from '@/utils/compareLayouts'
const props = defineProps(['mode', 'image', 'results', 'paper', 'zoom', 'outlines'])
const emit = defineEmits(['select', 'pan'])
const viewport = ref(null),
  sheet = ref(null)
const boxes = ref([]),
  badges = ref([])
const groups = computed(() => candidateGroups(props.results, props.mode, props.paper))
const percent = (b) => ({
  left: (b[0] / props.image.naturalWidth) * 100 + '%',
  top: (b[1] / props.image.naturalHeight) * 100 + '%',
  width: ((b[2] - b[0]) / props.image.naturalWidth) * 100 + '%',
  height: ((b[3] - b[1]) / props.image.naturalHeight) * 100 + '%',
})
let generation = 0,
  observer,
  frame
function schedule() {
  generation++
  cancelAnimationFrame(frame)
  frame = requestAnimationFrame(() => layout(generation))
}
async function layout(version) {
  const originals = props.results.map((r) => r.bbox)
  boxes.value = originals.slice()
  badges.value = []
  await nextTick()
  if (version !== generation || !sheet.value?.clientWidth) return
  const width = props.image.naturalWidth,
    height = props.image.naturalHeight
  const scale = sheet.value.clientWidth / width
  const step = 12 / scale
  for (let i = 0; i < originals.length; i++) {
    const text = sheet.value.querySelector('[data-text="' + i + '"]')
    if (!text) continue
    const baseline = props.mode === 'original'
    const original = originals[i]
    const owner = props.mode === 'balloon' && props.paper?.owner(original)
    // Cap exploratory growth when no reliable paper boundary is available.
    const obstacles = boxes.value.filter((_, j) => j !== i)
    let fit = false
    for (let pass = 0; pass <= 6; pass++) {
      if (fitTextToBox(text, baseline ? 11 : 14)) {
        fit = true
        break
      }
      if (pass === 6) break
      const b = boxes.value[i]
      let next = b
      if (baseline) {
        const w = Math.min(width, b[2] - b[0] + 2 * step),
          h = Math.min(height, b[3] - b[1] + 2 * step)
        const x = Math.max(0, Math.min(width - w, b[0] - step)),
          y = Math.max(0, Math.min(height - h, b[1] - step))
        next = [x, y, x + w, y + h]
      } else {
        for (const side of [0, 2, 1, 3]) {
          const candidate = safeExpansion(next, side, step, [width, height], obstacles, props.paper, owner)
          if (candidate) next = candidate
        }
        if (next === b) break
      }
      boxes.value[i] = next
      await nextTick()
      if (version !== generation) return
    }
    if (!fit && !baseline) fit = fitTextToBox(text, 11)
    if (!fit) {
      if (!baseline) boxes.value[i] = original
      badges.value[i] = true
    }
  }
}
watch(() => [props.image, props.results, props.mode, props.zoom, props.paper], schedule, { flush: 'post' })
onMounted(() => {
  observer = new ResizeObserver(schedule)
  observer.observe(sheet.value)
  schedule()
})
onBeforeUnmount(() => {
  generation++
  observer?.disconnect()
  cancelAnimationFrame(frame)
})
function pan(x, y) {
  if (viewport.value) {
    viewport.value.scrollLeft = x
    viewport.value.scrollTop = y
  }
}
defineExpose({ pan })
</script>
<template>
  <div
    ref="viewport"
    class="viewport"
    @scroll="emit('pan', $event.target.scrollLeft, $event.target.scrollTop)"
  >
    <div
      ref="sheet"
      class="sheet"
      :style="{ width: zoom + '%', aspectRatio: image.naturalWidth + '/' + image.naturalHeight }"
    >
      <img :src="image.src" alt="对比页原图" draggable="false" />
      <template v-for="(r, i) in results" :key="r._id">
        <button
          v-if="boxes[i]"
          type="button"
          class="gt-ocr-box"
          :class="{ 'gt-box-has-badge': badges[i] }"
          :style="percent(boxes[i])"
          :aria-label="'对白 ' + (i + 1)"
          @click="emit('select', i)"
        >
          <span
            v-if="r.translation && !badges[i]"
            :data-text="i"
            class="gt-box-trans-text"
            :class="{
              'gt-box-vertical': (r.orientation || boxOrientation(r.bbox)) === 'vertical',
              'gt-box-sfx': r.kind === 'sfx',
            }"
            >{{ r.translation }}</span
          >
          <span v-else class="gt-box-badge">{{ i + 1 }}</span>
        </button>
      </template>
      <template v-if="outlines"
        ><i v-for="(b, i) in groups" :key="i" class="outline" :style="percent(b)"
      /></template>
    </div>
  </div>
</template>
<style scoped>
.viewport {
  overflow: auto;
  min-height: 0;
  flex: 1;
  scrollbar-gutter: stable;
}
.sheet {
  position: relative;
}
.sheet > img {
  display: block;
  width: 100%;
  height: 100%;
}
.sheet button {
  padding: 0;
  font: inherit;
}
.outline {
  position: absolute;
  pointer-events: none;
  border: 2px dashed #00e3ee;
  box-shadow: inset 0 0 0 1px #143438;
  z-index: 2;
}
</style>
