# NoHentai

Vue 前端 + Python FastAPI 后端，使用 SQLite 保存内容、管理配置、缓存、会话和同步任务。独立服务器部署，不依赖 GitHub Actions、Vercel Serverless 或 Upstash Redis。

## 本地开发

需要 Python 3.11+、Node.js 20+。从仓库根目录运行：

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.lock.txt
cp .env.example .env
.venv/bin/python -m backend.cli generate-key
```

把生成的密钥填入 `.env` 的 `CREDENTIAL_ENCRYPTION_KEY`，设置独立的高强度 `ADMIN_PASSWORD`，然后：

```sh
.venv/bin/python -m backend.cli init
.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

另开终端启动同步 worker：

```sh
.venv/bin/python -m backend.cli worker
```

另开终端启动前端：

```sh
cd web-static
npm ci
npm run dev
```

打开 `http://localhost:3000`。管理入口为 `/#/admin`。Vite 将 `/api`、`/data` 和 `/media` 代理到 Python。首次导入包含仓库当前的收藏、每日结果、标签翻译、书单及配置；不需要立即抓取，也不会覆盖仓库源文件。再次导入会拒绝执行。

服务器部署、切换及恢复步骤见 [Vultr 部署](docs/vultr-deployment.md)。后台行为见 [Admin](docs/admin.md)，同步机制见 [数据同步](docs/data-sync.md)。

## 管理与维护

后台支持逐条编辑与历史恢复、封面上传、分组服务配置、持久化任务与调度、Cookie 登录和账户会话管理。首次从 `ADMIN_PASSWORD` 创建管理员后，密码由数据库管理。调度默认暂停，在服务凭证验证后通过后台启用；旧 `nohentai-sync.timer` 保持关闭。schema 1 / 2 自动事务升级到 schema 3，上线前必须备份并验证副本，降级需恢复对应旧库。

## 验证

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
npm test
cd web-static
npm ci
npm run build  # 包含 Vue / TypeScript 检查
```

`npm test` 依赖先安装 `web-static` 的依赖。Python 测试使用临时 SQLite 和模拟上游，不调用付费服务。前端完整构建会移除 `dist/data`，运行时数据统一由 Python 提供。首页使用 `/api/galleries` 的服务器分页和高级搜索，详情按 ID 查询；兼容的全量 JSON 接口不再参与首页加载。

可选浏览器联调（需要本机 Nginx 和 Chromium，使用临时数据库，不访问第三方服务）：

```sh
.venv/bin/pip install -r tests/requirements-browser.txt
.venv/bin/python -m playwright install --with-deps chromium
.venv/bin/python tests/browser_review.py
.venv/bin/python tests/browser_search.py
.venv/bin/python tests/browser_smoke.py
```

统计页使用 `/api/stats`，SQL 聚合结果按数据版本和 UTC 日期缓存在 SQLite，所有 API 进程共享，旧统计地址保持兼容。

代码检查工作流只运行测试、类型检查与构建，不执行数据同步或自动部署。
