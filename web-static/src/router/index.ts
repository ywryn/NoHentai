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
    meta: { title: '日文查词' },
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  /**
   * 前进/后退恢复原滚动位置，其余情况回到顶部。
   * 此前未配置：翻页后停留在原滚动位置，用户点击底部「下一页」
   * 看到的是新一页的尾部。
   */
  scrollBehavior(to, _from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.meta.immersive) return false
    return { top: 0 }
  },
})

const BASE_TITLE = 'NoHentai | の変態'

/* 路由切换时更新标题，便于区分多标签页与浏览历史 */
router.afterEach(to => {
  const title = to.meta.title as string | undefined
  document.title = title ? `${title} · ${BASE_TITLE}` : BASE_TITLE
})

export default router
