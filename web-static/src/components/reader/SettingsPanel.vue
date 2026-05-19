<!-- web-static/src/components/reader/SettingsPanel.vue -->
<template>
  <div class="sp-overlay" @click.self="$emit('close')">
    <div class="sp-panel">
      <div class="sp-header">
        <span>Settings</span>
        <button class="reader-btn" @click="$emit('close')">✕</button>
      </div>

      <div class="sp-body">
        <!-- Reading Mode -->
        <div class="sp-row">
          <span class="sp-label">Mode</span>
          <div class="sp-radio-group">
            <label class="sp-radio">
              <input type="radio" :checked="settings.readingMode === 'book'"
                @change="update('readingMode', 'book')" />
              Book
            </label>
            <label class="sp-radio">
              <input type="radio" :checked="settings.readingMode === 'scroll'"
                @change="update('readingMode', 'scroll')" />
              Scroll
            </label>
          </div>
        </div>

        <!-- Direction (book only) -->
        <div class="sp-row" v-show="settings.readingMode === 'book'">
          <span class="sp-label">Direction</span>
          <div class="sp-radio-group">
            <label class="sp-radio">
              <input type="radio" :checked="settings.bookDirection === 'rtl'"
                @change="update('bookDirection', 'rtl')" />
              RTL ←
            </label>
            <label class="sp-radio">
              <input type="radio" :checked="settings.bookDirection === 'ltr'"
                @change="update('bookDirection', 'ltr')" />
              LTR →
            </label>
          </div>
        </div>

        <!-- Animation (book only) -->
        <div class="sp-row" v-show="settings.readingMode === 'book'">
          <span class="sp-label">Animation</span>
          <div class="sp-radio-group">
            <label class="sp-radio">
              <input type="radio" :checked="settings.pageTurnAnimation === 'slide'"
                @change="update('pageTurnAnimation', 'slide')" />
              Slide
            </label>
            <label class="sp-radio">
              <input type="radio" :checked="settings.pageTurnAnimation === 'flip'"
                @change="update('pageTurnAnimation', 'flip')" />
              Flip
            </label>
            <label class="sp-radio">
              <input type="radio" :checked="settings.pageTurnAnimation === 'none'"
                @change="update('pageTurnAnimation', 'none')" />
              None
            </label>
          </div>
        </div>

        <!-- Width Scale -->
        <div class="sp-row sp-row-col">
          <div class="sp-label-row">
            <span class="sp-label">Width</span>
            <span class="sp-value">{{ settings.widthScale }}%</span>
          </div>
          <input
            type="range" min="50" max="150" step="5"
            :value="settings.widthScale"
            @input="update('widthScale', parseInt(($event.target as HTMLInputElement).value))"
            class="sp-slider"
          />
        </div>

        <!-- Scroll margin (scroll mode only) -->
        <div class="sp-row sp-row-col" v-show="settings.readingMode === 'scroll'">
          <div class="sp-label-row">
            <span class="sp-label">Page Gap</span>
            <span class="sp-value">{{ settings.scrollPageMargin }}px</span>
          </div>
          <input
            type="range" min="0" max="40" step="2"
            :value="settings.scrollPageMargin"
            @input="update('scrollPageMargin', parseInt(($event.target as HTMLInputElement).value))"
            class="sp-slider"
          />
        </div>

        <!-- Keyboard shortcuts reference -->
        <div class="sp-section-title">Keyboard Shortcuts</div>
        <div class="sp-shortcuts">
          <div class="sp-shortcut"><kbd>← / A</kbd><span>Visual prev</span></div>
          <div class="sp-shortcut"><kbd>→ / D</kbd><span>Visual next</span></div>
          <div class="sp-shortcut"><kbd>F</kbd><span>Thumbnail grid</span></div>
          <div class="sp-shortcut"><kbd>S</kbd><span>Settings</span></div>
          <div class="sp-shortcut"><kbd>M</kbd><span>Toggle mode</span></div>
          <div class="sp-shortcut"><kbd>Esc</kbd><span>Close / Back</span></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { READER_KEY } from '@/composables/useReader'
import type { ReaderSettings } from '@/composables/useReader'

defineEmits<{ close: [] }>()

const reader = inject(READER_KEY)!
const { settings, updateSetting } = reader

function update<K extends keyof ReaderSettings>(key: K, value: ReaderSettings[K]) {
  updateSetting(key, value)
}
</script>

<style scoped>
.sp-overlay {
  position: fixed;
  inset: 0;
  z-index: 300;
  background: var(--reader-overlay);
  display: flex;
  justify-content: flex-end;
}
.sp-panel {
  width: min(320px, 90vw);
  height: 100%;
  background: #111827;
  display: flex;
  flex-direction: column;
  box-shadow: -4px 0 20px rgba(0,0,0,0.5);
}
.sp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--reader-border);
  font-size: 15px;
  font-weight: 600;
  flex-shrink: 0;
}
.sp-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.sp-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.sp-row-col { flex-direction: column; align-items: stretch; }
.sp-label { font-size: 13px; color: var(--reader-muted); flex-shrink: 0; }
.sp-label-row { display: flex; justify-content: space-between; }
.sp-value { font-size: 13px; color: var(--reader-accent); }

.sp-radio-group { display: flex; gap: 8px; flex-wrap: wrap; }
.sp-radio {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  cursor: pointer;
  color: var(--reader-text);
}
.sp-radio input { accent-color: var(--reader-accent); cursor: pointer; }

.sp-slider {
  width: 100%;
  accent-color: var(--reader-accent);
  cursor: pointer;
}

.sp-section-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--reader-muted);
  padding-bottom: 4px;
  border-bottom: 1px solid var(--reader-border);
}
.sp-shortcuts { display: flex; flex-direction: column; gap: 6px; }
.sp-shortcut {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}
kbd {
  background: var(--reader-surface);
  border: 1px solid var(--reader-border);
  border-radius: 4px;
  padding: 2px 6px;
  font-family: monospace;
  font-size: 11px;
  color: var(--reader-text);
  min-width: 52px;
  text-align: center;
}
.sp-shortcut span { color: var(--reader-muted); }
</style>
