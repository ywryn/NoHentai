# NoHentai 开发交接

本文按仓库版本 `28bdbf7`（`SCHEMA_VERSION = 6`）核对。接手一个页面时，先定位它的路由和数据来源，再沿下面的组件关系找到最接近的现有页面。对外观做决定时，以当前代码和已验收的用户路径为准。历史评审和方案记录已归档至 `docs/archive/`，其中的提议需要与现状核对。

## 从任务找到入口

以下是浏览器的 hash 路由，例如搜索页实际地址为 `/#/search`。页面名、懒加载、旧链接重定向、历史滚动恢复都在同一处注册。公共导航、跳至正文入口和移动菜单由应用外壳提供。[路由表](web-static/src/router/index.ts) · [App.vue](web-static/src/App.vue)

| 改什么 | 先读哪个实现 | 数据和交互由谁负责 |
| --- | --- | --- |
| 首页收藏画廊 `/` | [Home.vue](web-static/src/components/Home.vue) | 页面把 URL 的查询、分类（`types`）、多选收藏夹（`fav`）、排序（`sort`）和页码交给服务端分页，把响应映射成列表项。改筛选条件重置页码，主动翻页支持浏览器后退，并在异步列表渲染后恢复滚动位置。 |
| 搜索 `/search` | [LiveAccess.vue](web-static/src/components/LiveAccess.vue) → [LiveSearch.vue](web-static/src/components/LiveSearch.vue) | 搜索 E/EX。前者验证访问权，并在详情、阅读器、翻译之间切换子视图；后者持有编辑中的条件、上次提交的条件、结果和游标。旧 `/live`、详情及阅读链接仍会重定向。 |
| 每日 `/daily`、书单 `/printed` | [DailySearch.vue](web-static/src/components/DailySearch.vue) · [Printed.vue](web-static/src/components/Printed.vue) | 每日展示同步好的分组及生成时的规则，书单组合书目和已关联画廊（按最新优先排序）。两页在已取得的数据上筛选和分页。书单还有简繁匹配与书目专属字段。 |
| 画廊详情 `/gallery/:gid`、`/search/:gid` | [GalleryDetail.vue](web-static/src/components/GalleryDetail.vue) | 两个入口共用封面、操作栏、信息卡、标签（含词典释义悬停）、预览和错误状态。来源决定取数方式和可展示的字段。操作栏读取 [useReadingProgress](web-static/src/composables/useReadingProgress.ts)（LRU 200），有进度时以 Split Button（`.gd-action-split`）合并「继续阅读 · 第 N 页」与「从第 1 页阅读」，另有「翻译」，浏览器承担返回。 |
| 两类详情下的 `read`、`translate` | [GalleryReader.vue](web-static/src/components/reader/GalleryReader.vue) · [GalleryTranslate.vue](web-static/src/components/GalleryTranslate.vue) | 沉浸页面各自管理工具栏，并通过 [pageImage.ts](web-static/src/utils/pageImage.ts) 共用页图加载与重试。阅读器顶栏支持直达「翻译当前页」（快捷键 `T`）及 `?` 快捷键说明，并支持 2 步前瞻预加载；翻译工作台通过 [useTranslateDrafts](web-static/src/composables/useTranslateDrafts.ts)（LRU 60）缓存页草稿。`/translate` 是独立的 [URL 输入入口](web-static/src/components/TranslateLookup.vue)，解析 gid 和 token 后进入工作台。 |
| 统计 `/data` | [DataAnalys.vue](web-static/src/components/DataAnalys.vue) · [TagCountTable.vue](web-static/src/components/TagCountTable.vue) | 聚合来自 `/api/stats`，标签表另有分页接口。Chart.js、矩阵图和页面样式随统计功能加载。 |
| 管理 `/admin/*` | [Admin.vue](web-static/src/components/admin/Admin.vue) → [AdminPanel.vue](web-static/src/components/admin/AdminPanel.vue) | 前者负责管理会话、导航、确认入口和管理主题。后者按 section 分发概览（含第一方访问量/独立访客）、记录编辑（含画廊批量显隐与增删标签）、服务配置、服务用量（本地额度与 xAI 账单）、任务、健康、备份等面板。`/admin/printed` 经 [PrintedEditor.vue](web-static/src/components/PrintedEditor.vue) 进入书目编辑。 |

## 组装一个和现有前台一致的页面

**以同类页面为参照。** 做画廊列表先打开首页，同时观察手机菜单收起、搜索补全展开、筛选生效、结果加载及失败后的布局。首页的标题卡、筛选区和结果区已有布局类，搜索页复用它们；书单、每日和统计各自保留适合其内容的页头。用下表选组件，再决定页面还缺什么。[首页布局](web-static/src/assets/Home.css) · [搜索页组装实例](web-static/src/components/LiveSearch.vue)

| 需求 | 可用组件及调用约定 |
| --- | --- |
| 输入关键词、补全标签 | [GallerySearchInput](web-static/src/components/GallerySearchInput.vue) 接受 `v-model`、可访问名称 `label`、`profile` 和 `variant`。画廊、书目、纯文本、上游搜索分别使用 `gallery/book/plain/live`。额外操作放入 `#actions`。输入法组合、光标处 token 替换、上下键选项、Enter/Tab 选中、迟到补全响应都已有处理。[补全逻辑](web-static/src/composables/useSearchSuggestions.js) |
| 同时筛分类/收藏夹、显示和清除条件 | [GalleryFilters](web-static/src/components/GalleryFilters.vue) 内含上述输入框、分类与收藏夹 Popover 和已选条件。父页传 `query`、`types`，首页还传 `counts`、`fav`、`favCounts` 与 `update:fav`，接收 `change(q, types)`；搜索页用 `profile="live"`、`submitting` 和单独的 `submit` 事件决定何时请求上游。 |
| 展示搜索结果、切换列表与封面 | [GalleryList](web-static/src/components/GalleryList.vue) 接受已经映射好的 `items`、`loading`、`emptyText`、`emptyHint`。照首页 `normalizedItems` 准备稳定的 `key`、`title`、`thumb`、`tags` 数组，以及适用的分类、评分和页数。站内目的地传 `to`，外部搜索传 `searchUrl`；组件据此生成真正可打开新标签页的链接。骨架、空结果、封面失败及两种视图由列表处理，请求失败和重试由父页处理。 |
| 有总页数的列表 | [Paginator](web-static/src/components/Paginator.vue) 接收 `page` 和总页数 `total`，发出 `go`。首页、每日、书单的上下分页连接同一个页码状态。E/EX 只返回上一批、下一批游标，沿用搜索页的批次按钮。 |
| 访问密码、图片加载阶段、评分 | [AccessPassword](web-static/src/components/AccessPassword.vue) 负责输入、提交、错误和返回，父级处理验证和票据。传 `v-model`、`prefix`、`label`、加载及错误状态。[ImageLoadProgress](web-static/src/components/ui/ImageLoadProgress.vue) 区分目录、地址解析和图片加载；[StaticRating](web-static/src/components/ui/StaticRating.vue) 用于只读评分。 |
| 管理记录与确认 | [RecordEditor](web-static/src/components/admin/RecordEditor.vue) 按记录类型复用列表、草稿和保存流程。画廊关联搜索与主列表搜索各用独立输入实例。共享确认入口由后台外壳提供，已有 [AdminConfirm](web-static/src/components/admin/AdminConfirm.vue) 和 [草稿工具](web-static/src/utils/adminDrafts.js)。 |

**视觉和状态归属。** Vue 在 [main.ts](web-static/src/main.ts) 注册 PrimeVue Aura，深色选择器为 `.my-app-dark`。[style.css](web-static/src/style.css) 定义前台字体、明暗配色、圆角、动效、触控目标及通用列表样式。正文、次要文字、背景、边框、强调色分别取 `--text-color`、`--muted-color`、`--surface-color`、`--border-color`、`--primary-color` 等对应变量。先看组件自身的 scoped 样式，再看页面引入的 CSS。阅读器使用 [reader.css](web-static/src/assets/reader.css) 的沉浸式配色，后台由 [admin.css](web-static/src/assets/admin.css) 和 [admin-v2.css](web-static/src/assets/admin-v2.css) 提供工作区样式。

- 图标从 [paths.ts](web-static/src/icons/paths.ts) 选择，通过 [AppIcon](web-static/src/components/ui/AppIcon.vue) 渲染，继承文字颜色。图标按钮的居中、点击面积和焦点样式由按钮承担；名称放在按钮上。品牌使用 BrandMark 和 BrandWordmark。图标规格、方向语义和品牌文件见[图标说明](web-static/src/icons/README.md)和[品牌说明](docs/branding.md)。
- 767px 及以下，公共页右上角是单列菜单。明暗主题、妈妈模式和适用页面的浏览视图在菜单内；桌面有对应工具按钮。新增一个列表入口时，同时检查 App 的导航项和 `showViewModeToggle` 路径判断。新页面进入时检查导航位置和按钮对齐，也检查亮色、暗色及窄屏。
- [useTheme](web-static/src/composables/useTheme.ts)、[useMomMode](web-static/src/composables/useMomMode.ts)、[useViewMode](web-static/src/composables/useViewMode.ts) 持有全局偏好。列表模式的内部值为 `card/cover`。妈妈模式写入 `localStorage['mom-mode']` 并更新 body 上的类；阅读设置和首页菜单调用同一个切换函数。新增入口可以采用所在面板的控件外观，状态仍从同一个 composable 读取。
- 页面独有的视觉调整限定在该页。改共享组件时按上表检查其他调用方，尤其是同页存在两个搜索框、深色后台、键盘焦点、短横屏和减少动效偏好的情况。安卓 Chrome 点按卡顿要在触屏路径复查；桌面缩窄可验证断点，不能证明手机上的响应时间。

## 三条容易改错的交互路径

### 搜索条件从输入走到结果

首页以 URL 为已生效的条件。输入默认 220ms 防抖，分类和页码由页面协调，并通过 AbortController 和请求版本丢弃过时结果。浏览器侧匹配器与服务端 SQL 解析分别在 [gallerySearch.js](web-static/src/utils/gallerySearch.js) 和 [catalog.py](backend/catalog.py)。修改通用搜索语义时，同时核对书单、每日和后台记录搜索。[搜索契约说明](docs/search.md)

E/EX 搜索有显式提交边界。输入、补全、清空、选择分类和打开带查询的链接都只改变草稿。搜索按钮占用语法按钮的位置，以点击瞬间的文本提交；主动翻批使用上次提交的条件。补全走本地标签接口，结果的中文标签在同一次搜索响应中用首页词典生成，缺译时显示原词。LiveAccess 用 KeepAlive 保留搜索结果，从详情返回可以继续浏览。回归时分别计数补全和 `/api/live/search`，一次提交后进入详情再返回，后者应恰好一次。[搜索结果及分页](web-static/src/components/LiveSearch.vue) · [上游转发实现](backend/live.py)

### 从详情进入阅读器

GalleryDetail 为本地和搜索来源提供同一套内容层级。搜索详情通过 `directory?details=true` 获取信息并复用首批预览，后续目录按需加载。向阅读器或翻译工作台传递 gid、token、页码；搜索来源还要保留 site 和相应的路由名。若改标签交互，核对展示译名、复制原始搜索表达式、按来源返回对应检索入口这三个动作。

[GalleryReader](web-static/src/components/reader/GalleryReader.vue) 建立 [useReader](web-static/src/composables/useReader.ts) 并以 `READER_KEY` 提供给子组件。BookView 和 ScrollView 负责排版及分页，PageImage 负责图片加载和重试，ReaderTopBar 负责设置，ThumbStrip 负责缩略图栏和页码跳转，当前页与 URL 同步。换一种阅读模式或数据来源，继续走这条共享链路。

手机图片在点按位置连续三次**双击**，依次进入两档放大、动画还原。倍率由图像和视口尺寸计算；两次放大之间的单击不推进缩放档位。左、中、右单击区域用于翻页或唤出工具栏，点击区保持透明。手势的延迟判定、移动阈值、事件抑制和还原集中在 [useReaderZoom](web-static/src/composables/useReaderZoom.ts)。阅读设置里的「妈妈模式」同样适用于书页和滚动模式。[设置面板](web-static/src/components/reader/ReaderTopBar.vue)

### 从详情进入翻译

[GalleryTranslate](web-static/src/components/GalleryTranslate.vue) 负责页图、缩略图、OCR 框、翻译结果及当前页请求序号。搜索来源复用阅读器的数据访问来按需取目录和图片，本地来源沿用画廊媒体接口。切页后到达的旧 OCR 或图片响应要按请求序号作废。OCR 与翻译是有成本的操作，保留用户主动识别和自动翻译设置各自的触发条件。

`/api/trans-verify` 发放搜索与翻译共用的 72 小时票据。管理员登录另有会话体系。AI 缺译时，服务端按配置和额度对缺失项使用 Google 兜底，前端保留逐条来源并显示提示。远程标签汉化使用本地词典，两条翻译路径的费用和调用条件不同。[翻译响应处理](web-static/src/utils/translationApi.js) · [翻译服务](backend/translation.py)

## 后端如何配合页面

| 工作 | 请求链路与修改位置 |
| --- | --- |
| 公共目录与统计 | [useGalleryData.js](web-static/src/composables/useGalleryData.js) → [FastAPI 入口](backend/main.py) → [catalog.py](backend/catalog.py)。首页用 `GET /api/galleries` 取得单页、分类/收藏夹计数及排序结果（由 `gallery_tags` 倒排索引加速），详情按 gid 取。书单、每日读取各自的数据集；统计由 [stats.py](backend/stats.py) 聚合；第一方页面访问与独立访客由 [router/index.ts](web-static/src/router/index.ts) 上报至 `POST /api/visits` → [traffic.py](backend/traffic.py)。已有页面通过 `watchPublicRevision` 在获得焦点或重新可见时核对版本。 |
| 上游搜索和图片 | [live.ts](web-static/src/utils/live.ts)、[pageImage.ts](web-static/src/utils/pageImage.ts) → `/api/live/{search,directory,image-url,image}` 与 `/api/page-image` → [live.py](backend/live.py)、[media.py](backend/media.py)、[upstream.py](backend/upstream.py)。浏览器路径是 `/search`，API 前缀仍是 `/api/live`。服务器按后台配置选择 E/EX，检查票据、限流及来源站点。搜索内容按请求转发，原图解析走非持久化路径。收藏阅读的媒体接口有自己的缓存行为。 |
| 保存管理记录 | [adminApi.js](web-static/src/utils/adminApi.js) 获取同源 Cookie 会话和 CSRF 值，向 `POST /api/admin` 发送 action。后端经 [admin.py](backend/admin.py) 分派到 [records.py](backend/records.py) 等模块（含 `gallery-batch` 批量显隐与增删标签）。记录编辑区分同步源、人工覆盖和合并后的展示值，保存带预期版本，同步维护 `gallery_tags` 索引，并写审计历史。关联搜索、重新登录、版本冲突时注意保留未保存草稿。[后台说明](docs/admin.md) |
| 同步和持久化 | [db.py](backend/db.py) 和 [migrations.py](backend/migrations.py) 管理 SQLite（当前 `SCHEMA_VERSION = 6`）。管理操作入队，[jobs.py](backend/jobs.py) 和 [schedules.py](backend/schedules.py) 由独立 worker 运行；抓取逻辑在 [app/](app/)。任务冻结配置、保存检查点，在发布事务内检查取消和版本，发布后清理检查点大结果并调度来源封面缓存（[cover_cache.py](backend/cover_cache.py)）。同步、记录编辑和公开读取应沿用已有版本更新路径，以便缓存失效并保留人工覆盖。[数据同步](docs/data-sync.md) |
| 服务健康与用量 | [WorkspaceOverview.vue](web-static/src/components/admin/WorkspaceOverview.vue)、[ServiceUsage.vue](web-static/src/components/admin/ServiceUsage.vue) → [operations.py](backend/operations.py)、[provider_usage.py](backend/provider_usage.py)。汇总后台服务状态、本地配额、xAI 账单与第一方访问统计。 |

生产运行数据来自 SQLite。仓库的 `web-static/public/data` 用作首次导入等用途，构建完成后会移除 `dist/data`。开发服务器将 `/api`、`/data`、`/media` 代理给 FastAPI；PWA 对运行时数据和静态资源有不同缓存策略。改数据优先从对应查询和写入路径入手。[Vite 配置](web-static/vite.config.ts) · [兼容数据接口](backend/public.py)

## 开发与验收

首次启动按 [README](README.md) 准备本地环境和数据。使用已初始化的开发库时，在仓库根目录启动 `.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000`，另一终端执行 `npm run dev --prefix web-static`，打开 `http://localhost:3000`。调试同步任务时另启 `.venv/bin/python -m backend.cli worker`。CI 的 Python、Node 版本及实际检查顺序见[工作流](.github/workflows/checks.yml)。

| 改动范围 | 最接近的已有验证 |
| --- | --- |
| 搜索、补全、分页、返回结果 | [browser_search.py](tests/browser_search.py) 验证 IME、同页多个搜索实例、手动搜索请求次数、搜索详情到翻译再返回。匹配语义还有 [跨端契约测试](tests/test_search_contract.py)。 |
| 菜单、视觉、键盘可达性 | [browser_layout.py](tests/browser_layout.py) 覆盖多宽度和明暗主题；[browser_modern_guidance.py](tests/browser_modern_guidance.py) 覆盖焦点、对话框、强制颜色和减少动效。 |
| 阅读、图片、翻译 | [browser_review.py](tests/browser_review.py) 覆盖触屏缩放、妈妈模式、缩略图栏跳页、图片阶段和切页后迟到的 OCR。涉及安卓手势时，再用 Android Chrome 走一次单击、双击、拖动、系统返回。 |
| API、数据写入、发布 | 在根目录运行 `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`。后端有独立的目录、每日同步、媒体、管理等测试。[browser_smoke.py](tests/browser_smoke.py) 在临时库和本机 Nginx 上做端到端验证。 |

前端依赖安装在 `web-static`。根目录的 `npm test` 运行 JS 测试，`npm run build --prefix web-static` 包含类型检查及完整构建。浏览器脚本使用构建后的资源，修改组件后先重建，再从根目录运行相应脚本，例如 `.venv/bin/python tests/browser_search.py`。浏览器依赖安装见 README。部署和回滚另见[部署文档](docs/vultr-deployment.md)。

交付 UI 改动时，说明复用了哪个现有页面或组件、改动影响哪些调用方，以及验证过哪些交互。以搜索页为例，截图能核对按钮和页头是否统一；请求计数能核对编辑条件是否产生额外消耗；从详情返回才能核对结果是否保留。三项回答的是不同问题。
