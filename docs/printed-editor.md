# 实体书单编辑

访问 `/#/admin/printed`，使用独立的管理密码登录。旧 `/#/printed/edit` 自动跳转到新入口。可以编辑全部字段、新增或删除书目，并保存全部修改。

编辑器读取 GitHub `master` 上最新的 `web-static/public/data/future_digi.csv`，而不是当前网站部署中的旧副本。保存会向该文件提交一次修改；现有 `Deploy to GitHub Pages` 工作流随后构建发布。成功保存表示仓库提交已完成，网站显示更新需要等待部署完成。

首页仍然读取原有 `galleries.json`。编辑器使用同一份数据，支持按画廊 ID、E-Hentai / ExHentai 画廊链接、中文或日文书名、上传者及首页支持的标签语法查找候选。选中候选只更新 `sid`，不会覆盖实体书自己的名称、价格或备注。编辑器按独立行管理书目，允许现有书目编号重复。`cover` 使用已有本地封面文件名，不提供文件上传。

## Vercel 配置

书单编辑已迁移到统一 Admin。配置独立的 `ADMIN_PASSWORD` 和仓库限定的 `ADMIN_GITHUB_TOKEN`，详细权限、部署顺序与可选平台能力见 [Admin 部署说明](admin.md)。原 `PRINTED_GITHUB_TOKEN` 仅作为兼容回退，`TRANS_PASSWORD` 不再授权写入。旧 `/api/printed-books` 接口返回 410。

## 冲突与备份

加载时记录 GitHub 文件 SHA，保存时要求该版本仍然有效。其他人修改了同一个 CSV 时，保存返回冲突，保留本地草稿；先导出 CSV，再重新加载最新书单并合并修改。每日收藏、翻译及搜索同步不写入此 CSV，因此无需调整现有定时任务。

密码只保留在编辑页面内存中，每次加载或保存 API 都会在服务端重新验证。重新加载页面或退出编辑后需要再次输入密码。未保存离开、删除条目或清空书单均有确认提示。公开 Printed 页面继续读取部署后的 CSV，不依赖 GitHub token 或新 API 可用性。

## 验证

从仓库根目录执行：

```sh
node --test tests/printed-books.test.mjs
cd web-static
npm run build
```

测试使用模拟 GitHub 响应，不会改动真实仓库或调用付费服务。线上验证需要配置 token 后实际保存一次测试书目，核对 GitHub 提交、Pages 部署及刷新后的书单，再删除测试书目。
