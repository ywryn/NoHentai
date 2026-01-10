import { createRouter, createWebHashHistory } from 'vue-router';
// @ts-ignore
import Home from '@/components/Home.vue';
// @ts-ignore
import DataAnalys from '@/components/DataAnalys.vue';
// @ts-ignore
import GalleryDetail from '@/components/GalleryDetail.vue';
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
    path: '/gallery/:gid',  // ExHentai 动态路由
    name: 'GalleryDetail',
    component: GalleryDetail,
    props: true,  // 将参数作为props传递给组件
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
