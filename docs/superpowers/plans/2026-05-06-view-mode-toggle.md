# Global View Mode Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a global Card/Cover view toggle button to the nav bar, affecting Home, Printed, and Daily pages consistently.

**Architecture:** A `useViewMode.ts` composable holds a module-level singleton ref (same pattern as `useTheme.ts`) persisted to localStorage. `ViewModeToggle.vue` renders the nav button. Shared CSS classes `vm-cover-*` and `vm-card-*` go into `style.css` (global). Each of the three pages conditionally renders its card or cover template based on `viewMode`.

**Tech Stack:** Vue 3 Composition API, CSS Grid, localStorage

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `src/composables/useViewMode.ts` | Create | Global viewMode state + toggle |
| `src/components/ViewModeToggle.vue` | Create | Nav button component |
| `src/style.css` | Modify | Add shared `vm-cover-*` and `vm-card-*` CSS |
| `src/App.vue` | Modify | Import & render ViewModeToggle in `theme-toggle-nav` |
| `src/components/Home.vue` | Modify | Add cover mode template (vm-cover-grid) |
| `src/components/Printed.vue` | Modify | Migrate cover to vm-cover-grid, add card mode (vm-card-list) |
| `src/components/DailySearch.vue` | Modify | Add cover mode template (vm-cover-grid) |

---

### Task 1: Create useViewMode.ts

**Files:**
- Create: `web-static/src/composables/useViewMode.ts`

- [ ] **Step 1: Create the file**

```typescript
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
```

- [ ] **Step 2: Verify file exists**

```bash
ls web-static/src/composables/
# Expected: useMomMode.ts  useTheme.ts  useViewMode.ts
```

---

### Task 2: Create ViewModeToggle.vue

**Files:**
- Create: `web-static/src/components/ViewModeToggle.vue`

- [ ] **Step 1: Create the component**

```vue
<template>
  <button
    class="view-mode-btn"
    :title="viewMode === 'card' ? '切换为封面视图' : '切换为列表视图'"
    @click="toggleViewMode"
  >
    <!-- Grid icon — shown in card mode, click to switch to cover -->
    <svg v-if="viewMode === 'card'" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 3h8v8H3V3zm0 10h8v8H3v-8zm10-10h8v8h-8V3zm0 10h8v8h-8v-8z"/>
    </svg>
    <!-- List icon — shown in cover mode, click to switch to card -->
    <svg v-else viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 5h18v2H3V5zm0 6h18v2H3v-2zm0 6h18v2H3v-2z"/>
    </svg>
  </button>
</template>

<script setup lang="ts">
import { useViewMode } from '@/composables/useViewMode'
const { viewMode, toggleViewMode } = useViewMode()
</script>

<style scoped>
.view-mode-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--surface-color);
  color: var(--text-color);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: color 0.2s, border-color 0.2s;
}
.view-mode-btn:hover {
  color: var(--primary-color);
  border-color: var(--primary-color);
  background: var(--surface-color);
}
.view-mode-btn svg {
  width: 16px;
  height: 16px;
  fill: currentColor;
}
</style>
```

---

### Task 3: Add shared CSS to style.css

**Files:**
- Modify: `web-static/src/style.css` — append at end of file

- [ ] **Step 1: Append shared view mode CSS**

Add the following block at the very end of `src/style.css`:

```css
/* ═══════════════════════════════════════
   View Mode — shared cover grid & Printed card row
   ═══════════════════════════════════════ */

/* Cover grid (Home / Daily / Printed cover mode) */
.vm-cover-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
  padding: 10px 14px;
}

.vm-cover-card {
  border-radius: 8px;
  overflow: hidden;
  background: var(--row-bg);
  border: 1px solid var(--row-border);
  cursor: pointer;
  transition: transform 0.15s, border-color 0.15s;
}

.vm-cover-card:hover {
  transform: translateY(-2px);
  border-color: var(--border-color);
}

.vm-cover-img {
  aspect-ratio: 2/3;
  overflow: hidden;
  background: #1a2640;
}

.vm-cover-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.vm-cover-no-img {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--muted-color);
  font-size: 28px;
}

.vm-cover-info {
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.vm-cover-id {
  font-size: 10px;
  color: var(--muted-color);
}

.vm-cover-title {
  font-size: 11px;
  color: var(--title-color);
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.vm-cover-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 2px;
}

.vm-cover-pages {
  font-size: 10px;
  color: var(--muted-color);
}

/* Card list (Printed card mode) */
.vm-card-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 14px;
}

.vm-card-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  background: var(--row-bg);
  border: 1px solid var(--row-border);
  border-radius: 8px;
  padding: 8px 10px;
  cursor: pointer;
  transition: border-color 0.12s, background 0.12s;
}

.vm-card-row:hover {
  border-color: var(--border-color);
  background: var(--row-hover-bg);
}

.vm-card-thumb {
  width: 49px;
  height: 70px;
  border-radius: 4px;
  flex-shrink: 0;
  overflow: hidden;
  background: #1a2640;
  display: flex;
  align-items: center;
  justify-content: center;
}

.vm-card-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.vm-card-no-thumb {
  color: var(--muted-color);
  font-size: 18px;
}

.vm-card-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.vm-card-top {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  min-width: 0;
}

.vm-card-id {
  font-size: 11px;
  color: var(--muted-color);
  font-weight: 600;
  flex-shrink: 0;
}

.vm-card-title {
  font-size: 13px;
  color: var(--title-color);
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.vm-card-subtitle {
  font-size: 11px;
  color: var(--muted-color);
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.vm-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
}

.vm-card-tag {
  font-size: 11px;
  background: var(--tag-bg);
  border: 1px solid var(--tag-border);
  color: var(--tag-color);
  border-radius: 4px;
  padding: 1px 5px;
}

.vm-card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.vm-card-pages {
  font-size: 11px;
  color: var(--muted-color);
}

.vm-card-empty {
  font-size: 11px;
  color: var(--muted-color);
  font-style: italic;
}

/* Mom mode blur for shared view classes */
.mom-mode .vm-cover-img img,
.mom-mode .vm-card-thumb img {
  filter: blur(var(--mom-mode-blur));
}
```

---

### Task 4: Update App.vue — add ViewModeToggle to nav

**Files:**
- Modify: `web-static/src/App.vue`

- [ ] **Step 1: Add import in `<script setup>`**

After the existing imports, add:
```typescript
import ViewModeToggle from '@/components/ViewModeToggle.vue'
```

- [ ] **Step 2: Add component to `theme-toggle-nav`**

Find:
```html
<div class="theme-toggle-nav">
  <MomModeToggle />
  <ThemeToggle />
</div>
```

Replace with:
```html
<div class="theme-toggle-nav">
  <ViewModeToggle />
  <MomModeToggle />
  <ThemeToggle />
</div>
```

- [ ] **Step 3: Commit**

```bash
git add web-static/src/composables/useViewMode.ts \
        web-static/src/components/ViewModeToggle.vue \
        web-static/src/style.css \
        web-static/src/App.vue
git commit -m "feat: 添加全局 Card/Cover 视图切换按钮"
```

---

### Task 5: Update Home.vue — add cover mode

**Files:**
- Modify: `web-static/src/components/Home.vue`

Home currently renders one `<div class="gallery-list">`. Replace it (and nothing else) with a v-if/v-else pair.

- [ ] **Step 1: Import useViewMode in script**

Home.vue uses Options API. Add to the `data()` / top of script section — actually Home.vue uses a mix. Find where other composables are used. Add at top of `<script>` section (it uses `<script>` not `<script setup>`):

Look for where `Rating` is imported (around line 1 of script). Add after existing imports:

```js
import { useViewMode } from '@/composables/useViewMode'
```

Then in the component's `setup()` or `created()` — Home.vue uses Options API with no explicit `setup()`. Add a `setup()` method to expose viewMode:

```js
setup() {
  const { viewMode } = useViewMode()
  return { viewMode }
},
```

- [ ] **Step 2: Add cover mode template**

Find the section (around line 92):
```html
<div class="gallery-list">
  <div v-if="loading" class="empty-state">Loading…</div>
  <div v-else-if="!mappedResults.length" class="empty-state">No data</div>
  <article
    v-else
    v-for="item in mappedResults"
    :key="item.gid"
    class="gallery-row"
    @click="navigateToGallery(null, item.gid)"
  >
    <div class="gr-thumb">
      <img :src="item.thumb || ''" :alt="item.type" loading="lazy" />
    </div>
    <div class="gr-body">
      <div class="gr-top">
        <span class="gr-badge" :class="item.typeClass">{{ item.type }}</span>
        <span class="gr-title">{{ item.title_jpn || item.title }}</span>
      </div>
      <div class="gr-tags" v-if="item.tags.length">
        <span v-for="(tag, i) in item.tags.slice(0, 8)" :key="i" class="gr-tag">
          {{ tag.tag_cn || tag.value }}
        </span>
      </div>
      <div class="gr-meta">
        <Rating :modelValue="item.rating" readonly class="gr-rating" />
        <span class="gr-pages" v-if="item.filecount">{{ item.filecount }}</span>
        <span class="gr-date">{{ item.published }}</span>
        <span class="gr-fav" v-if="item.favCategory">♥ {{ item.favCategory }}</span>
      </div>
    </div>
  </article>
</div>
```

Replace with:
```html
<!-- Card mode -->
<div v-if="viewMode === 'card'" class="gallery-list">
  <div v-if="loading" class="empty-state">Loading…</div>
  <div v-else-if="!mappedResults.length" class="empty-state">No data</div>
  <article
    v-else
    v-for="item in mappedResults"
    :key="item.gid"
    class="gallery-row"
    @click="navigateToGallery(null, item.gid)"
  >
    <div class="gr-thumb">
      <img :src="item.thumb || ''" :alt="item.type" loading="lazy" />
    </div>
    <div class="gr-body">
      <div class="gr-top">
        <span class="gr-badge" :class="item.typeClass">{{ item.type }}</span>
        <span class="gr-title">{{ item.title_jpn || item.title }}</span>
      </div>
      <div class="gr-tags" v-if="item.tags.length">
        <span v-for="(tag, i) in item.tags.slice(0, 8)" :key="i" class="gr-tag">
          {{ tag.tag_cn || tag.value }}
        </span>
      </div>
      <div class="gr-meta">
        <Rating :modelValue="item.rating" readonly class="gr-rating" />
        <span class="gr-pages" v-if="item.filecount">{{ item.filecount }}</span>
        <span class="gr-date">{{ item.published }}</span>
        <span class="gr-fav" v-if="item.favCategory">♥ {{ item.favCategory }}</span>
      </div>
    </div>
  </article>
</div>

<!-- Cover mode -->
<div v-else class="vm-cover-grid">
  <div v-if="loading" class="empty-state" style="grid-column:1/-1">Loading…</div>
  <div v-else-if="!mappedResults.length" class="empty-state" style="grid-column:1/-1">No data</div>
  <div
    v-else
    v-for="item in mappedResults"
    :key="item.gid"
    class="vm-cover-card"
    @click="navigateToGallery(null, item.gid)"
  >
    <div class="vm-cover-img">
      <img :src="item.thumb || ''" :alt="item.type" loading="lazy" />
    </div>
    <div class="vm-cover-info">
      <div class="vm-cover-meta">
        <span class="gr-badge" :class="item.typeClass">{{ item.type }}</span>
        <span class="vm-cover-pages">{{ item.filecount }}</span>
      </div>
      <div class="vm-cover-title">{{ item.title_jpn || item.title }}</div>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Build check**

```bash
cd web-static && npm run build 2>&1 | tail -10
# Expected: ✓ built in X.XXs
```

- [ ] **Step 4: Commit**

```bash
git add web-static/src/components/Home.vue
git commit -m "feat(Home): 添加 Cover 视图模式"
```

---

### Task 6: Update Printed.vue — add card mode, migrate cover to vm-cover-grid

**Files:**
- Modify: `web-static/src/components/Printed.vue`

- [ ] **Step 1: Add imports and helpers to script**

In `<script setup>`, after the existing imports, add:

```js
import Rating from 'primevue/rating'
import { useViewMode } from '@/composables/useViewMode'

const { viewMode } = useViewMode()

const typeClassMap = {
  'Doujinshi': 'red', 'Manga': 'orange', 'Artist CG': 'yellow',
  'Game CG': 'green', 'Western': 'gold', 'Non-H': 'lightblue',
  'Image Set': 'blue', 'Cosplay': 'purple', 'Asian Porn': 'pink', 'Misc': 'gray',
}

function getGallery(sid) {
  if (sid == null || sid === '') return null
  return galleryMap.value[String(sid)] ?? null
}

function getTagValues(tags) {
  if (!Array.isArray(tags)) return []
  return tags
    .map(t => (t.includes(':') ? t.split(':', 2)[1] : t))
    .slice(0, 6)
}
```

- [ ] **Step 2: Replace cover/card template**

Find (around line 155):
```html
<div v-else class="digi-grid">
  <article v-for="(item, index) in filteredItems" :key="index" class="digi-card" @click="clickCard(item)">
    <!-- 封面 -->
    <div class="digi-thumb">
      <img
        v-if="getThumb(item.sid)"
        :src="getThumb(item.sid)"
        :alt="item['书名']"
        loading="lazy"
      />
      <div v-else class="digi-no-cover">
        <span>{{ item.ID }}</span>
      </div>
    </div>

    <!-- 信息 -->
    <div class="digi-body">
      <span class="digi-id">{{ item.ID }}</span>
      <div class="digi-book-title">{{ item['书名'] }}</div>
      <div v-if="item['备注']" class="digi-remark">{{ item['备注'] }}</div>
    </div>
  </article>
</div>
```

Replace with:
```html
<!-- Cover mode (default) -->
<div v-else-if="viewMode === 'cover'" class="vm-cover-grid">
  <article v-for="(item, index) in filteredItems" :key="index" class="vm-cover-card" @click="clickCard(item)">
    <div class="vm-cover-img">
      <img v-if="getThumb(item.sid)" :src="getThumb(item.sid)" :alt="item['书名']" loading="lazy" />
      <div v-else class="vm-cover-no-img">📚</div>
    </div>
    <div class="vm-cover-info">
      <div class="vm-cover-id">{{ item.ID }}</div>
      <div class="vm-cover-title">{{ item['书名'] }}</div>
    </div>
  </article>
</div>

<!-- Card mode -->
<div v-else class="vm-card-list">
  <article v-for="(item, index) in filteredItems" :key="index" class="vm-card-row" @click="clickCard(item)">
    <div class="vm-card-thumb">
      <img v-if="getThumb(item.sid)" :src="getThumb(item.sid)" :alt="item['书名']" loading="lazy" />
      <div v-else class="vm-card-no-thumb">📚</div>
    </div>
    <div class="vm-card-body">
      <div class="vm-card-top">
        <span class="vm-card-id">{{ item.ID }}</span>
        <span
          v-if="getGallery(item.sid)"
          class="gr-badge"
          :class="typeClassMap[getGallery(item.sid).category] || 'default'"
        >{{ getGallery(item.sid).category }}</span>
        <span class="vm-card-title">{{ item['书名'] }}</span>
      </div>
      <div v-if="item['日文名']" class="vm-card-subtitle">{{ item['日文名'] }}</div>
      <template v-if="getGallery(item.sid)">
        <div v-if="getTagValues(getGallery(item.sid).tags).length" class="vm-card-tags">
          <span v-for="tag in getTagValues(getGallery(item.sid).tags)" :key="tag" class="vm-card-tag">{{ tag }}</span>
        </div>
        <div class="vm-card-meta">
          <Rating :modelValue="getGallery(item.sid).rating" readonly />
          <span v-if="getGallery(item.sid).filecount" class="vm-card-pages">{{ getGallery(item.sid).filecount }}p</span>
        </div>
      </template>
      <div v-else class="vm-card-empty">— 暂无匹配元数据 —</div>
    </div>
  </article>
</div>
```

Note: The condition `v-else-if` and `v-else` above rely on an earlier `v-if` in the template (`v-if="loading"`, `v-else-if="error"`, `v-else-if="!filteredItems.length"`). The replacement keeps `v-else` as the fallback after those conditions. Make sure the `v-else-if="viewMode === 'cover'"` and `v-else` follow directly after the `v-else-if="!filteredItems.length"` block.

- [ ] **Step 3: Build check**

```bash
cd web-static && npm run build 2>&1 | tail -10
# Expected: ✓ built in X.XXs
```

- [ ] **Step 4: Commit**

```bash
git add web-static/src/components/Printed.vue
git commit -m "feat(Printed): 添加 Card 视图模式，封面迁移至 vm-cover-grid"
```

---

### Task 7: Update DailySearch.vue — add cover mode

**Files:**
- Modify: `web-static/src/components/DailySearch.vue`

- [ ] **Step 1: Add import to script**

In `<script setup>`, after the existing imports, add:

```js
import { useViewMode } from '@/composables/useViewMode'
const { viewMode } = useViewMode()
```

- [ ] **Step 2: Wrap gallery list with v-if/v-else**

Find (around line 89):
```html
<div class="gallery-list daily-gallery-list">
  <div v-if="loading" class="empty-state">Loading…</div>
  <div v-else-if="!results.length" class="empty-state">No data</div>
  <article
    v-else
    v-for="item in results"
    :key="item.gid"
    class="gallery-row"
    @click="navigateToGallery(item.gid)"
  >
    <div class="gr-thumb">
      <img :src="item.thumb || ''" :alt="item.type" loading="lazy" />
    </div>
    <div class="gr-body">
      <div class="gr-top">
        <span class="gr-badge" :class="item.typeClass">{{ item.type }}</span>
        <span class="gr-title">{{ item.title_jpn || item.title }}</span>
      </div>
      <div class="gr-tags" v-if="item.tags.length">
        <span v-for="(tag, i) in item.tags.slice(0, 8)" :key="i" class="gr-tag">
          {{ tag.tag_cn || tag.value }}
        </span>
      </div>
      <div class="gr-meta">
        <Rating :modelValue="item.rating" readonly class="gr-rating" />
        <span class="gr-pages" v-if="item.filecount">{{ item.filecount }}p</span>
        <span class="gr-date">{{ item.published }}</span>
      </div>
    </div>
  </article>
</div>
```

Replace with:
```html
<!-- Card mode -->
<div v-if="viewMode === 'card'" class="gallery-list daily-gallery-list">
  <div v-if="loading" class="empty-state">Loading…</div>
  <div v-else-if="!results.length" class="empty-state">No data</div>
  <article
    v-else
    v-for="item in results"
    :key="item.gid"
    class="gallery-row"
    @click="navigateToGallery(item.gid)"
  >
    <div class="gr-thumb">
      <img :src="item.thumb || ''" :alt="item.type" loading="lazy" />
    </div>
    <div class="gr-body">
      <div class="gr-top">
        <span class="gr-badge" :class="item.typeClass">{{ item.type }}</span>
        <span class="gr-title">{{ item.title_jpn || item.title }}</span>
      </div>
      <div class="gr-tags" v-if="item.tags.length">
        <span v-for="(tag, i) in item.tags.slice(0, 8)" :key="i" class="gr-tag">
          {{ tag.tag_cn || tag.value }}
        </span>
      </div>
      <div class="gr-meta">
        <Rating :modelValue="item.rating" readonly class="gr-rating" />
        <span class="gr-pages" v-if="item.filecount">{{ item.filecount }}p</span>
        <span class="gr-date">{{ item.published }}</span>
      </div>
    </div>
  </article>
</div>

<!-- Cover mode -->
<div v-else class="vm-cover-grid">
  <div v-if="loading" class="empty-state" style="grid-column:1/-1">Loading…</div>
  <div v-else-if="!results.length" class="empty-state" style="grid-column:1/-1">No data</div>
  <div
    v-else
    v-for="item in results"
    :key="item.gid"
    class="vm-cover-card"
    @click="navigateToGallery(item.gid)"
  >
    <div class="vm-cover-img">
      <img :src="item.thumb || ''" :alt="item.type" loading="lazy" />
    </div>
    <div class="vm-cover-info">
      <div class="vm-cover-meta">
        <span class="gr-badge" :class="item.typeClass">{{ item.type }}</span>
        <span class="vm-cover-pages">{{ item.filecount }}p</span>
      </div>
      <div class="vm-cover-title">{{ item.title_jpn || item.title }}</div>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Build check**

```bash
cd web-static && npm run build 2>&1 | tail -10
# Expected: ✓ built in X.XXs
```

- [ ] **Step 4: Final commit**

```bash
git add web-static/src/components/DailySearch.vue \
        web-static/src/components/Printed.vue \
        web-static/src/components/Home.vue \
        web-static/src/App.vue \
        web-static/src/style.css \
        web-static/src/composables/useViewMode.ts \
        web-static/src/components/ViewModeToggle.vue
git commit -m "feat(DailySearch): 添加 Cover 视图模式"
```

---

## Self-Review

**Spec coverage:** All confirmed design points covered:
- ✅ Global toggle button in nav (ViewModeToggle)
- ✅ Persistent state via localStorage (useViewMode)
- ✅ Home: card (existing) + cover (vm-cover-grid)
- ✅ Printed: cover (vm-cover-grid) + card (vm-card-list) with ID + Sheets title priority + matched/unmatched states
- ✅ Daily: card (existing) + cover (vm-cover-grid)
- ✅ All cover modes use same CSS classes (vm-cover-*)
- ✅ No overlay text on cover images
- ✅ Mom mode blur applied to vm-cover-img and vm-card-thumb

**Type consistency:** `viewMode` is `Ref<'card' | 'cover'>` throughout. `getGallery()` returns `gallery object | null`. `getTagValues()` returns `string[]`. All consistent.

**Ambiguity resolved:** `v-else-if` / `v-else` ordering in Printed accounts for the existing `v-if="loading"` and `v-else-if="error"` and `v-else-if="!filteredItems.length"` guards preceding the grid.
