<script setup>
import { computed, ref, inject, watch, onBeforeUnmount, onMounted } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { loadGalleries } from '@/composables/useGalleryData'
import { BOOK_FIELDS, serializeBooksCSV, validateBooks } from '@/utils/printedBooks'
import { findBookMatches } from '@/utils/printedMatching'
import AdminIcon from './admin/AdminIcon.vue'

const confirm = inject('adminConfirm')
const openNavigation = inject('adminOpenNavigation')
const detailOpen = ref(false), bookTab = ref('details')
const props = defineProps({ adminPassword: { type: String, required: true } })

const API_BASE = import.meta.env.VITE_API_BASE || 'https://no-hentai.vercel.app'
const verified = ref(false)
const loading = ref(false)
const matchingLoading = ref(false)
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
watch(books, () => { if (dirty.value) { notice.value = ''; lastCommit.value = '' } }, { deep: true })
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
  const response = await fetch(`${API_BASE}/api/admin`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: props.adminPassword, action, resource: 'printed', ...(body.books ? { data: body.books } : {}), ...(body.sha ? { sha: body.sha } : {}) }),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.error || `请求失败（${response.status}）`)
  return action === 'load' ? { ...data, books: data.data } : data
}

async function unlock() {
  if (!props.adminPassword || loading.value) return
  loading.value = true; error.value = ''; notice.value = ''
  try {
    const data = await request('load')
    books.value = data.books; sha.value = data.sha; original.value = JSON.stringify(data.books)
    verified.value = true
    selectBook(books.value.length ? 0 : -1, false)
    matchingLoading.value = true
    loadGalleries().then(list => {
      galleries.value = list
      if (!list.length) matchWarning.value = '画廊数据暂时无法加载，仍可编辑书目信息，稍后重新打开页面可重试匹配。'
    }).finally(() => { matchingLoading.value = false })
  } catch (e) { error.value = e.message || '加载失败，请检查网络' }
  finally { loading.value = false }
}

function selectBook(index, open = true) {
  detailOpen.value = open; bookTab.value = 'details'
  selected.value = index
  const book = books.value[index]
  matchQuery.value = book?.['日文名'] || book?.['书名'] || book?.sid || ''
}

function addBook() {
  books.value.push(Object.fromEntries(BOOK_FIELDS.map(f => [f, ''])))
  filter.value = ''; selectBook(books.value.length - 1)
  notice.value = ''; lastCommit.value = ''
}

async function removeBook() {
  if (!activeBook.value || !await confirm({ title: '删除当前书目？', description: `“${activeBook.value['书名'] || activeBook.value.ID || '新书目'}”将从书单中移除，保存后生效。`, confirmLabel: '删除书目', danger: true })) return
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
  if (!snapshot.length && !await confirm({ title: '清空整个书单？', description: '保存后所有书目会从公开书单中移除。可以先导出 CSV 留存。', confirmLabel: '确认清空', danger: true })) return
  saving.value = true
  try {
    const data = await request('save', { books: snapshot, sha: sha.value })
    sha.value = data.sha; original.value = JSON.stringify(snapshot); lastCommit.value = data.commit
    notice.value = '书单已提交，自动部署完成后 Printed 页面会显示更新。' + (data.warnings?.length ? ` ${data.warnings.join('；')}` : '')
  } catch (e) { error.value = e.message || '保存失败，请检查网络' }
  finally { saving.value = false }
}

async function reload() {
  if (dirty.value && !await confirm({ title: '重新加载书单？', description: '当前未保存修改将被丢弃，可以先导出 CSV。', confirmLabel: '放弃并重新加载', danger: true })) return
  loading.value = true; error.value = ''; notice.value = ''
  try {
    const data = await request('load')
    books.value = data.books; sha.value = data.sha; original.value = JSON.stringify(data.books)
    lastCommit.value = ''; selectBook(books.value.length ? 0 : -1, false)
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

async function leave() {
  if (saving.value) { error.value = '正在保存，请等待结果后再离开。'; return false }
  return !dirty.value || await confirm({ title: '离开前保存修改？', description: '书单有未提交的修改。返回编辑可以继续保存，也可以放弃修改后离开。', confirmLabel: '放弃并离开', danger: true })
}

function beforeUnload(event) {
  if (dirty.value || saving.value) { event.preventDefault(); event.returnValue = '' }
}
function shortcut(e) { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') { e.preventDefault(); if (dirty.value && !saving.value && !loading.value) save() } }
onMounted(unlock)
window.addEventListener('keydown', shortcut)
onBeforeUnmount(() => window.removeEventListener('keydown', shortcut))
window.addEventListener('beforeunload', beforeUnload)
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
onBeforeRouteLeave(leave)
</script>

<template>
  <div class="a-page a-printed-page a-has-savebar" :aria-busy="loading || saving">
    <header class="a-page-heading"><div class="a-page-title"><button class="a-button a-icon-button a-mobile-menu" aria-label="打开管理导航" @click="openNavigation"><AdminIcon name="menu" /></button><div><h1>实体书单</h1><p>整理书目信息，关联画廊中的数字版本。</p></div></div><div class="a-heading-actions"><button class="a-button" :disabled="saving || loading || !verified" @click="addBook"><AdminIcon name="plus" :size="16" />新增书目</button><details class="a-more-menu"><summary class="a-button a-icon-button" aria-label="更多书单操作"><AdminIcon name="dots" :size="18" /></summary><div><button :disabled="saving || loading || !verified" @click="exportCSV"><AdminIcon name="download" :size="15" />导出 CSV</button><button :disabled="saving || loading" @click="reload"><AdminIcon name="refresh" :size="15" />重新加载</button><RouterLink to="/printed"><AdminIcon name="arrow" :size="15" />查看公开书单</RouterLink></div></details></div></header>
    <div v-if="error" class="a-alert a-alert-error" role="alert"><AdminIcon name="info" /><div>{{ error }} <button v-if="verified" class="a-text-button" @click="exportCSV">导出草稿</button></div></div>
    <div v-if="notice" class="a-alert a-alert-success" role="status"><AdminIcon name="check" /><div>{{ notice }} <RouterLink v-if="lastCommit" to="/admin/tasks">查看发布进度 →</RouterLink></div></div>
    <div v-if="!verified" class="a-loading-state"><span v-if="loading" class="a-spinner" /><p>{{ loading ? '正在加载最新书单…' : '书单尚未加载成功' }}</p><button v-if="!loading" class="a-button" @click="unlock">重新加载</button></div>
    <template v-if="verified">
      <div class="a-master-detail a-book-layout" :class="{ 'a-detail-open': detailOpen }">
        <aside class="a-card a-master-list"><div class="a-search-row"><div class="a-search-input"><AdminIcon name="search" :size="18" /><input id="book-filter" v-model="filter" aria-label="查找现有书目" type="search" placeholder="搜索书名、编号或备注" /></div></div><div class="a-list-caption"><span>{{ books.length }} 部实体书</span><span>{{ visibleBooks.length }} 个结果</span></div><div class="a-gallery-list a-book-list"><button v-for="{book,index} in visibleBooks" :key="index" class="a-gallery-row" :class="{ 'is-selected': selected === index }" :disabled="saving || loading" @click="selectBook(index)"><span class="a-book-row-icon"><AdminIcon name="book" :size="19" /></span><span class="a-gallery-copy"><strong>{{ book['书名'] || book['日文名'] || '新书目' }}</strong><span>{{ book.ID || '未填写编号' }}<i>·</i>{{ book.sid ? `画廊 ${book.sid}` : '未关联数字版' }}</span></span><AdminIcon name="chevron" :size="15" /></button><div v-if="!visibleBooks.length" class="a-empty"><AdminIcon name="book" :size="30" /><h3>{{ books.length ? '没有匹配的书目' : '开始整理你的书单' }}</h3><p>{{ books.length ? '换个书名或编号试试。' : '添加书目，再关联收藏中的画廊。' }}</p><button v-if="!books.length" class="a-button" @click="addBook">新增书目</button></div></div></aside>
        <section class="a-card a-detail-pane"><template v-if="activeBook"><button class="a-button a-ghost a-mobile-back" @click="detailOpen = false"><AdminIcon name="back" :size="16" />返回书单</button><div class="a-section-heading"><div><span class="a-eyebrow">BOOK DETAILS</span><h2>{{ activeBook['书名'] || activeBook['日文名'] || '新书目' }}</h2></div><span class="a-badge" :class="activeBook.sid ? 'a-badge-accent' : 'a-badge-neutral'">{{ activeBook.sid ? '已关联数字版' : '未关联' }}</span></div>
          <div class="a-segmented" role="tablist" aria-label="书目编辑区域"><button id="book-details-tab" role="tab" :aria-selected="bookTab === 'details'" aria-controls="book-details-panel" @click="bookTab = 'details'">书目信息</button><button id="book-gallery-tab" role="tab" :aria-selected="bookTab === 'gallery'" aria-controls="book-gallery-panel" @click="bookTab = 'gallery'">关联画廊<span v-if="activeBook.sid" class="a-dot" /></button></div>
          <fieldset :disabled="saving || loading">
            <div v-show="bookTab === 'details'" id="book-details-panel" role="tabpanel" aria-labelledby="book-details-tab" class="a-form-stack"><div class="a-form-grid"><label class="a-field a-wide">中文书名<input v-model="activeBook['书名']" maxlength="5000" placeholder="输入书目名称" /></label><label class="a-field a-wide">日文书名<input v-model="activeBook['日文名']" maxlength="5000" placeholder="可选" /></label><label class="a-field a-wide">书目编号<input v-model="activeBook.ID" maxlength="5000" placeholder="必填，允许重复编号" /></label><label class="a-field">收价<input v-model="activeBook['收价']" inputmode="decimal" maxlength="5000" placeholder="可选" /></label><label class="a-field">原价<input v-model="activeBook['原价']" inputmode="decimal" maxlength="5000" placeholder="可选" /></label><label class="a-field a-wide">备注<textarea v-model="activeBook['备注']" rows="4" maxlength="5000" placeholder="记录版本、购买信息或其他说明" /></label></div><details class="a-disclosure"><summary>封面设置</summary><label class="a-field">本地封面文件名<input v-model="activeBook.cover" maxlength="5000" placeholder="留空使用关联画廊封面" /><span class="a-field-help">填写已存在的封面文件名，不需要完整路径。</span></label></details><div class="a-rule-footer"><button class="a-text-button" @click="bookTab = 'gallery'">{{ activeBook.sid ? '查看画廊关联' : '关联数字版本' }}<AdminIcon name="chevron" :size="15" /></button><button class="a-text-button a-danger-text" @click="removeBook">删除书目</button></div></div>
            <div v-show="bookTab === 'gallery'" id="book-gallery-panel" role="tabpanel" aria-labelledby="book-gallery-tab" class="a-form-stack"><div v-if="linkedGallery" class="a-linked-gallery"><span class="a-cover"><img v-if="linkedGallery.thumb" :src="linkedGallery.thumb" alt="关联书目封面" loading="lazy" referrerpolicy="no-referrer" /><AdminIcon v-else name="gallery" /></span><div><span class="a-badge a-badge-success">当前关联</span><strong>{{ linkedGallery.title_jpn || linkedGallery.title }}</strong><small>#{{ linkedGallery.gid }}</small></div><button class="a-text-button" @click="activeBook.sid = ''">取消关联</button></div><p v-else-if="activeBook.sid" class="a-inline-note">已关联画廊 {{ activeBook.sid }}，当前收藏中暂无该记录。</p><label class="a-field" for="gallery-match">查找画廊<div class="a-search-input"><AdminIcon name="search" :size="18" /><input id="gallery-match" aria-label="查找画廊" v-model="matchQuery" type="search" placeholder="书名、画廊 ID、链接或作者" /></div><span class="a-field-help">选择候选仅修改关联，不会覆盖书目名称与价格。</span></label><div class="a-match-shortcuts"><button class="a-button a-small" :disabled="!activeBook['书名']" @click="matchQuery = activeBook['书名']">用中文书名查找</button><button class="a-button a-small" :disabled="!activeBook['日文名']" @click="matchQuery = activeBook['日文名']">用日文书名查找</button></div><p v-if="matchingLoading" class="a-inline-note" role="status"><span class="a-spinner" />正在加载画廊匹配数据…</p><p v-if="matchWarning" class="a-alert a-alert-warning" role="status">{{ matchWarning }}</p><div class="a-matches"><article v-for="{gallery,reason} in matches" :key="gallery.gid"><span class="a-cover"><img v-if="gallery.thumb" :src="gallery.thumb" alt="" loading="lazy" referrerpolicy="no-referrer" /><AdminIcon v-else name="gallery" /></span><div><strong>{{ gallery.title_jpn || gallery.title }}</strong><small>#{{ gallery.gid }} · {{ gallery.category }} · {{ gallery.uploader }}</small><small>{{ reason }}</small></div><button class="a-button a-small" :disabled="activeBook.sid === String(gallery.gid)" @click="linkGallery(gallery)">{{ activeBook.sid === String(gallery.gid) ? '已关联' : '关联' }}</button></article><div v-if="matchQuery.trim() && !matches.length && !matchWarning && !matchingLoading" class="a-empty"><AdminIcon name="search" :size="28" /><h3>暂无匹配结果</h3><p>尝试较短的书名、作者或画廊 ID。</p></div></div><details class="a-disclosure"><summary>手动填写关联 ID</summary><label class="a-field">关联画廊 ID<input v-model="activeBook.sid" inputmode="numeric" maxlength="5000" /><span class="a-field-help">新关联必须存在于当前收藏中。</span></label></details></div>
          </fieldset></template><div v-else class="a-empty a-empty-detail"><AdminIcon name="book" :size="32" /><h2>选择一部实体书</h2><p>编辑书目信息，或新增一部书加入收藏。</p></div></section>
      </div>
      <footer class="a-savebar"><div class="a-save-state"><span :class="['a-save-indicator',{'is-dirty':dirty}]" /><div><strong>{{ saving ? '正在保存…' : dirty ? '书单有未保存修改' : lastCommit ? '已保存，等待发布' : '没有待保存的修改' }}</strong><small>{{ books.length }} 部书目 · 保存后等待前端发布生效</small></div></div><div class="a-toolbar"><button class="a-button a-export-button" :disabled="saving || loading" @click="exportCSV"><AdminIcon name="download" :size="16" />导出 CSV</button><button class="a-button a-primary" :disabled="!dirty || saving || loading" @click="save"><span v-if="saving" class="a-spinner" /><AdminIcon v-else name="check" :size="17" />{{ saving ? '正在保存…' : '保存更改' }}</button></div></footer>
    </template>
  </div>
</template>
