# GalleryReader 重构设计文档

**日期：** 2026-05-19  
**范围：** 全量重写 `/gallery/:gid/read` 阅读器，参考 eHunter 3.1.0 实现所有功能（除 ZIP 打包下载）  
**原则：** 全新代码，不复用 `GalleryReader.vue` 旧实现，避免屎山

---

## 一、背景与目标

现有 `GalleryReader.vue` 是单文件实现，功能简陋：
- 仅支持书本翻页（无滚动模式）
- 无缩略图导航
- 无设置面板
- 无动画
- 无键盘快捷键完整支持

目标：参照 eHunter 的功能集，在现有 Vercel API 基础上重写为完整阅读体验。网络层（`/api/gallery-images`、`/api/image-url`）保持不变。

---

## 二、功能清单

| 功能 | 说明 |
|------|------|
| 书本模式（默认） | 单/双页翻页，含翻页动画 |
| 滚动模式 | 所有页垂直连续排列，原生懒加载 |
| 双页自动切换 | 宽度 ≥ 900px 时自动双页，否则单页 |
| 阅读方向 | 默认 RTL，可在设置中切换 LTR |
| 翻页动画 | slide（平移）/ flip（翻书）/ none，设置可切换 |
| 底部缩略图条 | 横向滚动，sprite 裁切显示，当前页高亮 |
| 全屏缩略图网格 | 覆盖层，点击跳页 |
| 设置面板 | 右侧抽屉，所有配置项，持久化到 localStorage |
| 键盘快捷键 | 方向键翻页、F/S/M/Escape |
| 移动端手势 | 滑动翻页，捏合/双击缩放交给浏览器原生 |
| 图片预加载 | goTo(n) 后自动预取 n±1~3 |
| 错误重试 | 单页失败显示重试按钮，支持 nlParam 换源重试 |
| 设置持久化 | localStorage key: `reader-settings` |
| ~~ZIP 打包下载~~ | 不实现 |

---

## 三、文件结构

```
web-static/src/
├── components/
│   └── reader/
│       ├── GalleryReader.vue      # 根容器：路由入口，provide 状态，组装各部件
│       ├── ReaderTopBar.vue       # 顶部栏：标题、页码、模式切换、设置按钮
│       ├── BookView.vue           # 书本模式：单/双页翻页 + 动画
│       ├── ScrollView.vue         # 滚动模式：全页垂直布局，loading="lazy"
│       ├── ThumbStrip.vue         # 底部缩略图条
│       ├── ThumbGrid.vue          # 全屏缩略图网格（teleport to body）
│       └── SettingsPanel.vue      # 设置抽屉（teleport to body）
├── composables/
│   └── useReader.ts               # 唯一状态源
└── assets/
    └── reader.css                 # 阅读器公共 CSS 变量与工具类
```

路由 import 路径从 `@/components/GalleryReader.vue` 改为 `@/components/reader/GalleryReader.vue`，路由定义本身不变。

---

## 四、状态管理：useReader.ts

`GalleryReader.vue` 调用 `useReader()`，通过 `provide('reader', state)` 注入全树，子组件 `inject('reader')` 消费。

### 4.1 状态结构

```typescript
interface ReaderSettings {
  readingMode: 'book' | 'scroll'
  bookDirection: 'rtl' | 'ltr'
  pageTurnAnimation: 'slide' | 'flip' | 'none'
  pagesPerScreen: 1 | 2          // 书本模式，宽屏时自动覆盖为 2
  widthScale: number             // 50~150
  scrollPageMargin: number       // px，仅滚动模式用
}

interface PageInfo {
  pageNum: number
  pageUrl: string
  thumbSprite: string
  thumbX: number
  thumbW: number
  thumbH: number
}

interface ImageData {
  imageUrl: string
  nlParam: string | null
}
```

### 4.2 对外接口

```typescript
// 画廊元数据
pages: Ref<PageInfo[]>
total: Ref<number>
galleryTitle: Ref<string>
initLoading: Ref<boolean>
initError: Ref<string | null>

// 阅读状态
currentPage: Ref<number>
effectivePagesPerScreen: ComputedRef<1 | 2>   // 综合 settings + 窗口宽度

// 图片加载
getImageUrl: (pageNum: number) => Promise<ImageData>
retryImage: (pageNum: number, nlParam?: string | null) => Promise<ImageData>
imageCache: Map<number, ImageData>

// 设置
settings: Reactive<ReaderSettings>
updateSetting: <K extends keyof ReaderSettings>(key: K, value: ReaderSettings[K]) => void

// 导航
goTo: (pageNum: number) => void
prev: () => void
next: () => void
```

### 4.3 关键逻辑

- **图片缓存**：`getImageUrl(n)` 先查 `imageCache`，命中返回；未命中调 `/api/image-url`，写缓存后返回
- **预加载**：`goTo(n)` 完成后，异步依次预取 `n+1, n-1, n+2, n-2, n+3, n-3`（书本双页模式额外包含 `n+3, n+4`）
- **设置初始化**：读 `localStorage('reader-settings')`，与默认值深度合并（防止字段缺失）
- **effectivePagesPerScreen**：`settings.pagesPerScreen === 2 && windowWidth >= 900 ? 2 : 1`

---

## 五、各组件设计

### GalleryReader.vue
- 挂载时初始化 `useReader()`，provide 全部状态
- `v-if` 在 `BookView` 和 `ScrollView` 间切换（非 `v-show`）
- 注册 / 卸载全局 `keydown` 事件
- 接收路由参数：`gid`（params）、`token`、`page`（query）

### ReaderTopBar.vue
- 显示：画廊标题（截断）、当前页/总页数
- 按钮：返回、模式切换（书本↔滚动）、设置
- 鼠标悬停时重置自动隐藏计时器

### BookView.vue
- 三槽（prev / cur / next）复用 DOM，翻页时交换引用
- CSS transition class 由 `settings.pageTurnAnimation` + 翻页方向决定：
  - `slide`：`transform: translateX(±100%)`
  - `flip`：`transform: rotateY(±90deg)` + `perspective`
- RTL：双页时右列 = currentPage（页码较小），左列 = currentPage+1（页码较大）；LTR 相反
- 点击区域：左 30% prev，右 30% next，中 40% 切换 TopBar

### ScrollView.vue
- 渲染所有页 `<img loading="lazy">`
- `IntersectionObserver` 监测当前视口中心页，更新 `currentPage`
- `goTo(n)` 调用 `el.scrollIntoView({ behavior: 'smooth' })`

### ThumbStrip.vue
- 固定在底部，高度 80px，横向 `overflow-x: auto`
- 每格使用 `background-image + background-position` 渲染 sprite 缩略图
- 当前页格子加高亮边框，自动 `scrollIntoView`

### ThumbGrid.vue
- `teleport to="body"`，全屏半透明遮罩 + 网格
- 同样使用 sprite 缩略图
- 点击格子：`goTo(n)` + 关闭网格

### SettingsPanel.vue
- `teleport to="body"`，右侧抽屉，宽 300px
- 设置项：
  - 阅读模式（radio）
  - 阅读方向（radio）
  - 翻页动画（radio，书本模式可用）
  - 页面宽度（range slider 50~150%）
  - 页间距（range slider，滚动模式可用）

---

## 六、键盘快捷键

| 按键 | 动作 |
|------|------|
| `←` / `A` | 视觉上向前（RTL 时页码递增，LTR 时页码递减） |
| `→` / `D` | 视觉上向后 |
| `Escape` | 退出阅读器（router.back）|
| `F` | 切换全屏缩略图网格 |
| `S` | 切换设置面板 |
| `M` | 切换书本/滚动模式 |

方向键与**视觉方向**绑定，而非页码方向。

---

## 七、移动端

- 书本模式：`touchstart` / `touchend` 水平滑动翻页，阈值 40px，`Math.abs(dx) > Math.abs(dy)` 判定
- 缩放：`touch-action: pinch-zoom`，浏览器原生处理，不自行实现
- TopBar：触摸后显示，4 秒淡出

---

## 八、错误处理

| 场景 | 处理方式 |
|------|---------|
| `gallery-images` API 失败 | 全屏错误页 + "返回"按钮 |
| 单张图片加载失败 | 格内显示错误占位 + Retry 按钮 |
| Retry 逻辑 | 删除缓存 → 若有 `nlParam` 拼接到 pageUrl → 重新调 `/api/image-url` |

---

## 九、设置默认值

```json
{
  "readingMode": "book",
  "bookDirection": "rtl",
  "pageTurnAnimation": "slide",
  "pagesPerScreen": 2,
  "widthScale": 100,
  "scrollPageMargin": 8
}
```

---

## 十、不在范围内

- ZIP 打包下载
- 放大镜（桌面端悬浮镜头）
- 自动翻页（Slideshow）
- nhentai 支持
- 自定义快捷键配置 UI
