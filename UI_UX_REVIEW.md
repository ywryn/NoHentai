# NoHentai 前端 UI/UX 评估报告

> 评估范围：`web-static/` 全部页面、组件、样式与交互逻辑
> 评估视角：产品级 Web / 移动端 UI 设计与前端可用性
> 评估日期：2026-08-03　基于 commit `0409f49`
> **修复状态：P0 / P1 / P2 已实施，见下方「修复记录」。**

---

## 修复记录（分支 `ui-ux-improvements`）

| 提交 | 覆盖问题 |
|------|----------|
| `refactor(style)` 建立设计 token 单一来源并修复关键对比度 | §1.2 §1.4 §6.1 §7.1A §7.3C §10-1 |
| `fix(a11y)` 恢复键盘焦点可见性并补齐语义标记 | §6.2 §6.3 §4.2 §10-4 |
| `feat(nav)` 导航栏吸顶、当前页高亮，移动端改为底部标签栏 | §2.1 §2.2 §2.3 §2.4 §2.5 §4.5 |
| `perf(router)` 路由级代码分割、滚动恢复与 PWA 方向解锁 | §3.5 §6.3 §8.1 §9 |
| `feat(list)` 列表条目改为语义化链接并引入骨架屏 | §4.1 §4.2 §4.3 §4.4 §3.7 |
| `feat(home)` 搜索改即时过滤、筛选条件可视化、语法可发现 | §3.1 §3.2 §3.3 §3.4 §3.6 §3.8 |
| `feat(pages)` 修复 Printed / Daily / DataAnalys | §5.2 §5.3 §5.4 |
| `refactor(detail)` 合并桌面/移动双 DOM，标签改为可检索 | §5.1 §1.3 |
| `feat(reader,translate)` 沉浸式阅读与移动端可用性改造 | §8.2 §8.3 §8.4 |

**未实施（附原因）**：

- §8.2 接入已写好的 `SettingsPanel.vue` / `PageNav.vue` —— 按作者说明，这两个组件开发时即存在明显缺陷而被弃用。移动端设置面板改为在 `ReaderTopBar` 内自带折叠实现，页码跳转由缩略图侧栏与页目录承担。
- §9 `galleries.json` 拆分/分片 —— 涉及 Python 同步脚本与数据格式变更，超出前端改造范围。当前已通过路由级代码分割 + `StaleWhileRevalidate` 缓解首屏压力。
- §9 死代码清理 —— `TelegramFeed` / `TagExplorer` 是被主动注释停用的功能而非遗留垃圾，去留应由作者决定。

**实测收益**：首屏 JS 由单 chunk 1153 kB（gzip 671 kB）降至约 396 kB（gzip 105 kB）；深色主题次要文字对比度由 2.19:1 提升至 6.51:1。

---

## 0. 结论摘要

| 维度 | 评分 | 一句话 |
|------|------|--------|
| 视觉语言与一致性 | ★★★☆☆ | 深色优先的 slate 体系有品味，但 token 分裂成 3 套、断点有 9 个、中英文混排无规则 |
| 信息架构 | ★★★★☆ | 5 个页面职责清晰，Daily 的「筛选条件可视化」是全站最佳设计 |
| 交互逻辑完备性 | ★★★☆☆ | 阅读器完成度很高；列表页存在翻页不回顶、搜索行为不统一等实打实的可用性缺陷 |
| 移动端适配 | ★★☆☆☆ | 布局能响应，但触控目标普遍 30–32px、阅读器顶栏横向滚动藏内容、PWA 锁竖屏与双页阅读冲突 |
| 动效 | ★★☆☆☆ | 有若干不错的微动效，但无统一时长/缓动 token，**全站 0 处 `prefers-reduced-motion`** |
| 可访问性 | ★★☆☆☆ | 列表项不可键盘操作、导航焦点环被显式移除、深色主题次要文字对比度 **2.19:1** |
| 性能感知 | ★★☆☆☆ | 首屏需下载 9.4MB JSON、无代码分割、全站加载态只有 "Loading…" 文字 |

**最该先修的 5 件事**（详见第 8 节）：

1. 深色主题 `--muted-color` 对比度 2.19:1 —— 全站小字几乎不可读
2. 列表条目用 `<div @click>` —— 键盘不可达、无法「新标签页打开」
3. 翻页后不回到列表顶部
4. 导航栏无当前页高亮，且不吸顶
5. PWA manifest 锁 `portrait`，与阅读器双页横屏模式直接冲突

---

## 1. 视觉语言与设计系统

### 1.1 做得好的地方

- **深色优先的 slate 色板**（`#0f172a` / `#131f2e` / `#334155`）克制、专业，符合「归档工具」而非「消费产品」的定位，长时间浏览不刺眼。
- **浅色主题选了暖米色 `#faf8f5` 而非纯白**（`style.css:46-66`），这是很有意识的护眼决策，比多数项目考究。
- **共享类系统 `vm-*` / `gr-*`**（`style.css:234-674`）让 Home / Daily / Printed 三个页面的卡片与封面网格保持像素级一致，`GalleryList.vue` 作为唯一渲染出口，这是正确的抽象。
- 防主题闪烁的内联脚本（`index.html`）处理得当。

### 1.2 设计 token 分裂成三套（中）

同一批变量在三个地方各定义了一次：

| 位置 | 定义了什么 |
|------|-----------|
| `src/style.css:1-89` | `--primary-color`、`--row-*`、`--tag-*`、`--muted-color` … |
| `src/assets/Home.css:15-37` | **再次**定义 `--bg-color` / `--surface-color` / `--border-color`，并**独家**定义 `--hover-bg` |
| `src/composables/useTheme.ts:8-40` | 用 JS 把 `#0f172a` / `#faf8f5` 直接写成 `html.style` 内联样式 |

后果有两个：

- `--hover-bg` **只在 Home.css 里存在**。而 `Home.vue:448` 和 `DailySearch.vue:192` 都是无 `scoped` 的 `<style src>`，意味着它是「访问过首页才会注入全局」。GalleryDetail / DataAnalys / Translate 里所有 `var(--hover-bg)` 的 hover 态，在用户没先经过首页时会静默失效。这属于靠副作用工作的 CSS。
- JS 内联样式与 CSS 变量双轨制，改主题色要改两处，且内联样式优先级最高，未来很难被覆盖。

**建议**：token 收敛到 `style.css` 单一来源；`useTheme.ts` 只负责切 class，不写内联样式；Home.css 拆成 `scoped` 的页面样式 + 提取共享部分到全局。

### 1.3 断点体系缺失（中）

全站出现的断点：**480 / 600 / 640 / 700 / 720 / 900 / 1000 / 1024 / 1100** —— 9 个，且分布随意：

- `GalleryDetail.css:433` 桌面/移动切换用 **720px**
- `GalleryTranslate.vue:2261` 用 **640px**
- `Printed.css:284` 只有 **600px** 一个断点
- `DataAnalys.css` 用 **1024 / 600**

结果是不同页面在 640–720px 之间会呈现互相矛盾的形态（详情页已切移动版、翻译页还是桌面分栏）。

**建议**：定为 4 档 —— `480 / 768 / 1024 / 1280`，全站统一。

### 1.4 硬编码颜色穿透主题（中）

```css
/* style.css:273, 522 */
.vm-cover-img { background: #1a2640; }   /* 封面占位底色 */
.gr-thumb     { background: #1a2640; }   /* 缩略图占位底色 */
```

浅色主题下，没有封面的条目会显示一块**深海军蓝色块**，在暖米色背景上非常突兀。同类问题还有：

- `.home-type-pill.active { color: #c7ceff }`（`Home.css:285`）—— 靠 `.my-app-light` 额外覆盖打补丁
- `.gr-badge.*` 11 个分类色全部 `!important` 硬编码（`style.css:570-580`）
- `ReaderTopBar` 顶栏 `background: #3a7d44`（草绿）—— 与全站 slate/靛蓝色系毫无关系，视觉断裂最明显的一处

### 1.5 排版

- 字体栈 CJK 优先（`style.css:2`）是对的。
- 但 **11px 及以下的字号出现了 45 处**（`grep "font-size: 1[01]px"`）。11px 中文在移动端已接近可读下限，叠加下面 §6.1 的对比度问题会更糟。
- `style.css:179` 全局 `h1 { font-size: 3.2em }` 是 Vite 模板残留，实际被各页面覆盖，属于死规则。

---

## 2. 导航与全局框架（`App.vue`）

### 2.1 无当前页高亮（高）

`RouterLink` 会自动加 `router-link-active` 类，但**全项目 CSS 中没有任何一条针对它的规则**（已 grep 确认为 0 处）。用户在 5 个页面之间跳转时，导航栏永远看起来一模一样，无法定位自己在哪。

这是导航设计里最基础的一条，成本极低（一条 CSS）而收益很高。

### 2.2 导航栏不吸顶（中）

`.navigation-bar` 是普通文档流元素。首页有 3998 条数据、133 页，用户滚到列表底部翻页后，想切到 Daily 或改搜索词必须先滚回顶部。移动端尤其痛。

**建议**：`position: sticky; top: 0; z-index: 100`，配合半透明 + `backdrop-filter` 更佳。

### 2.3 触控目标过小（中，移动端）

| 元素 | 尺寸 | 标准 |
|------|------|------|
| `.icon-nav a` | 32×32（≤600px 时 30×30） | Apple HIG 44×44，Material 48×48 |
| `.theme-btn` / `.mom-mode-btn` / `.view-mode-btn` | 32×32 | 同上 |
| `.pag-btn` | 30×30 | 同上 |
| `.gr-tag` | 高 16px | 同上 |

移动端主导航的 5 个图标全部低于标准 27%，且间距只有 10px，误触率会很高。

### 2.4 图标语义弱

≤900px 时文字菜单换成纯图标（`App.vue:280-292`），只有 `title` / `aria-label` 而无可见文字。其中：

- Data Analys（柱状图）✓ 可识别
- Printed（书本）～ 勉强
- Daily Search（罗盘/定位）✗ 与「每日搜索」无语义关联
- Translate（文/A）～ 需要认知成本
- 右侧「妈妈模式」的眼睛图标 ✗ 完全无法从图标推断功能

**建议**：移动端改成底部 Tab Bar（图标 + 8–10px 文字标签），这也顺带解决了 §2.2 和 §2.3。

### 2.5 两套导航 DOM 同时渲染

文字菜单和图标菜单都在 DOM 里，靠 `display: none` 切换。DOM 体积翻倍，且屏幕阅读器会读到两组重复的导航链接。可用 `v-if` + 一个 `useMediaQuery` 解决。

---

## 3. 首页（`Home.vue`）

### 3.1 交互模型自相矛盾（高）

同一个搜索框里存在**两种反馈模型**：

- 主搜索是**提交式**：必须按 Search 按钮或回车（`Home.vue:390`）
- 标签联想是**输入即出**：`tagSuggestions` 是 computed，输入 2 个字符就弹（`Home.vue:185-224`）

用户看到下拉实时响应，会自然推断列表也在实时过滤，但列表纹丝不动。更严重的是：**Printed 页面的同款搜索框是即时过滤的**（`Printed.vue:324` 的 `filteredItems` computed）。两个视觉完全相同的控件，行为相反。

**建议**：统一为 250ms 防抖的即时过滤（3998 条客户端过滤性能完全够），保留回车提交作为兼容。

### 3.2 高级语法的发现性几乎为零（高）

首页支持一套相当强的查询语法（AND / `-排除` / `~OR` / `"短语"` / `term*` / `tag$` / `title:` `uploader:` `f:` `m:` `a:` …，见 `Home.vue:269-341`），这是这个站点真正的差异化能力。

但它的**唯一入口是搜索框右侧一个 12px 的 `?` 字符**（`Home.vue:28-34`）——无按钮外观、无边框、无 hover 提示，`--muted-color` 颜色（见 §6.1，对比度 2.19:1）。绝大多数用户永远不会发现这个功能存在。

而且 Printed 页面支持额外的 `id:` `name:` `jpname:` `sid:` 字段（`Printed.vue:250`），**完全没有任何说明入口**。

**建议**：
- `?` 改成有边框的图标按钮，或直接在 placeholder 里给示例：`Search… 试试 f:"lolicon$" -webtoon`
- 首次访问时在搜索框下方展示 3 个可点击的示例查询 chip
- Printed 补上自己的语法说明

### 3.3 标签联想下拉的交互缺陷（中）

`Home.vue:35-46` 的联想列表：

- **无键盘导航** —— 没有 ↑↓ 选择、Enter 确认，只能用鼠标点。对一个「打字过程中弹出的下拉」来说这是硬伤。
- **无 role/aria** —— 不是 `role="listbox"`，无 `aria-activedescendant`，屏幕阅读器完全感知不到它出现了。
- **不会失焦关闭** —— 没有 blur / Escape / 点击外部的关闭逻辑，只在 token 变化时才消失。
- 最多 8 条，每次输入都要遍历完整 translations（约 4 万个标签）做打分排序，无防抖 —— 快速打字时每个字符触发一次全量扫描。

### 3.4 筛选状态不可见、不可撤销（中）

- 分类 pill **单选**（`toggleType` 逻辑，`Home.vue:392`），无法「Doujinshi + Manga」组合筛选。
- 没有统一的「当前筛选条件」区域。选了分类 + 输入了查询后，用户看不到一个可逐项移除的条件列表。
- `Clear` 按钮同时清空搜索词**和**分类（`Home.vue:391`），但按钮只写「Clear」，用户预期可能只是清输入框。
- 各分类的**结果数量不显示** —— pill 上没有 count，用户不知道点下去有没有结果。

对比一下：Daily 页面把筛选条件做成了 chip 可视化（做得很好），首页反而没有。

### 3.5 翻页不回顶（高）

`goToPage()`（`Home.vue:424`）只改数据不动滚动位置，且 `router/index.ts` **没有配置 `scrollBehavior`**（已确认）。

实际后果：用户滚到页面底部，点底部分页器的「›」，页面内容换了但滚动位置不变 —— 用户看到的是**新一页的最后几条**，必须手动滚回顶部才知道这页从哪开始。这是每次翻页都会遇到的高频缺陷。

Printed / DailySearch 有完全相同的问题。

**修法**：`router` 加 `scrollBehavior: () => ({ top: 0 })`，或在 `goToPage` 里 `window.scrollTo({ top: 0, behavior: 'smooth' })`。

### 3.6 分页器设计

- 只有「首 / 前 / 输入框 / 后 / 末」，**没有页码列表**。133 页的情况下，用户失去了「大概在什么位置」的空间感。
- 无「每页条数」选择器，`perPage` 硬编码 30（`Home.vue:161`）。
- 顺带一提：**CLAUDE.md 写的是「每页 25 条」，实际是 30** —— 文档已漂移。
- 上下两个分页器共用同一个 `pageJumpValue` ref，两处 input 会同步变化，这个处理是对的。

### 3.7 加载体验（中）

```js
// Home.vue:430-445
allGalleries.value = await loadGalleries()     // 5.5 MB
...
loadTranslations().then(data => {              // 3.9 MB
  translationData.value = data
  filterAndPaginateData(...)                   // ← 全量重渲染
})
```

- 首屏需要 **5.5MB + 3.9MB = 9.4MB** 未压缩 JSON（gzip 后仍有约 1.5–2MB）。4G 下首屏白屏数秒，弱网下更糟。
- 加载态是一行文字 `Loading…`（`GalleryList.vue:23`），**全站没有任何骨架屏**。
- translations 到达后会**再次全量重算并重渲染列表**，用户会看到标签从英文突然跳成中文、行高变化的二次跳动（layout shift）。

**建议**：
- `galleries.json` 拆成「列表所需精简字段」+「详情按需加载」两份，或做分片
- 列表加骨架屏（沿用 `gr-*` 结构做灰块即可）
- translations 到达后只更新标签文本，不重跑整个 filter + paginate

### 3.8 隐藏 SEO 文本

`Home.vue:3-6` 有一段 `position: absolute; left: -10000px` 的隐藏关键词段落（`Home.css:39-46`）。这是搜索引擎明确列为灰色手法的 off-screen text，且本项目是纯静态 SPA 无 SSR，实际收益极低。考虑到站点性质，建议直接删掉。

---

## 4. 列表组件（`GalleryList.vue`）—— 全站复用，问题影响面最大

### 4.1 条目不是链接（高 · 可访问性 + 可用性）

```vue
<article class="gallery-row" @click="$emit('click', item)">   <!-- 卡片模式 -->
<div class="vm-cover-card" @click="$emit('click', item)">     <!-- 封面模式 -->
```

用 `div` / `article` + `@click` 模拟链接，代价是：

- **键盘用户完全无法访问列表** —— 无 `tabindex`、无 `role`、Tab 键跳不到、Enter 无响应
- **无法中键 / Cmd+点击在新标签页打开** —— 对一个「浏览大量画廊」的站点来说，这是个每天都会用到的功能
- **鼠标悬停不显示目标 URL**，无法预判要去哪
- 屏幕阅读器读到的是一段无语义的文本块

**修法**：改成 `<RouterLink :to="...">`，用 CSS 去掉默认样式即可。Printed 的「无匹配元数据」条目才需要保留 button 形态。

### 4.2 图片缺 alt

全项目 12 个 `<img>` 只有 2 个有 `alt`（已 grep 确认）。`GalleryList.vue` 的封面图和缩略图都没有，屏幕阅读器会读出图片文件名或直接跳过。

### 4.3 标签渐隐不可展开

`.gr-tags` 用 `mask-image: linear-gradient(to right, black 70%, transparent)`（`style.css:598`）做溢出渐隐 —— 视觉上很优雅，但被截断的标签**没有任何方式查看**（不能横滑、不能展开、不能 hover 显示全部）。用户知道有更多标签却拿不到。

### 4.4 封面模式信息密度失衡

封面模式（`vm-cover-*`）只显示 badge / 页数 / 标题，**丢掉了评分、日期、标签**。而卡片模式全都有。两种视图不是「同一数据的不同布局」而是「不同的数据集」，用户切换视图会莫名其妙丢信息。

### 4.5 视图切换按钮位置

视图切换（卡片/封面）放在**全局导航栏**（`App.vue:110`），但它只影响 Home / Daily / Printed 三个列表页。在详情页、统计页、阅读器里这个按钮依然显示且可点，但完全没有效果 —— 违反「控件应作用于当前上下文」的原则。

---

## 5. 各页面专项

### 5.1 画廊详情页（`GalleryDetail.vue`）

**桌面 / 移动两套完整 DOM 同时存在**（`:6` 和 `:111`，靠 `GalleryDetail.css:433` 的 `display` 切换）：

- DOM 体积翻倍
- **页面里有两个 `<h1>`**，两个相同的 `Tags` 标题、两个 ToggleSwitch —— 屏幕阅读器会读两遍全部内容
- 维护成本翻倍：改一处要记得改两处

**标签点击 = 复制搜索语法**（`:430-443`）：

- 交互本身有价值，但**没有任何可发现性提示** —— 无 hover 文案、无复制图标、`cursor` 也没有特殊化说明
- 反馈方式是把标签文字整个替换成「已复制」1.2 秒 → **标签宽度变化导致整行重排跳动**
- 更符合直觉的行为其实是「点击标签 → 跳转首页并用该标签搜索」。当前实现让用户必须手动切页面再粘贴。建议：点击跳转，长按/右上角小图标复制。

**「Browse Pages」按需加载缩略图**是个好决策（省流量、省 API 调用），但按钮上没说明它会请求外部服务且可能失败。

**文案语言混乱**：这个页面同时出现 `Gallery Detail` / `Taxonomy` / `Posted` / `Uploader`（英文）和「已复制」/「此画廊为 ExHentai 独占，云服务器 IP 被 Cloudflare 拦截…」（中文长句）。全站范围看：Home / Detail / Data 是英文，Printed / Translate / Reader 是中文，**没有任何规则**。

### 5.2 统计页（`DataAnalys.vue`）

- 结构（热力图 → 季度趋势 → 分类饼图 → 标签柱状 → 命名空间表格）清晰，**构建时预计算 `stats.json`** 是很好的架构决策，首屏零计算。
- **关键信息全部依赖 hover**：图表数值靠 Chart.js tooltip，表格的标签翻译和介绍靠 `v-tooltip`（`:97-101`）。**触屏设备完全拿不到这些信息** —— 移动端用户看到的是一堆没有数值的图和一列没有解释的英文标签。
  - 建议：图表启用数据标签（`chartjs-plugin-datalabels`）或点击展开详情面板；表格的翻译直接作为第二列显示而非 tooltip。
- 「Show All / 5 年」切换是个 ToggleSwitch 配文字 `Show All`，语义不如两个分段按钮（`5Y` / `All`）直观。

### 5.3 实体书单（`Printed.vue`）

- **搜索行为与首页不一致**（即时 vs 提交式），见 §3.1。
- 「未匹配元数据」的条目点击后弹 toast「未匹配元数据」—— 这是个**死路**：告诉用户失败了，但不提供任何出路。建议改成跳转 EX 搜索该书名，或提供「复制书名」。
- toast 有进出场 `Transition`（`:449`），是全站少数几个完整的微动效，做得好。
- 只有一个 600px 断点，中等屏幕（600–1024px）下布局未做优化。
- `watch(currentPage)` 里的 `router.replace({ query: v > 1 ? { page } : {} })`（`:359`）会**清空 query 里的其它参数**。目前只有 page 所以无害，但一旦加入搜索词同步 URL 就会互相冲掉。

### 5.4 每日搜索（`DailySearch.vue`）

**这是全站信息设计最好的一页**：Group pill + 筛选条件 chip + 「生成时间 / 起始日期 / 总数」元信息，把「这批数据是怎么来的」完整讲清楚了。这个模式值得反向移植到首页。

但：

- **chip 是纯展示却长得像控件**（有边框、圆角、主题色、26px 高度）—— 典型的 affordance 误导。用户会尝试点击「-webtoon」去掉这个排除条件，结果毫无反应。
  - 要么做成可交互（点击临时增删条件，客户端重算），要么弱化视觉（去边框、降饱和度、加「条件」前缀标签）。
- **排除 chip 只是变红去掉 `-` 前缀**（`:28`），CLAUDE.md 里写的「红色 + 删除线」在代码里**并不存在**（无 `text-decoration: line-through`）。红色在 UI 惯例里表示「错误/危险」，用来表示「排除」语义不明确。建议保留 `−` 前缀 + 删除线，红色降饱和。
- **切换 Group 不写 URL**（只有 `page` 写了，`:141`），刷新后必回 Group 1，也无法把某个 Group 分享出去。而且切 Group 时 `router.replace` 会把 `page` 清掉。
- 无跨 Group 搜索/筛选 —— 用户只能在预设的 3 组里被动浏览。

---

## 6. 可访问性（全站）

量化结果（grep 全项目）：

| 检查项 | 结果 |
|--------|------|
| `prefers-reduced-motion` | **0 处** |
| `focus-visible` | 2 处 |
| `aria-*` 属性 | ~8 处 |
| `<img alt="">` | 12 个 img 中 2 个有 |
| 语义化可点击元素 | 列表项全部为 `div`/`article` |
| `<html lang>` | `en`（内容大量中文） |

### 6.1 深色主题次要文字对比度 2.19:1（高 · 最严重）

```css
--muted-color: #475569;   /* 深色主题 */
--row-bg:      #131f2e;
```

按 WCAG 2.1 相对亮度公式计算：**对比度 = 2.19:1**，而正常文本要求 4.5:1、大文本 3:1。**连非文本 UI 元素的 3:1 都不达标。**

这个颜色被用在（不完全统计）：

- `.gr-pages` / `.gr-date` / `.gr-fav`（12px 页数、日期、收藏夹）
- `.vm-cover-id` / `.vm-cover-pages`（10px）
- `.home-eyebrow` / `.home-filter-eyebrow`（11px 大写字母）
- `.home-search-input::placeholder`
- `.home-search-help`（那个 `?` 按钮）
- `.pag-btn` 未激活态、`.pag-jump-total`
- `.daily-meta`、`.gr-thumb-placeholder`、`.empty-state`

也就是说**深色主题下几乎所有 10–12px 的次要信息都处在不可读状态**，叠加 §1.5 的小字号问题后更糟。

对照：浅色主题的 `--muted-color: #64748b` 在白底上是 **4.76:1**，是达标的。所以这是深色主题独有的回归。

**修法**：深色 `--muted-color` 从 `#475569` 提到 `#94a3b8`（约 6.5:1）或至少 `#64748b`（约 3.4:1，仅够 UI 元素）。这是一行 CSS 的改动，收益极大。

**其它对比度问题**：

- `--primary-color: #646cff` 在 `#0f172a` 上 = **4.36:1**，正文文本刚好不达标
- `.gr-badge.yellow` 白字 `#fff` 在 `#d6a922` 上 = **2.20:1**，`.gr-badge.gold`（`#d4af37`）同理。分类徽章在浅色主题下尤其难读

### 6.2 焦点指示被显式移除（高）

`style.css:201-204` 有全局焦点环：

```css
button:focus, button:focus-visible { outline: 4px auto -webkit-focus-ring-color; }
```

但被组件逐个覆盖掉了：

- `ThemeToggle.vue`：`.theme-btn:focus { outline: none }`
- `MomModeToggle.vue`：`.mom-mode-btn:focus { outline: none }`
- `Home.css:353`：`.pag-jump-input { outline: none }`
- `ReaderTopBar.vue`：`.tb-select { outline: none }`

结果：键盘用户 Tab 到导航栏右侧三个按钮、分页输入框、阅读器所有下拉时**完全没有视觉焦点提示**。这是 WCAG 2.4.7 的直接失败。

**修法**：把 `outline: none` 换成自定义的 `:focus-visible` 样式（如 `box-shadow: 0 0 0 2px var(--primary-color)`），不要裸移除。

### 6.3 其它

- `index.html` 的 `lang="en"` 与大量中文内容不符 —— 屏幕阅读器会用英文发音引擎读中文。改为 `lang="zh-CN"`。
- **路由切换不更新 `document.title`**（全项目 0 处 `document.title`）—— 所有页面浏览器标签都叫「NoHentai | の変態」，多标签页无法区分，浏览历史也无意义。
- 妈妈模式依赖 `:hover` 解除模糊（`style.css:100-106`）—— **触屏设备没有 hover**。移动端要么点一下触发 sticky hover 后无法取消，要么完全无法查看。这个功能在移动端基本是坏的。建议改成点击 toggle 单张图片的模糊状态。
- `style.css:538` 的 `.mom-mode .gr-thumb img { filter: blur(6px) }` 与 `:92` 的 `!important` 规则冲突（前者永远不生效），属于冗余死代码。

---

## 7. 动态效果

### 7.1 现状盘点

| 位置 | 效果 | 时长 |
|------|------|------|
| 主题切换 | 背景/文字色过渡 | 0.3s |
| 卡片 hover | `translateY(-2px)` + 边框色 | 0.15s |
| 导航 hover | `translateY(-1px)` + 背景 | 0.3s |
| 分页按钮 | 背景/颜色 | 0.12s |
| 阅读器翻页 | slide / flip(3D rotateY) / none | 0.28s |
| Printed toast | 进出场 | — |
| 翻译词卡 | `scale(0.96)` + opacity | 0.15s / 0.12s |
| 阅读器 spinner | 旋转 | 0.8s |

### 7.2 问题

**A. 无统一的动效 token（中）**
时长散布在 0.12 / 0.15 / 0.2 / 0.28 / 0.3s，缓动几乎全是默认 `ease`。同一次交互里不同元素以不同速度响应（如 hover 时边框 0.15s、背景 0.12s），细看会有「不同步」的廉价感。

**建议**：定义 `--dur-fast: 120ms` / `--dur-base: 200ms` / `--dur-slow: 320ms` 和 `--ease-out: cubic-bezier(.2,.8,.2,1)`，全站引用。

**B. 全站 0 处 `prefers-reduced-motion`（高 · 可访问性）**
阅读器的 `flip` 动画是 `perspective(1200px) rotateY(±90deg)` 的 3D 翻转，对前庭功能敏感人群可能诱发不适。用户虽然可以在阅读器设置里手动关，但**系统级的减少动态偏好被完全忽略**。这是 WCAG 2.3.3 的相关条款。

**修法**：
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .01ms !important;
    transition-duration: .01ms !important;
  }
}
```

**C. `transition: all` 的滥用（低–中）**
`style.css:194`（全局 button）、`App.vue:178`（icon-nav）、`ThemeToggle`、`MomModeToggle` 都用了 `transition: all`。它会把 `width` / `height` / `padding` 等触发 layout 的属性一并纳入过渡，既有性能开销也让行为不可预期。应显式列出 `background-color, border-color, color, transform`。

**D. 缺失的动效（中）**
- **路由切换零过渡** —— 页面之间是硬切，SPA 感全无
- **无骨架屏 / 加载占位动画** —— 所有加载态都是静止的 `Loading…` 文字
- **列表/分页切换零过渡** —— 30 条数据瞬间整体替换，视觉上是「闪一下」
- **详情页缩略图展开无动画** —— 内容直接撑开，造成大幅 layout shift

这些恰恰是用户感知「流畅度」的主要来源。当前项目的动效集中在了 hover 这类低价值场景，而高价值的**状态转换**场景全是空的。

---

## 8. 移动端专项

### 8.1 PWA manifest 锁竖屏，与阅读器冲突（高）

```js
// vite.config.js
manifest: { orientation: 'portrait', ... }
```

而阅读器的核心功能之一是**双页对开模式**（`useReader.ts` 默认 `pagesPerScreen: 2`）—— 双页阅读在竖屏手机上毫无意义，必须横屏。安装为 PWA 后用户被锁死在竖屏，双页模式永远用不了。

而且双页的启用条件是 `windowWidth >= 900`（`useReader.ts:effectivePagesPerScreen`），主流手机横屏宽度约 844–932px，**大量机型横屏后依然拿不到双页**。

**修法**：`orientation` 改 `any`；双页阈值从 900 降到 768，或改用 `aspect-ratio > 1` 判断。

### 8.2 阅读器顶栏横向滚动藏内容（高）

`ReaderTopBar.vue` 在 40px 高的单行里塞了：返回 + 阅读模式 + 同屏页数 + 阅读方向 + 翻页动画（4 个 `<select>`）+ 缩略图栏 + 页目录（2 个 toggle）+ 页码 + 关闭。

窄屏靠 `overflow-x: auto` + `scrollbar-width: none`（**隐藏滚动条**）容纳。后果：

- 移动端用户看到的是被截断的一行，**没有任何可以横滑的视觉暗示**（滚动条被隐藏了）
- 「页目录」「关闭」等按钮完全在屏幕外，用户会以为功能不存在
- 每个 `<select>` 高约 20px，远低于触控标准

讽刺的是，**项目里已经有一个写好的 `SettingsPanel.vue`（215 行）—— 但它从未被任何组件引用**（已 grep 确认为死代码）。这个抽屉式设置面板正是移动端需要的正确形态，只是没接上。

同样死掉的还有 `PageNav.vue`（114 行的页码跳转条），导致阅读器**没有任何页码跳转 UI**，只有顶栏一个纯文字计数和左侧缩略图列表。

**建议**：顶栏只留「返回 / 页码 / 设置齿轮 / 目录」四个 44px 按钮，把 4 个 select 移进已经写好的 `SettingsPanel`，并挂上 `PageNav`。

### 8.3 阅读器移动端其它缺失

- **点击区不可见、无首次引导**：左 30% / 中 40% / 右 30%（`BookView.vue`），新用户不知道点哪。且**中间 40% 区域什么都不做** —— 按行业惯例这里应该 toggle UI 显隐（沉浸阅读）。
- **无进度条**：3998 页的画廊只有「12 / 340」文字，缺少空间感。
- **顶栏永远占位**：40px 常驻，无法隐藏，破坏沉浸感。
- **滑动无跟手**：`onTouchStart/End` 只判断位移是否 > 40px（`BookView.vue`），翻页是离散的，没有手指拖动时的实时位移反馈。这是移动漫画阅读器的基本体验。
- **缺少 Fullscreen API / 屏幕常亮**。
- **`router.back()` 退出**：用户若直接粘贴 URL 进入阅读器，`back()` 会把他们带离本站。应改为 `router.push` 到详情页。

### 8.4 翻译工作台移动端对照断裂（中）

`≤640px` 时布局从左右分栏变成上下堆叠，且 `.gt-workbench` 变成 `height: auto` 长滚动（`GalleryTranslate.vue:2261-2292`）。

后果：**图片上的 OCR 框在屏幕上方，识别结果/译文列表在下方**，用户要对照原文和译文必须反复上下滚动，两者不可能同屏。这直接破坏了这个页面的核心价值。

**建议**：移动端改为「图片全屏 + 底部可拖拽 sheet」，sheet 支持 25% / 60% / 90% 三档高度，实现同屏对照。

此外「功能设置」折叠面板里塞了 OCR 三选一分段控件 + 显示开关 + 自动 + 学习共 4 行，在 45% 宽的侧栏（900px 断点）里会非常拥挤；词性图例只有 6 个色点无文字，必须 hover 才知道含义（触屏拿不到）。

---

## 9. 性能与工程

- **无路由级代码分割**：`router/index.ts` 全部使用静态 `import`。首屏就会加载 Chart.js（统计页）、opencc-js（Printed）、`GalleryTranslate.vue`（2295 行 + kuromoji 相关）—— 大部分用户从不访问这些页面。改成 `() => import(...)` 是零风险的显著优化。
- **9.4MB JSON 首屏加载**（见 §3.7）。
- **PWA `NetworkFirst` + 10s 超时** 应用在 `/data/*.json` 上：弱网时用户要等满 10 秒才回落到缓存。对这种「一天更新一次」的数据，`StaleWhileRevalidate` 是更好的策略 —— 立即出缓存内容，后台更新。
- **死代码**：`SettingsPanel.vue`(215) + `PageNav.vue`(114) + `TagExplorer.vue`(260) + `TagExplorer.css`(246) + `TelegramFeed.vue`(1099) ≈ **1934 行**未被路由引用（TelegramFeed 路由已注释）。约占前端源码 16%。
- **CSS 全局泄漏**：`Home.vue:448` 和 `DailySearch.vue:192、194` 的 `<style>` 均无 `scoped`，Home.css 的 549 行样式会全局注入并影响其它页面。

---

## 10. 优先级修复清单

### P0 — 影响所有用户，成本极低

| # | 问题 | 位置 | 工作量 |
|---|------|------|--------|
| 1 | 深色 `--muted-color` 对比度 2.19:1 | `style.css:80` | 1 行 |
| 2 | 翻页不回到顶部 | `router/index.ts` 加 `scrollBehavior` | 3 行 |
| 3 | 导航栏无当前页高亮 | `App.vue` 加 `.router-link-active` 样式 | 5 行 |
| 4 | `<html lang="en">` → `zh-CN` | `index.html:2` | 1 行 |
| 5 | 加 `prefers-reduced-motion` 全局降级 | `style.css` | 6 行 |
| 6 | PWA `orientation: portrait` → `any` | `vite.config.js` | 1 行 |
| 7 | 路由懒加载 | `router/index.ts` | 10 行 |

### P1 — 核心体验，1–2 天

| # | 问题 | 位置 |
|---|------|------|
| 8 | 列表条目改为 `<RouterLink>`（键盘可达 + 新标签打开） | `GalleryList.vue` |
| 9 | 移除各处 `outline: none`，改用 `:focus-visible` | 4 个组件 |
| 10 | 导航栏 sticky + 移动端触控目标提到 44px | `App.vue` |
| 11 | 统一搜索行为（Home 改即时过滤，与 Printed 一致） | `Home.vue` |
| 12 | 挂上已写好的 `SettingsPanel` 与 `PageNav`，精简阅读器顶栏 | `reader/` |
| 13 | 列表加骨架屏 | `GalleryList.vue` |
| 14 | 图表/表格的 tooltip 信息在触屏上可达 | `DataAnalys.vue` |

### P2 — 体系化重构，3–5 天

| # | 问题 |
|---|------|
| 15 | 设计 token 收敛为单一来源，断点统一为 4 档 |
| 16 | 详情页合并桌面/移动双 DOM 为单一响应式布局 |
| 17 | 首页引入「当前筛选条件 chip」区（借鉴 Daily 的做法），分类支持多选 + 显示计数 |
| 18 | 语法帮助改为可发现的入口 + 示例查询 chip |
| 19 | `galleries.json` 拆分/分片，缓解 9.4MB 首屏 |
| 20 | 建立动效 token（时长/缓动），补齐路由过渡与状态转换动画 |
| 21 | 移动端翻译工作台改为「图片全屏 + 底部 sheet」 |
| 22 | 全站文案语言规则统一（建议全中文，保留专有名词英文） |
| 23 | 清理 1934 行死代码 |

---

## 11. 值得保留的优点（不要在重构中丢掉）

1. **`GalleryList` 的统一抽象** —— 三个页面共用一套渲染，这是正确的架构。
2. **Daily 的筛选条件可视化** —— 全站信息设计的高点，应反向移植到首页。
3. **构建时预计算 `stats.json`** —— 客户端零计算，首屏即渲染。
4. **浅色主题的暖米色选择** —— 有意识的护眼决策。
5. **阅读器的功能完备度** —— 键盘 / 触摸 / RTL / 双页 / ±3 spread 预载 / sprite 缩略图 / 设置持久化 / nl 参数重试，这一套逻辑本身写得相当扎实，问题主要出在「移动端外壳」而非核心。
6. **缩略图按需加载**（Browse Pages）—— 省流量、省 API 配额的正确决策。
7. **防主题闪烁的内联脚本** —— 细节到位。
