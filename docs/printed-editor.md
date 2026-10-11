# 实体书单编辑

在 Printed 页面点击“编辑书单”，或访问 `/#/printed/edit`。输入与 OCR / 翻译工作台相同的密码，编辑全部字段、新增或删除书目，并保存全部修改。

编辑器读取 GitHub `master` 上最新的 `web-static/public/data/future_digi.csv`，而不是当前网站部署中的旧副本。保存会向该文件提交一次修改；现有 `Deploy to GitHub Pages` 工作流随后构建发布。成功保存表示仓库提交已完成，网站显示更新需要等待部署完成。

首页仍然读取原有 `galleries.json`。编辑器使用同一份数据，支持按画廊 ID、E-Hentai / ExHentai 画廊链接、中文或日文书名、上传者及首页支持的标签语法查找候选。选中候选只更新 `sid`，不会覆盖实体书自己的名称、价格或备注。编辑器按独立行管理书目，允许现有书目编号重复。`cover` 使用已有本地封面文件名，不提供文件上传。

## Vercel 配置

保留现有 `TRANS_PASSWORD`，另外在承载 `api/` 的 Vercel 项目中配置 **`PRINTED_GITHUB_TOKEN`**：

1. 优先在仓库所有者账号下创建 fine-grained personal access token。
2. Resource owner 选择仓库所属账号或组织，仅授权 `ywryn/NoHentai`。
3. Repository permissions 设置 **Contents: Read and write**。Metadata 的默认读取权限即可；不需要 Actions 或 Workflows 写权限。
4. 如组织要求审批，先完成审批。确认 `master` 的分支规则允许该身份提交修改。
5. 将 token 安全填写到 Vercel 的 Environment Variables 中，名称为 `PRINTED_GITHUB_TOKEN`，应用于 Production；如需预览环境联调，单独配置所需环境。
6. 重新部署 Vercel 后端，使新接口和变量生效。GitHub Pages 也需要部署含编辑页面的前端代码。

如果使用的是个人仓库的协作者账号，GitHub fine-grained token 可能无法选择该仓库作为资源，不能只凭协作者 Write 权限假定 token 可用。此时可由仓库所有者生成上述限定仓库的 token，或使用 GitHub App；如采用 classic token，公开仓库需要 `public_repo`，私有仓库需要 `repo`，并确认账号确实具有写权限。

不要将 token 放入 `VITE_*`、源码、浏览器存储或聊天。平台为 Codex 提供的 GitHub 认证不会自动成为 Vercel 函数的写入凭据。token 到期后需要在 Vercel 更新并重新部署。

如 Vercel 项目的 Ignored Build Step 或 Git 集成只跟踪部分目录，请确认新增的 `api/printed-books.js` 及其引用的 `web-static/src/utils/printedBooks.js` 会部署到后端项目。保留现有部署目录设置；本功能不迁移前后端托管平台。

## 冲突与备份

加载时记录 GitHub 文件 SHA，保存时要求该版本仍然有效。其他人修改了同一个 CSV 时，保存返回冲突，保留本地草稿；先导出 CSV，再重新加载最新书单并合并修改。每日收藏、翻译及搜索同步不写入此 CSV，因此无需调整现有定时任务。

密码只保留在编辑页面内存中，每次加载或保存 API 都会在服务端重新验证。重新加载页面或退出编辑后需要再次输入密码。未保存离开、删除条目或清空书单均有确认提示。公开 Printed 页面继续读取部署后的 CSV，不依赖 GitHub token 或新 API 可用性。

## 验证

从仓库根目录执行：

```sh
node --test tests/printed-books.test.mjs
cd web-static
npm --ignore-scripts run build
```

测试使用模拟 GitHub 响应，不会改动真实仓库或调用付费服务。线上验证需要配置 token 后实际保存一次测试书目，核对 GitHub 提交、Pages 部署及刷新后的书单，再删除测试书目。
