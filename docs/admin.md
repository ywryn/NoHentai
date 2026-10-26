# 无数据库 Admin

入口为 `https://nohentai.com/#/admin`，登录后进入概览。前端仍由 GitHub Pages 托管，管理 API 仍部署到原 Vercel 项目，不需要新增数据库或托管平台。

## 功能与数据归属

| 功能 | 权威文件 / 平台 | 生效方式 |
| --- | --- | --- |
| 画廊来源数据 | `web-static/public/data/galleries.json` | 仅抓取脚本写入 |
| 画廊人工覆盖 | `web-static/public/data/gallery-overrides.json` | Pages 构建时合并到公开 JSON |
| printed 书单 | `web-static/public/data/future_digi.csv` | Pages 发布后生效 |
| daily 搜索规则 | `config/daily.json` | 后续抓取时读取，完成发布后更新结果 |
| 翻译模型 / JSON 模式 | `config/translate.json` | Vercel 后端重新部署后生效 |
| 默认 OCR | 同上 | Pages 发布后生效；开发模式也支持 |
| 抓取与发布记录 | GitHub Actions | Admin 按需读取，不另存日志 |
| 密钥 / Cookie | GitHub Actions Secrets、Vercel Production 环境变量 | GitHub 后续任务使用新值；Vercel 需要重新部署 |

修改均通过固定白名单资源写入 `ywryn/NoHentai` 的 `master`，不接受客户端提供任意仓库、分支、文件路径或工作流。文件使用 SHA 防止旧页面覆盖新版本；冲突时保留浏览器草稿，可先导出再重新加载。

Admin 登录后使用服务端签名的会话凭证，不把管理密码写入浏览器存储。勾选“记住登录 30 天”时，会话凭证存入 localStorage；未勾选时存入当前标签页的 sessionStorage，均可在刷新后恢复。过期需重新登录，退出管理会清除本机记录，修改 ADMIN_PASSWORD 会使旧会话失效。后台权限与翻译权限分离。旧 `/#/printed/edit` 重定向到 Admin；旧 `/api/printed-books` 返回 410，不再允许通过 `TRANS_PASSWORD` 写入仓库。

## 首次部署

在原 Vercel 后端项目设置以下服务端环境变量，随后部署本次代码：

- `ADMIN_PASSWORD`：独立的高强度管理密码，不要复用公开分享的翻译密码。
- `ADMIN_GITHUB_TOKEN`：仅授权该仓库的 fine-grained token。原 `PRINTED_GITHUB_TOKEN` 可作为兼容回退，但只有原 Contents 权限时不能管理 Actions 和 Secrets。
  - Contents: Read and write，用于加载、保存、读取修改历史。
  - Actions: Read and write，用于查看运行、手动触发、重跑。
  - Secrets: Read and write，用于查询配置状态和替换仓库 Secrets。
  - Metadata 默认读取权限。
- 可选 `ADMIN_VERCEL_TOKEN`：具有目标项目环境变量和部署管理权限的 Vercel token。
- 可选 `ADMIN_VERCEL_PROJECT_ID`：原后端项目 ID。
- 可选 `ADMIN_VERCEL_TEAM_ID`：项目属于 Team 时填写 Team ID。

Vercel 平台管理未配置不影响内容编辑、daily 配置和 GitHub 任务管理；系统页会显示不可用。Contents 权限不足、分支保护不允许直接提交时，保存会失败，不会显示已提交。

不要把这些值放入 `VITE_*`、源码或普通 JSON。Admin 不提供修改自身管理密码和平台管理 token 的入口，避免切断当前管理通道；在平台控制台轮换。

前端执行完整的 `npm run build`，会依次运行统计生成、Vite 构建和 `postbuild` 发布数据合并。不要用裸 `vite build` 替代完整构建。GitHub Pages 现有工作流已经调用完整命令。

Vercel 保持仓库根目录为 Root Directory，`vercel.json` 已包含 `config/**`，确保后端配置随部署打包。若配置了 Ignored Build Step，请将 `api/**`、`shared/**`、`config/**` 和根依赖变化都纳入；`config/translate.json` 修改必须触发后端部署。如果 Vercel Git 集成未自动构建此类提交，需要在后台凭证管理页点击“重新部署后端”或到平台控制台部署。

首次上线建议先部署具备 `ADMIN_PASSWORD` 的新后端，再发布新前端。核对 Admin 登录、加载、一次测试提交、Actions 发布和发布标记后，再开始正式编辑。此仓库改造的离线测试不会设置任何真实凭证或自动修改线上数据。

## 画廊合并规则

覆盖文件以画廊 ID 为键，只允许 `title`、`title_jpn`、`tags`、`category`、`uploader`、`hidden`。ID、来源 token、时间和其他原始信息不由 Admin 改写。

```json
{
  "123": {
    "title": "人工标题",
    "tags": [],
    "hidden": true
  }
}
```

字段不存在时沿用最新来源值；空数组表示人工清空标签；移除覆盖字段即可恢复来源值。来源文件被全量更新时，人工覆盖文件保持独立。

构建不会修改仓库来源文件。生成的 `dist/data/galleries.json`、每日结果和统计均使用覆盖后的数据；`hidden` 从画廊和每日公开列表移除，printed 自身条目保留。隐藏用于展示控制，不是私密存储：仓库和现有历史备份仍可能包含来源数据。

printed 新增关联必须存在于当前收藏元数据中；已有的站外画廊关联保留并返回提示。当前画廊源数据缩减保护保持原有规则，见 `data-sync.md`；这次不擅自改为永远保留已取消收藏的条目。失去来源的旧覆盖会保留，来源恢复后仍可应用。

## daily 与翻译

daily 配置保存时以及 Python 抓取前均验证格式。任一分组抓取失败，脚本返回非零并保留上一份每日结果，不发布空列表冒充成功。预览入口是来源站点的搜索链接；回溯日期由脚本分页筛选执行，预览不是执行一次抓取。

翻译配置的 `model: null` 和 `jsonMode: null` 分别沿用现有 `LLM_MODEL`、`LLM_JSON_MODE`，避免迁移时改变当前模型。设置明确值后，仓库配置优先。模型和 JSON 模式随 Vercel 部署生效，浏览器不能通过请求参数任意改模型。默认 OCR 随 Pages 发布生效，保留工作台手动切换能力。

## 任务、发布与测活

保存返回的是 GitHub 提交完成，不代表发布成功。任务页列出工作流状态、结论、提交 SHA、更新时间和原始步骤/日志链接。Pages 构建产生 `data/release.json`，记录实际构建的提交；任务页从线上读取该标记，便于与目标提交核对。多个提交可能合并在一次后续部署中，必要时通过 GitHub 提交记录判断包含关系。

工作流不再取消正在执行的发布；同步提交前 rebase，以保留期间 Admin 对独立文件的修改。真实冲突会使任务失败，不强制覆盖。GitHub concurrency 的排队仍受平台限制，任务是否执行以 Actions 记录为准。

即时测活只访问固定的首页、画廊 JSON 和鉴权 API，不接受任意 URL，不调用付费 OCR/翻译。测活说明可达性，不证明第三方密钥和 Cookie 有效；需要实际业务调用确认。没有新增长期监控存储或自动告警。

## 密钥替换

GitHub Secrets 通过仓库公钥加密后提交，无法读回旧明文。Vercel 状态接口仅向浏览器返回名称和是否配置，不返回平台接口中的 value。替换结果仅说明平台接受了新配置，不能证明新密钥有效。

只允许列出的 Cookie、翻译服务等变量。Vercel 只写 Production。已有变量如果与 Preview 共用、存在多个版本或自定义环境绑定，后台拒绝替换，请先在控制台拆分独立 Production 变量。跨平台更新分别操作、分别展示结果，不假装提供原子同步。

Admin 不记录密钥值、调用明细或跨平台凭证版本。凭证变更审计使用平台提供的记录；内容变更使用 Git 历史。内容回滚可在仓库中创建还原提交后重新发布，历史页提供提交入口，当前不提供一键回滚按钮。

## 验证

```sh
npm ci
npm test
python -m pip install -r app/requirements.txt
python -m unittest discover -s tests -p 'test_*.py' -v
cd web-static
npm ci
npm run build
```

接口测试模拟 GitHub / Vercel，不写真实仓库，不调用付费服务。生产环境权限、分支限制和平台部署仍需配置凭证后完成一次线上验收。

## 管理界面与 Vercel 连接排查

后台分为概览、画廊、实体书单、每日筛选、翻译配置、任务与发布、服务测活、凭证管理。桌面使用侧栏导航；手机通过页面标题旁的菜单打开抽屉，列表与编辑详情分屏切换。

画廊字段直接编辑即进入本页草稿，切换记录会保留有效修改，不再需要“应用到草稿”。所有内容编辑器使用标题区保存操作；Ctrl/Cmd+S 可保存，离开前会提示未保存修改。保存表示仓库已提交，发布状态仍需在任务页查看。每日规则可调整顺序。实体书单将书目信息与画廊关联分为两个区域。

服务测活不请求平台管理状态，不要求 ADMIN_VERCEL_TOKEN。旧 `/#/admin/system` 跳转到服务测活。平台连接与凭证替换在 `/#/admin/credentials`。

Vercel 未连接不代表服务故障。仅设置 ADMIN_PASSWORD 和 ADMIN_GITHUB_TOKEN 不会获得 Vercel 管理授权。凭证页会列出缺失的 ADMIN_VERCEL_TOKEN / ADMIN_VERCEL_PROJECT_ID；Team 项目可另配 ADMIN_VERCEL_TEAM_ID。变量加入 Production 后需重新部署后端。API 区分未配置、Token 无效或过期（401）、权限不足（403）、项目不存在（404）、请求限流（429）、连接失败和平台异常，错误响应不转发上游原文或密钥。

顶部面包屑栏已移除，标题区采用紧凑布局。后台页面使用细滚动条，侧栏和导航抽屉隐藏轨道但保持可滚动，离开后台后恢复网站原有滚动条样式。

画廊、实体书单与每日筛选采用固定视口的双栏工作区，heading 保持可见，卡片填满剩余高度。列表与编辑卡片各自滚动，页面外层不滚动；手机仍切换列表/详情，当前卡片内部滚动。其他页面继续正常页面滚动。
