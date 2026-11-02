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

打开 `http://localhost:3000`。管理入口为 `/#/admin`。Vite 将 `/api` 和 `/data` 代理到 Python。首次导入包含仓库当前的收藏、每日结果、标签翻译、书单及配置；不需要立即抓取，也不会覆盖仓库源文件。再次导入会拒绝执行。

服务器部署、切换及恢复步骤见 [Vultr 部署](docs/vultr-deployment.md)。后台行为见 [Admin](docs/admin.md)，同步机制见 [数据同步](docs/data-sync.md)。

## 验证

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
npm test
cd web-static
npm ci
npm run build
```

`npm test` 依赖先安装 `web-static` 的依赖。Python 测试使用临时 SQLite 和模拟上游，不调用付费服务。前端完整构建会移除 `dist/data`，运行时数据统一由 Python 提供。

可选浏览器联调（需要本机 Nginx 和 Chromium，使用临时数据库，不访问第三方服务）：

```sh
.venv/bin/pip install -r tests/requirements-browser.txt
.venv/bin/python -m playwright install --with-deps chromium
.venv/bin/python tests/browser_smoke.py
```
