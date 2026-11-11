# 通用搜索与分页

Home、Printed、Daily、后台列表和画廊关联使用同一个 `GallerySearchInput.vue`。组件自身提供样式，直接打开任何页面均可使用；`public/admin` 只切换主题变量，交互和补全实现共用。

## 组件职责

- `v-model` 表示已提交查询；输入即时显示，统一 220ms 防抖提交，Enter 立即提交，清空立即生效。
- 中文输入法组合输入结束后才提交，组合期间不发起标签补全。
- 共用 `useSearchSuggestions.js`：150ms 补全防抖、取消过时请求、忽略迟到响应、焦点显隐、方向键和有效高亮。
- 每个实例生成独立的 input / listbox / option ID，关闭补全时移除 active descendant。
- 光标所在 token 可以替换为补全结果，后续搜索条件保留。
- 统一语法帮助；`gallery/book/plain` profile 控制字段说明与补全。书单提供 `id/name/jpname/sid`；plain 适合普通文字输入。
- Home 的分类按钮通过 actions slot 放入搜索行。标签编辑继续承担添加、删除和去重等编辑动作。
- 页面使用组件的 focus / clear / reset 接口处理外部重置，不再复制键盘、输入法或补全代码。

## 搜索执行

- `gallerySearch.js` 维护浏览器的 tokenizer、解析、AND / 排除 / OR、文本 / 标签匹配、光标 token 替换和书单字段适配。
- `backend/catalog.py` 维护 Python 端的同一语法和 SQL 条件组合；首页与后台画廊复用它。
- 后台书单经 `book_term_sql()` 适配书目字段和关联画廊，复用解析、条件组合及画廊条件生成。已关联画廊的人工覆盖参与匹配；未关联书目仍可按书名、编号、备注等检索。
- Printed、Daily 对已获取的数据使用浏览器匹配。Printed 继续传入现有的简转繁扩展；这是书单页面的匹配适配，不额外下载全收藏。
- 画廊 profile 的纯数字和完整 E-Hentai / ExHentai 链接按 gid 定位；书单 profile 的纯数字仍可查书目编号。
- 查询值始终作为 SQL 参数传递。公开展示与后台编辑保留各自可见范围。

JS 与 Python 各自运行在浏览器和服务器；通过 `test_catalog.py`、`test_search_contract.py` 的跨语言结果对照约束核心语法，而不是在页面里各复制一套实现。扩展字段时，需要同步 profile 适配和契约用例。

Home、Printed、Daily 的查询保存在 URL，刷新可恢复。翻页和结果加载仍由各页面按数据来源处理。

## 分页与验证

三个页面的上下分页直接使用 `Paginator.vue`。边框和间距由组件自身管理，统一无分割线、上下 10px / 左右 14px 内边距；页面不再额外套 toolbar / digi-pagination 等分页外壳。

自动验证覆盖：Node 查询及 token 替换、Python / JS 书单匹配一致性、画廊 ID / 链接、六处分页样式、跨页共用控件、IME、补全迟到响应、同页后台双实例、原有后台编辑流程。新增的 `browser_search.py` 仅使用本地静态资源与模拟 API，不操作生产数据。

本次是中等规模的现有逻辑收拢，未引入搜索服务、数据库迁移或新的运行依赖。后续交互修复集中在单个组件和补全 composable；新增数据类型通过 profile / matcher 适配。
