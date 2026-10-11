<script setup>
import { computed, ref, onBeforeUnmount } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { loadGalleries } from '@/composables/useGalleryData'
import { BOOK_FIELDS, serializeBooksCSV, validateBooks } from '@/utils/printedBooks'
import { findBookMatches } from '@/utils/printedMatching'

const API_BASE = import.meta.env.VITE_API_BASE || 'https://no-hentai.vercel.app'
const password = ref('')
const verified = ref(false)
const loading = ref(false)
const saving = ref(false)
const books = ref([])
const sha = ref('')
const original = ref('[]')
const selected = ref(-1)
const filter = ref('')
const matchQuery = ref('')
const galleries = ref([])
const error = ref('')
const notice = ref('')
const matchWarning = ref('')
const lastCommit = ref('')
const dirty = computed(() => JSON.stringify(books.value) !== original.value)
const activeBook = computed(() => books.value[selected.value] || null)
const galleryMap = computed(() => new Map(galleries.value.map(g => [String(g.gid), g])))
const linkedGallery = computed(() => galleryMap.value.get(activeBook.value?.sid))
const matches = computed(() => findBookMatches(galleries.value, matchQuery.value, activeBook.value || {}))
const visibleBooks = computed(() => {
  const q = filter.value.trim().toLocaleLowerCase()
  return books.value.map((book, index) => ({ book, index })).filter(({ book }) =>
    !q || BOOK_FIELDS.some(f => String(book[f] || '').toLocaleLowerCase().includes(q))
  )
})

async function request(action, body = {}) {
  const response = await fetch(`${API_BASE}/api/printed-books`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: password.value, action, ...body }),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.error || `请求失败（${response.status}）`)
  return data
}

async function unlock() {
  if (!password.value || loading.value) return
  loading.value = true; error.value = ''; notice.value = ''
  try {
    const response = await fetch(`${API_BASE}/api/trans-verify`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: password.value }),
    })
    if (!response.ok) throw new Error(response.status === 401 ? '密码错误' : '密码验证服务暂时不可用')
    const data = await request('load')
    books.value = data.books; sha.value = data.sha; original.value = JSON.stringify(data.books)
    verified.value = true
    selectBook(books.value.length ? 0 : -1)
    galleries.value = await loadGalleries()
    if (!galleries.value.length) matchWarning.value = '首页书目数据未能加载，暂时无法搜索关联；仍可编辑书单。'
  } catch (e) { error.value = e.message || '加载失败，请检查网络' }
  finally { loading.value = false }
}

function selectBook(index) {
  selected.value = index
  const book = books.value[index]
  matchQuery.value = book?.['日文名'] || book?.['书名'] || book?.sid || ''
}

function addBook() {
  books.value.push(Object.fromEntries(BOOK_FIELDS.map(f => [f, ''])))
  filter.value = ''; selectBook(books.value.length - 1)
  notice.value = ''; lastCommit.value = ''
}

function removeBook() {
  if (!activeBook.value || !window.confirm(`删除「${activeBook.value['书名'] || activeBook.value.ID || '新书目'}」？保存后才会生效。`)) return
  books.value.splice(selected.value, 1)
  selectBook(Math.min(selected.value, books.value.length - 1))
}

function linkGallery(gallery) {
  activeBook.value.sid = String(gallery.gid)
  notice.value = `已关联画廊 ${gallery.gid}，保存后生效。书名与其他字段保持原样。`
}

async function save() {
  if (saving.value || !dirty.value) return
  error.value = ''; notice.value = ''; lastCommit.value = ''
  const snapshot = JSON.parse(JSON.stringify(books.value))
  try { validateBooks(snapshot) } catch (e) { error.value = e.message; return }
  if (!snapshot.length && !window.confirm('书单将被清空，是否继续保存？')) return
  saving.value = true
  try {
    const data = await request('save', { books: snapshot, sha: sha.value })
    sha.value = data.sha; original.value = JSON.stringify(snapshot); lastCommit.value = data.commit
    notice.value = '书单已保存，自动部署完成后 Printed 页面会显示更新。'
  } catch (e) { error.value = e.message || '保存失败，请检查网络' }
  finally { saving.value = false }
}

async function reload() {
  if (dirty.value && !window.confirm('重新加载会丢弃当前未保存的修改，是否继续？建议先导出 CSV。')) return
  loading.value = true; error.value = ''; notice.value = ''
  try {
    const data = await request('load')
    books.value = data.books; sha.value = data.sha; original.value = JSON.stringify(data.books)
    lastCommit.value = ''; selectBook(books.value.length ? 0 : -1)
  } catch (e) { error.value = e.message || '加载失败，请检查网络' }
  finally { loading.value = false }
}

function exportCSV() {
  try {
    const blob = new Blob(['\uFEFF', serializeBooksCSV(books.value)], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'future_digi.csv'; a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (e) { error.value = e.message }
}

function leave() {
  if (saving.value) { error.value = '正在保存，请等待结果后再离开。'; return false }
  return !dirty.value || window.confirm('还有未保存的书单修改，确定离开？')
}

function lock() {
  if (!leave()) return
  password.value = ''; verified.value = false; books.value = []; original.value = '[]'
  sha.value = ''; selected.value = -1; error.value = ''; notice.value = ''; lastCommit.value = ''
}

function beforeUnload(event) {
  if (dirty.value || saving.value) { event.preventDefault(); event.returnValue = '' }
}
window.addEventListener('beforeunload', beforeUnload)
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
onBeforeRouteLeave(leave)
</script>

<template>
  <div class="printed-editor">
    <header class="editor-heading">
      <div><h1>编辑实体书单</h1><RouterLink to="/printed">返回书单</RouterLink></div>
      <button v-if="verified" type="button" :disabled="saving || loading" @click="lock">退出编辑</button>
    </header>
    <form v-if="!verified" class="unlock-form" @submit.prevent="unlock">
      <p>输入与 OCR / 翻译工作台相同的密码。</p>
      <label for="printed-password">编辑密码</label>
      <input id="printed-password" v-model="password" type="password" autocomplete="current-password" required :disabled="loading" />
      <button type="submit" :disabled="loading">{{ loading ? '正在验证并加载…' : '进入编辑' }}</button>
    </form>
    <p v-if="error" class="message error" role="alert">{{ error }}</p>
    <p v-if="notice" class="message" role="status">{{ notice }} <a v-if="lastCommit" :href="`https://github.com/ywryn/NoHentai/commit/${lastCommit}`" target="_blank" rel="noopener noreferrer">查看保存记录</a></p>
    <template v-if="verified">
      <div class="editor-toolbar">
        <span>{{ books.length }} 部 · {{ dirty ? '有未保存修改' : '已保存' }}</span>
        <button type="button" :disabled="saving || loading" @click="addBook">新增书目</button>
        <button type="button" :disabled="saving || loading" @click="exportCSV">导出 CSV</button>
        <button type="button" :disabled="saving || loading" @click="reload">重新加载</button>
        <button type="button" class="primary" :disabled="!dirty || saving || loading" @click="save">{{ saving ? '正在保存…' : '保存全部修改' }}</button>
      </div>
      <div class="editor-layout" :aria-busy="saving || loading">
        <aside class="book-list">
          <label for="book-filter">查找现有书目</label>
          <input id="book-filter" v-model="filter" type="search" placeholder="编号、书名、关联 ID、备注…" />
          <p>{{ visibleBooks.length }} 个结果</p>
          <div class="book-scroll">
            <button v-for="{ book, index } in visibleBooks" :key="index" type="button" :class="{ selected: selected === index }" :disabled="saving || loading" @click="selectBook(index)">
              <strong>{{ book['书名'] || book['日文名'] || '新书目' }}</strong><span>{{ book.ID || '未填写编号' }} · {{ book.sid || '未关联' }}</span>
            </button>
            <p v-if="!visibleBooks.length">没有符合条件的书目</p>
          </div>
        </aside>
        <section v-if="activeBook" class="book-form">
          <h2>书目信息</h2>
          <fieldset :disabled="saving || loading">
            <div class="field-grid">
              <label v-for="field in BOOK_FIELDS" :key="field" :class="{ wide: ['书名', '日文名', '备注'].includes(field) }">
                {{ field === 'sid' ? '关联画廊 ID（sid）' : field === 'cover' ? '本地封面文件名（cover）' : field }}
                <textarea v-if="field === '备注'" v-model="activeBook[field]" rows="3" maxlength="5000" />
                <input v-else v-model="activeBook[field]" :inputmode="['sid', '收价', '原价'].includes(field) ? 'decimal' : 'text'" maxlength="5000" />
              </label>
            </div>
            <p class="hint">书目 ID 可以重复。封面可填现有文件名；留空时使用关联画廊的封面。</p>
            <div v-if="linkedGallery" class="linked-gallery">
              <img v-if="linkedGallery.thumb" :src="linkedGallery.thumb" alt="关联书目封面" loading="lazy" referrerpolicy="no-referrer" />
              <div><strong>已关联：{{ linkedGallery.gid }}</strong><p>{{ linkedGallery.title }}</p><RouterLink :to="`/gallery/${linkedGallery.gid}`">查看画廊</RouterLink></div>
            </div>
            <p v-else-if="activeBook.sid" class="hint">首页数据中暂未找到 ID {{ activeBook.sid }}，可以重新搜索关联。</p>
            <button type="button" v-if="activeBook.sid" @click="activeBook.sid = ''">取消关联</button>
            <h2>从首页书目匹配</h2>
            <label for="gallery-match">画廊 ID / 链接 / 名称 / 上传者 / 标签</label>
            <input id="gallery-match" v-model="matchQuery" type="search" placeholder="输入书名、画廊 ID，或 a:作者 / uploader:上传者" />
            <div class="match-actions">
              <button type="button" @click="matchQuery = activeBook['书名']">用中文书名查找</button>
              <button type="button" @click="matchQuery = activeBook['日文名']">用日文书名查找</button>
            </div>
            <p class="hint">候选使用首页的数据源，按匹配程度排序，最多显示 20 条。请确认版本后再关联。</p>
            <p v-if="matchWarning" class="message" role="status">{{ matchWarning }}</p>
            <div class="matches">
              <article v-for="{ gallery, reason } in matches" :key="gallery.gid">
                <img v-if="gallery.thumb" :src="gallery.thumb" alt="候选书目封面" loading="lazy" referrerpolicy="no-referrer" />
                <div><strong>{{ gallery.title }}</strong><p>{{ gallery.title_jpn }}</p><small>#{{ gallery.gid }} · {{ gallery.category }} · {{ gallery.uploader }} · {{ gallery.filecount }} 页</small><p class="hint">{{ reason }}</p></div>
                <button type="button" @click="linkGallery(gallery)">{{ activeBook.sid === String(gallery.gid) ? '已关联' : '关联此书目' }}</button>
              </article>
              <p v-if="matchQuery.trim() && !matches.length && !matchWarning">没有匹配结果，可以尝试较短书名、作者标签或画廊 ID。</p>
            </div>
            <button type="button" class="danger" @click="removeBook">删除当前书目</button>
          </fieldset>
        </section>
        <p v-else class="empty-editor">选择书目进行编辑，或点击“新增书目”。</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.printed-editor { max-width: 1400px; margin: auto; padding: 24px 16px; color: var(--text-color); }
.editor-heading, .editor-toolbar, .match-actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.editor-heading { justify-content: space-between; margin-bottom: 24px; }
h1 { font-size: 24px; margin: 0 0 8px; } h2 { font-size: 18px; margin: 24px 0 12px; }
a { color: var(--primary-color); } button, input, textarea { font: inherit; }
button { min-height: 44px; padding: 8px 14px; border: 1px solid var(--border-color); border-radius: 8px; background: var(--surface-color); color: var(--text-color); cursor: pointer; }
button:disabled { opacity: .5; cursor: default; } button.primary { background: var(--primary-color); color: white; }
button.danger { color: #d84d5b; margin-top: 24px; }
input, textarea { display: block; width: 100%; box-sizing: border-box; padding: 10px; min-height: 44px; border: 1px solid var(--border-color); border-radius: 8px; background: var(--bg-color); color: var(--text-color); margin-top: 6px; }
label { display: block; font-size: 14px; } button:focus-visible, input:focus-visible, textarea:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
.unlock-form { max-width: 420px; padding: 24px; border: 1px solid var(--border-color); border-radius: 12px; }.unlock-form button { margin-top: 16px; }
.message { padding: 12px; border: 1px solid var(--border-color); border-radius: 8px; overflow-wrap: anywhere; }.error { color: #d84d5b; }
.editor-toolbar { margin-bottom: 16px; }.editor-toolbar span { margin-right: auto; }
.editor-layout { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 24px; }.book-list, .book-form { min-width: 0; }
.book-scroll { max-height: 72vh; overflow-y: auto; }.book-scroll button { width: 100%; text-align: left; margin: 0 0 6px; }.book-scroll strong, .book-scroll span { display: block; overflow-wrap: anywhere; }.book-scroll span { font-size: 12px; margin-top: 6px; color: var(--muted-color); }
.book-scroll button.selected { border-color: var(--primary-color); background: var(--primary-soft-bg); }
fieldset { border: 0; margin: 0; padding: 0; min-width: 0; }.field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }.wide { grid-column: 1 / -1; }
.hint { color: var(--muted-color); font-size: 13px; line-height: 1.6; }.match-actions { margin-top: 12px; }
.linked-gallery, .matches article { display: flex; gap: 12px; padding: 12px; margin-bottom: 10px; border: 1px solid var(--border-color); border-radius: 8px; align-items: start; }.linked-gallery img, .matches img { width: 64px; max-height: 100px; object-fit: contain; flex-shrink: 0; }.linked-gallery div, .matches article div { flex: 1; min-width: 0; overflow-wrap: anywhere; }.matches p { margin: 6px 0; }.matches article button { flex-shrink: 0; }
@media (max-width: 800px) { .editor-layout { grid-template-columns: 1fr; }.book-scroll { max-height: 260px; }.matches article { flex-wrap: wrap; }.matches article div { flex: 1 1 calc(100% - 76px); }.matches article button { flex-basis: calc(100% - 76px); margin-left: 76px; }.editor-toolbar button { flex: 1; }.editor-toolbar span { width: 100%; } }
</style>
