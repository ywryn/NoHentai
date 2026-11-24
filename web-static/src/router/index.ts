import { createRouter, createWebHashHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

/**
 * 全部页面走动态 import 做路由级代码分割。
 * 此前是静态 import，首屏会一并加载 Chart.js（统计页）、opencc-js（书单）、
 * 翻译工作台及其词典依赖 —— 而大多数访问只停留在首页。
 */
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/components/Home.vue'),
    meta: { title: '收藏画廊' },
  },
  {
    path: '/data',
    name: 'DataAnalys',
    component: () => import('@/components/DataAnalys.vue'),
    meta: { title: '数据统计' },
  },
  {
    path: '/printed',
    name: 'Printed',
    component: () => import('@/components/Printed.vue'),
    meta: { title: '实体书单' },
  },
  {
    path: '/printed/edit',
    name: 'PrintedEditor',
    redirect: '/admin/printed',
  },
  {
    path: '/admin',
    component: () => import('@/components/admin/Admin.vue'),
    meta: { title: '站点管理', immersive: true },
    children: [
      { path: '', redirect: '/admin/overview' },
      { path: 'system', redirect: '/admin/health' },
      { path: 'printed', component: () => import('@/components/PrintedEditor.vue'), meta: { title: '管理书单' } },
      { path: 'translate', redirect: '/admin/services' },
      { path: 'credentials', redirect: '/admin/services' },
      ...['overview', 'galleries', 'daily', 'tasks', 'health', 'services', 'account', 'backups', 'history'].map(section => ({
        path: section,
        component: () => import('@/components/admin/AdminPanel.vue'),
        props: { section },
        meta: { title: '站点管理' },
      })),
    ],
  },
  { path: '/live', redirect: {name:'LiveSearch'} },
  { path: '/live/:gid', redirect: {name:'LiveDetail'} },
  { path: '/live/:gid/read', redirect: {name:'LiveReader'} },
  { path: '/search/:gid/translate', name: 'LiveTranslate', component: () => import('@/components/LiveAccess.vue'), meta: {title:'翻译工作台', immersive:true} },
  { path: '/search', name: 'LiveSearch', component: () => import('@/components/LiveAccess.vue'), meta: {title: '搜索'} },
  { path: '/search/:gid', name: 'LiveDetail', component: () => import('@/components/LiveAccess.vue'), meta: {title: '画廊详情'} },
  { path: '/search/:gid/read', name: 'LiveReader', component: () => import('@/components/LiveAccess.vue'), meta: {title: '阅读器', immersive: true} },
  {
    path: '/daily',
    name: 'DailySearch',
    component: () => import('@/components/DailySearch.vue'),
    meta: { title: '每日搜索' },
  },
  {
    path: '/gallery/:gid',
    name: 'GalleryDetail',
    component: () => import('@/components/GalleryDetail.vue'),
    props: true,
    meta: { title: '画廊详情' },
  },
  {
    path: '/gallery/:gid/read',
    name: 'GalleryReader',
    component: () => import('@/components/reader/GalleryReader.vue'),
    meta: { title: '阅读器', immersive: true },
  },
  {
    path: '/gallery/:gid/translate',
    name: 'GalleryTranslate',
    component: () => import('@/components/GalleryTranslate.vue'),
    meta: { title: '翻译工作台', immersive: true },
  },
  {
    path: '/translate',
    name: 'TranslateLookup',
    component: () => import('@/components/TranslateLookup.vue'),
    meta: { title: '翻译入口' },
  },
]

const history = createWebHashHistory()
const contentScrollPositions = new Map<string, { top: number; left: number }>()
let activeEntry: string | undefined
let activePosition: unknown

function publicScrollArea() {
  return document.querySelector<HTMLElement>('#main-content.public-scroll-area')
}

const router = createRouter({
  history,
  routes,
  scrollBehavior(to, from, savedPosition) {
    const area = publicScrollArea()
    if (!area || to.meta.immersive) return savedPosition || false

    if (savedPosition && activeEntry) {
      area.scrollTo(contentScrollPositions.get(activeEntry) ?? { top: 0, left: 0 })
    } else if (!from.matched.length || to.path !== from.path || to.query.page !== from.query.page) {
      area.scrollTo({ top: 0, left: 0 })
    }
    return false
  },
})

const BASE_TITLE = 'NoHentai | の変態'

/* 路由切换时更新标题，便于区分多标签页与浏览历史 */
router.afterEach((to, _from, failure) => {
  if (failure) return
  // afterEach runs before Vue replaces the view. Capture the outgoing history entry.
  const position = history.state.position
  const area = publicScrollArea()
  if (area && activeEntry && activePosition !== position) {
    contentScrollPositions.set(activeEntry, { top: area.scrollTop, left: area.scrollLeft })
  }
  activePosition = position
  activeEntry = `${position}:${to.fullPath}`

  const favicon = document.getElementById('site-icon') as HTMLLinkElement | null
  if (favicon) favicon.href = to.path === '/admin' || to.path.startsWith('/admin/') ? '/brand/favicon-b-v2.png' : '/brand/favicon-g-v3.png'
  const title = to.meta.title as string | undefined
  document.title = title ? `${title} · ${BASE_TITLE}` : BASE_TITLE
})

export default router
