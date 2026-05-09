import { createRouter, createWebHashHistory } from 'vue-router';
// @ts-ignore
import Home from '@/components/Home.vue';
// @ts-ignore
import DataAnalys from '@/components/DataAnalys.vue';
// @ts-ignore
import GalleryDetail from '@/components/GalleryDetail.vue';
// @ts-ignore
import Printed from '@/components/Printed.vue';
// @ts-ignore
import DailySearch from '@/components/DailySearch.vue';
// @ts-ignore
import GalleryReader from '@/components/GalleryReader.vue';
// @ts-ignore
import GalleryTranslate from '@/components/GalleryTranslate.vue';
// // @ts-ignore
// import TelegramFeed from '@/components/TelegramFeed.vue';
// 静态版本移除这些组件
// // @ts-ignore
// import Settings from '@/components/Settings.vue';
// // @ts-ignore
// import Reader from '@/components/Reader.vue';
 

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home,
  },
  {
    path: '/data',
    name: 'DataAnalys',
    component: DataAnalys,
  },
  {
    path: '/printed',
    name: 'Printed',
    component: Printed,
  },
  {
    path: '/daily',
    name: 'DailySearch',
    component: DailySearch,
  },
  // {
  //   path: '/telegram',
  //   name: 'TelegramFeed',
  //   component: TelegramFeed,
  // },
  {
    path: '/gallery/:gid',  // ExHentai 动态路由
    name: 'GalleryDetail',
    component: GalleryDetail,
    props: true,  // 将参数作为props传递给组件
  },
  {
    path: '/gallery/:gid/read',
    name: 'GalleryReader',
    component: GalleryReader,
  },
  {
    path: '/gallery/:gid/translate',
    name: 'GalleryTranslate',
    component: GalleryTranslate,
  },
  // 静态版本暂时移除这些路由
  // {
  //   path: '/settings',
  //   name: 'Settings',
  //   component: Settings,
  // },
  // {
  //   path: '/reader/:gid/:token',  // ExHentai 阅读器路由
  //   name: 'Reader',
  //   component: Reader,
  //   props: true,  // 将参数作为props传递给组件
  // },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

export default router;
