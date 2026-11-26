# NoHentai 全面代码审查报告

> 本文记录 cb85b4f 审查基线；后续修复及验证状态见 [修复记录](2026-11-04-fixes.md)。

- 审查日期：2026-11-04（UTC）
- 基线：`feat/vultr-python-sqlite`，`cb85b4fbcb1f30a1cf4db68430e45adffaf84ca1`
- 范围：Vue 路由与页面、阅读器、翻译工作台、管理表单；FastAPI 管理及公开接口；SQLite 迁移、记录版本、缓存、任务、调度、备份；原抓取模块；Nginx / systemd / PWA / 发布脚本；现有测试与遗留文件。
- 方法：代码与引用关系检查、现有测试、临时数据库复现、模拟上游的 Chromium 交互验证，以及少量线上只读检查。
- 边界：未修改业务代码、未删除文件、未触发真实同步、未调用真实 OCR / 翻译服务、未修改生产配置或数据。浏览器复现使用测试图片与虚构凭证。用户明确要求的“后台明文展示配置”作为当前产品要求，不列为缺陷。

## 结论

迁移后的核心架构已经形成：业务数据来自 SQLite，后台按条编辑，worker 持久化执行任务，旧静态数据不会随完整构建发布。但迁移尚未完全收口，**仍有可调用的旧写入接口绕过新模型，以及多处异步状态和缓存逻辑问题**。

本次列出 **13 项问题：P1 3 项、P2 9 项、P3 1 项**。其中 11 项有针对性复现；类型检查问题直接执行命令验证；部署资源问题验证了旧资源 404，其对旧页面的影响基于代码路径分析。没有把“未发现问题”视为“已证明没有问题”。

最先处理：

1. 翻译工作台 OCR 串页并污染本地缓存。
2. 旧批量保存接口破坏书目 / 每日规则 UUID 与历史对应关系。
3. 标签词典缺少结构校验，可能成功发布不可用数据并影响多个公开接口。

## 一、按严重程度排列的问题

### F01 · P1 · OCR 完成后会写入另一页，并污染该页缓存【浏览器已复现】

**位置：** [GalleryTranslate.vue:1658](../../web-static/src/components/GalleryTranslate.vue#L1658)，另见 `savePageCache()`（1973 行）和 `performOcrAndTranslate()`（1468 行）。

**触发：** 在第 1 页点击翻译，OCR 请求尚未返回时通过缩略图进入第 2 页，然后让第 1 页 OCR 返回。

**原因：** `performOcr()` 没有捕获并核对页码 / 请求代次，直接赋值 `this.ocrResults`，再按此时的 `this.currentPage` 保存。图片请求有 `imageRequestId` 防护，OCR 流程没有同等防护；翻页入口也没有禁止 OCR 期间切页。后续自动串联的翻译还可能采用第 2 页上下文。

**实测：** 浏览器停在 `page=2`，`localStorage['trans_cache_1_p2']` 出现第 1 页的 `OLD_PAGE_OCR`。不是仅闪现错误内容，而是写入了错误缓存。

**建议：** 为整条 OCR → 翻译流程捕获 gallery / page / request generation；结果仅可写回对应页面，过期请求不得更新当前 UI。缓存写入必须显式接收发起页码。切页、重做 OCR、卸载时取消或废弃旧请求。补“处理中翻页、离开再返回、同页重新请求”的延迟响应测试。

### F02 · P1 · 旧批量保存接口按位置复用 UUID，破坏新记录模型【临时数据库已复现】

**位置：** [backend/admin.py:66](../../backend/admin.py#L66)、[backend/db.py:99](../../backend/db.py#L99)。

**触发：** 已认证客户端调用旧 `load/save` 管理 action，保存重排、插入或删除后的 `printed` / `daily` 数组。新界面虽不使用此入口，接口仍接受请求。

**原因：** `put_resource()` 先按 `position → id` 记住 UUID，再清空整表，并把第 i 项赋给旧第 i 项的 UUID。UUID 跟随位置，而不是逻辑记录；该路径也不生成对应的 `record_history`。

**实测：** 两本书反转保存后，第一个 UUID 不变，但已对应第二本书；原 UUID 的逐条历史没有相应变更。旧历史恢复因此可能恢复到错误的书目。每日规则 ID 还用于单组任务与结果关联，受到同类影响。

**建议：** 优先停止运行期旧整资源写入，保留必要只读兼容；初始化导入另走独立函数。如必须支持批量导入，应携带稳定 UUID，调用同一套校验、冲突检查和逐条审计。不能按显示编号合并，因为书目编号允许重复。

### F03 · P1 · 词典同步只校验顶层字段，可能“成功”发布后导致公开接口 502【临时数据库已复现】

**位置：** [app/sync_translations.py:65](../../app/sync_translations.py#L65)、[backend/jobs.py:280](../../backend/jobs.py#L280)、[backend/catalog.py:127](../../backend/catalog.py#L127)。

**触发：** 上游返回合法 JSON，但命名空间 / `data` 条目结构错误。

**原因：** `validate_and_parse()` 仅检查顶层存在 `data`。例如 `{"data":[{"namespace":"female","data":["bad"]}]}` 能通过校验和任务计数，并发布为成功；`translation_index()` 随后对列表调用 `.items()`。

**实测：** 使用该词典执行临时任务，任务结论为 `success`，随后 `/api/galleries` 返回 502。调用同一词典索引的详情、书单、每日、统计等路径也存在受影响可能。

**建议：** 发布前验证完整 schema：顶层对象、命名空间数组、namespace 字符串、标签字典、条目字段类型；增加空词典 / 规模骤降保护。在事务发布前实际构造索引，确保失败时保留上一份可用快照。

### F04 · P2 · 滚动阅读模式的起始页、目录跳转和键盘翻页没有同步到滚动位置【浏览器已复现】

**位置：** [ScrollView.vue:73](../../web-static/src/components/reader/ScrollView.vue#L73)、[useReader.ts:164](../../web-static/src/composables/useReader.ts#L164)、`ThumbGrid.vue:onSelect()`。

**触发：** 保存为滚动模式后打开 `read?...&page=4`，或打开页目录选择第 4 页。

**实测：** 两种操作之后 `.scroll-view.scrollTop` 均为 0，仍显示第一页。IntersectionObserver 还会按屏幕中实际可见页覆盖页码。

**原因：** `goTo()` 只修改 `currentPage` 并预取；只有 `ScrollView.onScrollClick()` 自己调用 `scrollIntoView()`，其他跳页入口没有。挂载也未定位初始页。

**建议：** 将“用户请求跳页”和“滚动观察更新当前页”分开，统一处理所有跳页入口；挂载、模式切换后定位目标页，图片尺寸变化时保持定位，避免 observer 反馈循环。

### F05 · P2 · 图片重试可能命中同一个失效 URL 缓存【临时数据库已复现】

**位置：** [backend/media.py:71](../../backend/media.py#L71)、`useReader.ts:retryImage()`、`GalleryTranslate.vue:retryCurrentImage()`。

**触发：** 图片源地址已失效，上游没有 `nl` 参数；或刷新过一次来源后再次重试相同的 `nl` URL。

**原因：** 前端只清除自己的 URL 缓存。后端按完整 `pageUrl` 缓存 900 秒；没有强制刷新语义，重新请求相同 pageUrl 不访问来源页面。

**实测：** 对没有 `nl` 的同一 pageUrl 连续取地址，第二次没有调用上游 fetch，而是返回同一失效地址。

**建议：** 增加有频率限制的重新解析参数 / 重试接口，明确废弃对应服务器缓存。缓存命中与“重新获取来源”应有不同语义，不能仅靠改 query 碰运气。

### F06 · P2 · 阅读器页面列表缺少完整性校验，会缓存缺页结果【临时数据库已复现】

**位置：** [backend/media.py:57](../../backend/media.py#L57)。

**触发：** 来源页面声明 5 页，但 HTML 解析仅得到 2 个页面链接，例如来源结构变化或页面内容不完整。

**实测：** `gallery_images()` 成功返回 `total=5, images=[两项]` 并缓存 1 小时。未检查页码连续、重复、缺失或各分页返回的一致性。

**影响：** 阅读器以 total 导航，却找不到对应 pageUrl；翻译台按 images 长度计算总页数，可能直接把缺页当成结束。

**建议：** 发布页面列表前验证页码唯一、覆盖 `1..total`，分页之间长度和编号一致；验证失败返回可重试错误，不缓存不完整结果。

### F07 · P2 · 详情页切换后请求失败，继续展示上一部作品且隐藏错误【浏览器已复现】

**位置：** [GalleryDetail.vue:1](../../web-static/src/components/GalleryDetail.vue#L1)、[GalleryDetail.vue:253](../../web-static/src/components/GalleryDetail.vue#L253)。

**触发：** 同一 SPA 会话从 `/gallery/1` 切到 `/gallery/2`，第 2 个请求失败。快速切换时也可能出现旧请求晚返回。

**原因：** 路由变化 / 新请求没有清空旧 `galleryData`，模板先判断 `v-if="galleryData"`，错误分支被挡住；请求没有取消或代次判断。

**实测：** 地址已为 `/gallery/2`，接口返回 404，页面仍显示 `FIRST_GALLERY`，错误区域不存在。此时链接可能组合新的 itemId 与旧 token。

**建议：** 捕获 gid/source/request generation，忽略过时响应；新目标明确展示加载 / 失败状态。若保留旧内容，必须明确标记并禁止旧数据生成新目标操作链接。

### F08 · P2 · 旧 replace-secret 接口显示成功但新配置可能不生效【临时数据库已复现】

**位置：** [backend/admin.py:116](../../backend/admin.py#L116)、[backend/security.py:42](../../backend/security.py#L42)、[backend/security.py:51](../../backend/security.py#L51)。

**触发：** 先在新服务配置页保存 `LLM_API_BASE`，再通过旧 `replace-secret` action 更改同名项。

**原因：** 新表单将地址存入 `service_settings`；旧接口只写 `credentials`，读取时却优先 `service_settings`。两个存储来源同时存在，旧写入被遮蔽。

**实测：** 旧接口成功写入第二个地址，`security.credential('LLM_API_BASE')` 仍返回第一个地址。

**建议：** 退役旧写接口，或委托给统一 `services.save()`，让每个配置名称只存在一种权威存储与统一审计、版本处理。

### F09 · P2 · 工作台密码保存与认证长度限制不一致【临时数据库已复现】

**位置：** [backend/services.py:89](../../backend/services.py#L89)、[backend/security.py:167](../../backend/security.py#L167)。

**实测：** 1025 字符的 `TRANS_PASSWORD` 可成功保存，但正确输入同一值也始终返回 401，因为认证最多允许 1024 字符。

**建议：** 为工作台密码定义单独且共用的长度规则，前后端同步。其他 API Key 可以保持不同长度上限；不要用一套“secret”长度覆盖所有字段。

### F10 · P2 · 类型检查入口已失效，生产构建通过不能证明类型正确【命令已验证】

**位置：** [web-static/tsconfig.app.json:3](../../web-static/tsconfig.app.json#L3)、`web-static/package-lock.json:6146`、`web-static/package.json:scripts`。

**执行：** `./web-static/node_modules/.bin/vue-tsc --noEmit -p web-static/tsconfig.app.json`

**结果：**

```text
TS5069: Option 'tsBuildInfoFile' cannot be specified without specifying option 'incremental' or option 'composite'.
TS5023: Unknown compiler option 'noUncheckedSideEffectImports'.
```

锁定的 TypeScript 为 5.4.5，与配置不匹配。现有 `build` 只执行 Vite；没有可运行的 typecheck 脚本或当前 CI 工作流来承担这项检查。

**建议：** 先统一锁文件、编译器和配置，修好独立 typecheck，再纳入持续检查。还应明确大量 JS / JS Vue 文件的静态检查策略；仅修好 TS 配置不等于这些文件也已覆盖。

### F11 · P2 · 发布切换后旧页面可能无法加载尚未访问的路由资源【旧资源 404 已验证，用户场景为代码推断】

**位置：** [deploy/publish-frontend.sh:11](../../deploy/publish-frontend.sh#L11)、[deploy/nginx.conf:66](../../deploy/nginx.conf#L66)、`web-static/src/router/index.ts`。

**条件：** 用户已打开旧版本，尚未访问某个懒加载路由；发布后该旧 chunk 没有被浏览器 / Service Worker 缓存。

**证据：** 发布脚本保留旧 release，但 Nginx 的资源根目录仅指向 current，`/assets/` 缺失直接 404。线上旧 chunk `/assets/AdminPanel-Dgp2D3Rf.js` 已返回 404。路由使用动态 import，且没有 chunk 加载失败恢复逻辑。

**影响：** 保留旧 release 只支持整体回滚，不代表旧页面仍能下载旧 chunk；可能需要手动刷新才能继续导航。已有 PWA 预缓存可缓解部分情况，不能覆盖没有受 SW 控制或缓存未完成的页面。

**建议：** 发布前把不可变 hash 资源合并到共享资源目录，延迟清理；或使用带 release 标识的资源 URL。另增加有次数限制的 chunk 失效重载处理，并对后台未保存草稿做恢复保障。用“旧页面打开 → 发布 → 首次进入另一页”的场景验收。

### F12 · P2 · 多词 / 带引号的搜索条件无法通过 chip 删除【浏览器已复现】

**位置：** [Home.vue:386](../../web-static/src/components/Home.vue#L386)、`gallerySearch.js:tokenizeQuery()`。

**实测：** 查询 `female:"sole female$"` 时点击条件 chip，查询和 chip 均不变化。

**原因：** tokenizer 为解析去掉引号，`term.raw` 不是原始源文本片段；删除函数却按空格切分后逐片对比。单个 token 内的空格 / 引号与删除逻辑不兼容。

**建议：** tokenizer 保留源文本起止偏移和原始片段，按偏移移除；或以结构化条件重建查询，避免再次使用不同分词规则。

### F13 · P3 · “本月 Vision 用量”混入仍未过期的上月计数【临时数据库已复现】

**位置：** [backend/operations.py:42](../../backend/operations.py#L42)、`WorkspaceOverview.vue` 的用量求和；计数写入见 `backend/translation.py:201`。

**原因：** Vision counter 的 TTL 是 35 天；概览返回所有未过期的 `vision:%`，前端全部相加，标签却写“本月”。

**实测：** 同时保留 `vision:2026-10` 和 `vision:2026-11` 各 1 次，页面数据合计为 2。实际当月配额判断仍按当月 key，因此主要是展示错误，不是配额失控。

**建议：** 后端按当前 UTC 月精确读取，并返回 month、used、limit，前端不要对跨月计数无条件求和。

## 二、废弃代码、隐藏入口与保留项

“当前无引用”不自动等于“产品应永久删除”。以下分组避免误删仍承担迁移、导入或测试作用的文件。

### A. 当前前端无引用的组件

通过 `web-static/src` 下路由、import 和组件名引用检查，发现以下文件没有其他源码引用：

| 文件 | 当前情况 | 建议 |
| --- | --- | --- |
| `components/reader/SettingsPanel.vue` | 未挂载；实际设置在 ReaderTopBar。仍含宽度、页间距和 S 快捷键等旧设计 | 删除旧实现或明确恢复所需功能，避免误认为这些设置现在可用 |
| `components/reader/PageNav.vue` | 未挂载；页码导航实现孤立 | 决定是否需要底部页码；不用则删除 |
| `components/admin/AdminPanePlaceholder.vue` | 骨架组件无使用方 | 删除，或统一接入各页面，不保留孤立设计 |
| `components/TagExplorer.vue` | 组件和 `assets/TagExplorer.css` 尚在，没有路由 / 导航入口 | 这是完整但当前关闭的标签浏览功能；决定恢复入口还是整体退役 |

`TagExplorer` 对应的 `/api/tags` 和 catalog 标签分页逻辑仍可直接调用。若退役标签浏览，不要误删 `/api/tags/suggestions`：首页和后台仍依赖补全。

### B. 当前生产 UI 不使用的工具与重复实现

| 位置 | 证据 / 影响 | 建议 |
| --- | --- | --- |
| `useGalleryData.js:loadGalleries/loadTranslations` 及模块级 Promise 缓存 | 当前 src 无调用者；页面已迁移专用 API | 移除旧全量加载器；`invalidateGalleryData()` 目前主要只重置这些无使用方的缓存，名称容易让人误以为它能失效所有页面数据 |
| `adminLogin.js:readAdminLogin/saveAdminLogin` | src 无调用者；当前登录使用 Cookie | 删除读写旧 token 的实现，保留 `clearAdminLogin()` 作为旧浏览器迁移清理，直至确定迁移期结束 |
| `adminDrafts.js:serviceOperations` | 新配置页已经不调用；仅旧测试仍引用 | 与已移除操作下拉框一同清理对应测试；是否保留后端 operations 应明确兼容期限 |
| `shared/adminData.js` 的多套校验函数 | 生产前端主要使用 CATEGORIES，若干校验只被 Node 测试使用；后端实际使用 Python 校验 | 明确 JS 校验是产品逻辑还是测试参考，避免只测试不在生产执行的版本而产生错误信心 |
| `backend/stats.py:generate()` | 生产走 SQL aggregate；Python generate 被测试作为对照 | 不是可以直接删除的死代码。建议迁到测试参考模块，避免与实际入口混淆 |
| `DailySearch.vue` 的 daily-rule 样式 | 相同规则同时出现在带 `src` 的 style 块内与 scoped 块 | 整理成单一明确来源；不作为本次功能缺陷计数 |

### C. 旧接口和兼容路由仍然存在

- `admin.handle()` 的 `load/save/history`：F02 说明旧写入不能按普通死代码处理。
- `platforms/replace-secret`：当前服务页不用；F08 说明旧写入口与新存储冲突。
- 旧 body password / token 管理模式仍保留，新 UI 已使用 Cookie + CSRF；需要兼容说明和退役边界，不能仅因“页面没有入口”就假设不可调用。
- `/api/printed-books` 返回 410，是明确退役响应；保留过渡提示合理，和仍可成功写入的旧接口不同。
- `/printed/edit → /admin/printed`、`/admin/system → /admin/health` 是显式兼容重定向，建议保留。
- `/admin/translate`、`/admin/credentials` 当前仍直接渲染统一服务页，可改成重定向 `/admin/services`，减少多个看似不同的后台入口。
- `/data/*.json/csv` 仍从数据库生成，属于兼容读接口；翻译台仍读取 `translate-config.json`，不能整体删除。

### D. 抓取脚本和部署遗留

- `app/sync_script.py`、`app/exhentai_search.py`、`app/sync_translations.py` 的核心抓取 / 解析函数仍被新 worker 导入，**不能整文件删除**。
- 同一批文件中的旧 `main()`、`app/sync_daily_search.py` 仍会写 `web-static/public/data`，与当前生产 SQLite 数据源不同。建议迁到明确的 `legacy/` 或独立离线导入工具，并给出醒目的“不更新当前线上数据库”提示。
- `app/exhentai_search.py` 中单页搜索、popular 和 CLI 演示方法未进入当前 worker 主路径，清理时按调用图拆分，不连带删除共享 parser / API client。
- `web-static/public/data` 约 41MB、11 个跟踪文件，包括旧备份。`backend.cli.initialize_data()` 仍依赖其中部分文件作为初次导入快照；完整构建通过 postbuild 删除 dist/data，因此本次未发现它们作为生产第二数据源被发布。建议将种子快照移到非 public 目录，明确保留最小导入集合并清理冗余备份。
- `deploy/systemd/nohentai-sync.timer` 仍可启用一体 all 任务，与数据库调度是第二条入口；线上只读检查确认其为 disabled。建议标记 legacy，避免安装时误开，不把当前 disabled 状态当作 bug。
- `CNAME`、`web-static/public/_redirects` 是旧静态托管配置，当前 Nginx 不使用，可随旧平台退役整理。
- `docs/superpowers/` 和 `UI_UX_REVIEW.md` 是历史设计 / 审查资料，不是当前运行规范；建议移动到 archive 或标注状态，保留历史价值。
- `kuromoji-dict` 约 18MB，仍被翻译学习模式使用，**不属于废弃资源**。

## 三、验证结果与覆盖限制

| 检查 | 结果 | 说明 |
| --- | --- | --- |
| Python unittest 全量 | 81 项通过 | 临时数据库、模拟上游 |
| Node tests 全量 | 14 项通过 | 其中有些验证的是遗留 JS 校验，不等于验证生产 Python 行为 |
| 完整生产构建 | 通过 | 包括 PWA 与 postbuild；确认构建结果没有 dist/data |
| Vue / TypeScript 检查 | 失败 | F10 两项配置错误，在进入完整代码检查前阻断 |
| 定向后端复现 | 7 个问题复现 | F02、F03、F05、F06、F08、F09、F13 |
| 定向 Chromium 复现 | 4 个问题复现 | F01、F04、F07、F12；模拟图片 / OCR 响应，无付费调用 |
| 现有全栈浏览器冒烟 | 原套件未通过；修正过期断言的临时副本通过 | 首次在第 194 行书单链接断言失败；复跑通过此前位置，但在第 299 行旧模型断言失败；临时副本将“填空”改为“填回初始显示值”后完整通过，未修改仓库测试 |
| 生产只读检查 | 正常 | 源码 cb85b4f；API/worker/Nginx active；Nginx 配置检查通过；SQLite schema 3、quick_check=ok；无排队 / 运行任务；旧 sync timer disabled |

现有全栈浏览器测试存在明确的过期断言：`tests/browser_smoke.py:297–299` 假设模型原值为空，修改后再次填空就应关闭保存按钮；但新配置页按产品要求显示当前生效模型，恢复原值应填回初始显示值。需要同步更新这一测试。首次书单断言在复跑中通过，说明不能仅凭首次失败认定书单产品有 bug。测试对部分 locator 使用默认 5 秒超时，失败清理阶段还输出大量路由取消异常，应单独改善稳定性与错误输出。以上不能替代 F01 等有独立复现的产品问题，也不能用单元测试通过掩盖原全栈套件未通过。

临时副本完整通过的流程包括首页 / 详情 / 统计、管理登录、逐条编辑与恢复、封面上传、画廊关联、任务日志、单组同步、取消、调度、备份、密码轮换和移动导航。这说明现有正常流程有较好基础，但不会覆盖本次独立复现的跨页竞态、坏词典发布等场景；原仓库的过期断言仍未修复。

另一次构建进行中启动浏览器测试，被测试自己的 `dist/data` 防护断言提前终止：当时 postbuild 尚未完成。这是本次验证时序造成，不作为项目缺陷；最终结果仅采用完整构建结束后的运行。

未进行依赖 CVE 扫描、生产压力测试、真实 Cookie 抓取和真实第三方付费服务调用；本报告不声称已覆盖这些范围。未主动升级依赖或触发外部供应商请求。

## 四、建议修复顺序

1. **第一批：数据正确性。** 修复 F01；关闭或统一 F02 / F08 的旧写入入口；对 F03 增加完整 schema 与发布前验证。每项都补能证明错误结果不会发布 / 写入的回归用例。
2. **第二批：阅读和导航。** 修复 F04 / F05 / F06 / F07 / F12，统一跳页、重试及异步请求代次机制。
3. **第三批：配置与工程检查。** 修复 F09 / F10 / F13；稳定全栈浏览器测试，增加延迟返回与跨页状态覆盖。
4. **第四批：发布兼容。** 处理 F11，并补旧版本页面跨发布导航测试。
5. **第五批：遗留清理。** 先建立接口 / 调用清单，再分批移除无引用组件、工具和旧 CLI。种子快照、迁移清理和参考测试实现分别归档，不做整目录盲删。

以上为审查基线时的状态；后续代码修复与验证见 [修复记录](2026-11-04-fixes.md)。生产版本是否更新以部署记录为准。


## 附：复现与日志位置

定向复现脚本仅存于本机 `/tmp`，未加入生产或原测试代码：

- `/tmp/nohentai-review-repro.py`：7 个后端问题，均用 `BackendTests` 创建 / 清理临时数据库。
- `/tmp/nohentai-review-browser-repro.py`：滚动阅读跳页和 OCR 串页，使用本地静态服务器与模拟接口。
- `/tmp/nohentai-review-ui-repro.py`：详情错误残留、搜索 chip 删除。
- `/tmp/nohentai-review-browser-adapted.py`：原冒烟套件的临时副本，仅更正模型原值断言以及项目根目录定位，便于继续审查后续流程；不能把副本结果当成原套件已通过。

对应日志为 `/tmp/nohentai-review-{python-tests,node-tests,typecheck,build,repro,browser-repro,ui-repro,browser-final,browser-adapted}.log`。这些临时证据文件可能随环境清理消失；各问题的触发条件、根因和结果已写入本报告，后续正式修复应把相应复现转换成仓库内回归测试。
