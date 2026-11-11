# Vultr 独立服务器部署与迁移

架构为 Nginx 静态前端 + 同域 FastAPI + SQLite（WAL）+ 单实例同步 worker（数据库调度）+ systemd 备份 timer。GitHub 仅保存源码，生产内容和任务状态不再提交 Git。第三方收藏、词典、翻译、OCR 仍通过相应服务获取；Python 替代的是原 Serverless 业务逻辑。

## 1. 准备服务器

以下以具有 sudo 权限的 Debian 13 / Ubuntu 24.04 服务器为例，项目固定 `/opt/nohentai`，数据库固定 `/var/lib/nohentai`。需要 Python 3.11+、Node.js 20+、Git、Nginx。Node 仅构建前端时使用。

```sh
sudo apt-get update
sudo apt-get install -y git python3-venv nodejs npm nginx certbot python3-certbot-nginx
node --version
python3 --version
sudo useradd --system --home-dir /var/lib/nohentai --shell /usr/sbin/nologin nohentai
sudo install -d -o nohentai -g nohentai -m 0700 /var/lib/nohentai
sudo install -d -o root -g nohentai -m 0750 /etc/nohentai
```

服务器部署和后续开发统一使用 `master` 主分支（已有 checkout 可以切换到该分支）：

```sh
sudo git clone --branch master https://github.com/ywryn/NoHentai.git /opt/nohentai
cd /opt/nohentai
sudo python3 -m venv .venv
sudo .venv/bin/pip install -r backend/requirements.lock.txt
sudo cp .env.example /etc/nohentai/nohentai.env
sudo chown root:nohentai /etc/nohentai/nohentai.env
sudo chmod 0640 /etc/nohentai/nohentai.env
.venv/bin/python -m backend.cli generate-key
sudoedit /etc/nohentai/nohentai.env
```

在配置文件中填写：

- 独立、高强度且至少 16 字符的 `ADMIN_PASSWORD`，与翻译密码分开。
- 刚生成的 `CREDENTIAL_ENCRYPTION_KEY`，只生成一次并单独备份。
- `ALLOWED_ORIGINS=https://你的域名,https://www.你的域名`，按实际使用域名填写。
- 旧平台的 Cookie、TRANS_PASSWORD、LLM/OCR 参数。GitHub Secrets 不能读回旧值，需从原始凭证来源重新配置。未配置的服务可稍后在 admin 中补充。

不要将配置文件放进前端目录。环境文件供 systemd 读取，格式为 `NAME=value`，不要写 `export`；复杂值使用引号。生产 systemd 单元显式设置持久数据路径，无需把配置复制到源码目录。

## 2. 冻结旧任务并导入数据

正式切换前，在 GitHub Actions 设置中停用旧工作流，等待已经运行的同步 / 发布结束；暂停旧 admin 编辑。删除工作流文件只有在代码合并后才影响默认分支，本分支的删除不会立即停掉 master 上的旧任务。

保存当前线上/旧仓库的最新内容，尤其是 gallery-overrides.json、future_digi.csv、daily.json 和 translate.json。初次导入以本 checkout 文件为准；若 master 在分支创建后又更新过数据，先将最终数据复制进迁移快照，或者用 `--source /path/to/final-snapshot` 导入该快照。snapshot 目录需保留 config/ 和 web-static/public/data/ 的相对结构。

```sh
cd /opt/nohentai
sudo -u nohentai env NOHENTAI_DATA_DIR=/var/lib/nohentai \
  /opt/nohentai/.venv/bin/python -m backend.cli init
# 若从单独的最终快照导入：在上述命令尾部添加 --source /path/to/final-snapshot
```

导入在单一事务中完成，已有数据时拒绝重导。旧 JSON 备份不自动导入历史表，需要时另行归档。原始 source 和人工覆盖分别存储，避免把构建后的合并数据当原始数据导入。

## 3. 构建前端和安装服务

```sh
cd /opt/nohentai/web-static
sudo npm ci
sudo npm run build
cd /opt/nohentai
sudo sh deploy/publish-frontend.sh
sudo cp deploy/systemd/nohentai-* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nohentai-api.service nohentai-worker.service
sudo systemctl disable --now nohentai-sync.timer
sudo systemctl enable --now nohentai-backup.timer
curl --fail http://127.0.0.1:8000/api/health
sudo systemctl list-timers 'nohentai-*'
```

服务以 nohentai 用户运行，仅 `/var/lib/nohentai` 可写。API 使用两个 Uvicorn worker，队列 worker 为一个进程；SQLite 的 WAL、busy timeout、事务及 OS 文件锁控制并发。API 启动会检查管理密码、加密主密钥和导入状态，缺配置直接启动失败，避免半配置上线。

前端构建不再生成业务数据，完整 `npm run build` 会移除 `dist/data`。`publish-frontend.sh` 创建 release 目录并原子切换 `/srv/nohentai/www/current`，保留旧 release 便于回滚。不要在 `VITE_*` 中放服务端配置；默认不设置 VITE_API_BASE，统一同域。

## 4. Nginx、域名与 HTTPS

编辑 `deploy/nginx.conf` 中的 server_name 为实际域名，再安装：

```sh
sudo cp deploy/nginx.conf /etc/nginx/sites-available/nohentai
sudo ln -s /etc/nginx/sites-available/nohentai /etc/nginx/sites-enabled/nohentai
sudo nginx -t
sudo systemctl reload nginx
```

先把域名 DNS 指向服务器 IP；若使用 CDN，应先确保源站证书签发与代理配置匹配。在 Vultr 防火墙和系统防火墙允许 SSH、80、443，8000 仅绑定本机。启用 HTTPS 后再登录后台：

```sh
sudo certbot --nginx -d 你的域名 -d www.你的域名 --redirect
```

若只使用一个域名，移除另一个 `-d` 和对应 server_name / ALLOWED_ORIGINS。Nginx 中所有 `/data/` 都转 Python，未知数据名返回 404，不回退静态文件。备份、环境文件和数据库不位于 web root。

## 5. 切换验收

先在新服务器完成验证，再切 DNS 或流量。若提前验证域名，可在自己电脑 hosts 中临时指向新 IP。

- 首页数量、每日分组、统计和实体书单与最终迁移快照一致。
- 管理密码登录、刷新恢复、退出撤销；翻译密码不能管理内容。
- 编辑一条标题 / 书目，刷新公开页面立即生效，再还原测试内容。
- 两个浏览器编辑同一条目，旧版本保存得到冲突，草稿可导出。
- admin 配置凭证，确认只返回配置状态，不返回明文。
- 手动执行一次全量同步，确认任务完成、数据版本变化、人工修改仍在。
- 使用真实画廊验证阅读器图片、词典以及各已配置 OCR / 翻译服务。
- 在后台确认各项调度时间与时区、worker 心跳和备份；新安装 / 升级的调度默认暂停，验收后按需启用。

旧浏览器的 Service Worker 更新后，业务 JSON / CSV 使用 NetworkOnly。旧 Vercel admin 会话在新服务器失效，需重新登录；浏览器之前打开的页面请刷新。

验收后停用旧 Vercel 部署 / Git 集成、GitHub Pages 和所有旧 Actions，并撤销旧 ADMIN_GITHUB_TOKEN、ADMIN_VERCEL_TOKEN、Upstash 凭证。代码已移除这些依赖，但撤销远程平台配置需要在对应平台操作。保留旧数据及部署快照供短期回退，不能让新旧两个后台同时写入。

## 6. 日常维护

查看服务与任务：

```sh
sudo systemctl status nohentai-api nohentai-worker
sudo journalctl -u nohentai-api -u nohentai-worker --since today
sudo systemctl start nohentai-sync.service
sudo systemctl start nohentai-backup.service
```

同步详情在 admin 查看阶段和结果摘要。worker 的原始上游 stdout/stderr 不写入公开日志，避免包含 Cookie、源响应或服务密钥。单任务最多六小时；失败保留旧数据。任务表和审计历史持久保存，按实际数据规模安排归档。

更新代码前先备份：

```sh
sudo systemctl start nohentai-backup.service
sudo systemctl stop nohentai-api nohentai-worker
cd /opt/nohentai
sudo git pull --ff-only
sudo .venv/bin/pip install -r backend/requirements.lock.txt
cd web-static
sudo npm ci
sudo npm run build
cd ..
sudo sh deploy/publish-frontend.sh
sudo systemctl restart nohentai-api
sudo systemctl start nohentai-worker
```

worker 运行中不要替换 Python 代码。计划维护时先查看任务状态，等待当前任务结束后再停止 worker、更新代码；上面更新命令用于已无运行任务时。systemd 停止会终止整个任务进程组；若强制停止，重启后中断任务显示失败，可以重跑。数据库目录在 checkout 外，不受 pull / 前端发布影响。

首次启动从 `ADMIN_PASSWORD` 创建账户，之后在后台“账户与会话”修改密码；环境文件不再轮换数据库密码。忘记密码使用本机 `reset-admin --password-file`，见下方命令。加密主密钥不要直接替换。后台写过的业务凭证优先于环境文件；替换时建议始终使用 admin 管理同一项，避免两个配置来源混淆。

## 7. 备份、恢复与回退

每天 UTC 19:45 及每次同步开始前使用 SQLite Backup API 生成一致性备份，保留最近七份，路径为 `/var/lib/nohentai/backups`。这表示七个快照，不一定覆盖七天；频繁手动同步会更快轮换。有上传封面时同时生成同名 `.media.zip`，恢复时将其中 WebP 放回数据目录的 uploads/。应把数据库、配套媒体以及单独保存的主密钥 / 环境文件复制到服务器以外的位置。

恢复时停写并保留当前完整目录（包含 WAL/SHM），不要只复制在线 `.sqlite3` 文件：

```sh
sudo systemctl stop nohentai-sync.timer nohentai-backup.timer
sudo systemctl stop nohentai-api nohentai-worker
# 先将所选备份复制到 /root/restore.sqlite3，并验证 PRAGMA integrity_check = ok。
# 保留原目录，使用新的空目录恢复，避免残留旧 WAL/SHM。
sudo mv /var/lib/nohentai /var/lib/nohentai.before-restore
sudo install -d -o nohentai -g nohentai -m 0700 /var/lib/nohentai
sudo install -o nohentai -g nohentai -m 0600 /root/restore.sqlite3 /var/lib/nohentai/nohentai.sqlite3
sudo systemctl start nohentai-api nohentai-worker
sudo systemctl start nohentai-backup.timer
# 数据库内的调度状态来自所恢复的快照，请在后台确认。
```

目录备份名已存在时改用新名字，勿覆盖。恢复快照会同时恢复当时的内容、配置、加密凭证、会话与任务状态；恢复后建议轮换管理密码以使旧会话失效。使用对应加密密钥，否则无法读取凭证。前端可把 current 符号链接切回先前 release，但后端降级前必须确认数据库 schema 兼容；本版 schema 为 3，拒绝高于 3 的数据库；旧 schema 1 代码不能读取升级后的库。

确认主动批量取消收藏，需要绕过 20% 保护时，先停止常驻 worker，在具备生产环境变量的本机维护终端执行：

```sh
sudo systemctl stop nohentai-worker
# 本机命令需要加载与 systemd 相同的环境文件，可通过 transient unit：
sudo systemd-run --wait --pipe --collect --uid=nohentai --gid=nohentai \
  -p WorkingDirectory=/opt/nohentai \
  -p EnvironmentFile=/etc/nohentai/nohentai.env \
  -p Environment=NOHENTAI_DATA_DIR=/var/lib/nohentai \
  /opt/nohentai/.venv/bin/python -m backend.cli sync favorites --allow-favorites-shrink
sudo systemctl start nohentai-worker
```

该放行仅作用于这一次本机运行，admin 和定时任务不能关闭保护。维护命令也持有同一 worker 文件锁，不与正常任务并行。

## 参考

实现依据 [FastAPI 运行部署](https://fastapi.tiangolo.com/deployment/manually/)、[Python SQLite 事务与备份](https://docs.python.org/3/library/sqlite3.html)、[systemd timer](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html)。本地自动化不证明 Vultr 网络、来源站 Cookie 或付费服务凭证有效，最终上线按上面的验收步骤验证。

## schema 1 升级到 schema 2

先通过 SQLite Backup API 生成一致性快照，并把回退用快照复制到七份轮换目录之外。保存当前代码 commit、Nginx 配置和静态 release 路径；在副本上调用新版本 `db.initialize()`，比较来源、覆盖、书目、规则、凭证和快照数据，执行 `PRAGMA integrity_check`。迁移保留旧历史并为书目 / 规则分配稳定内部 ID，重复启动不会重建 ID。

正式升级时停止 API 和 worker，重新备份最终库，安装锁定依赖（包含 Pillow），更新代码，然后以服务用户和生产环境运行迁移。启动 API 验证后再启动 worker 和发布前端。新调度默认关闭，不要同时启用旧 sync.timer。已有 HTTPS 的 Nginx 只合并新 API 压缩规则和 `/media/` 代理，不能覆盖为仓库 HTTP 模板。

迁移失败会回滚事务。若上线验收失败需要回退，保持 API / worker 停止，使用新的空数据目录恢复停写前 schema 1 快照，恢复旧代码与静态 release，再启动；不能只降级代码。升级后已产生写入时，先备份并评估数据合并，不直接覆盖。

本机密码恢复（新密码文件需预先创建为 0600；命令不在参数中暴露密码）：

```sh
sudo systemd-run --wait --pipe --collect --uid=nohentai --gid=nohentai \
  -p WorkingDirectory=/opt/nohentai \
  -p EnvironmentFile=/etc/nohentai/nohentai.env \
  -p Environment=NOHENTAI_DATA_DIR=/var/lib/nohentai \
  /opt/nohentai/.venv/bin/python -m backend.cli reset-admin --password-file /var/lib/nohentai/new-admin-password
```

文件应仅允许 nohentai 用户读取，重置完成后立即删除。原始初始密码文件不再反映后台修改后的密码。

## schema 2 升级到 schema 3

停写并保留一致性回退备份后，使用新代码初始化数据库，将事务新增 job_events 表及索引。内容、记录版本、任务、凭证、账户和会话保持不变。历史任务仍保留摘要，无法追溯升级前未采集的日志。部署前检查无运行任务，先验证数据库副本；旧代码不接受 schema 3，回退需旧代码与对应旧库一起恢复。

## 大图片请求与测试目录隔离

OCR 图片请求会超过 Nginx 内存请求体缓冲，落盘到 client_body_temp_path。生产 `/var/lib/nginx/body` 以及 `/var/lib/nginx/proxy` 的目录及其分层子目录应由实际 Nginx worker 用户（本机 www-data）拥有并可写；不能将其变成 root 私有目录。否则大请求会在到达 API 前返回 HTML 500。

浏览器测试的 Nginx 实例必须显式设置独立的 client_body_temp_path、proxy_temp_path、fastcgi_temp_path、uwsgi_temp_path 和 scgi_temp_path，全部位于临时目录；不能复用编译默认路径。tests/browser_smoke.py 现在检查大 OCR 请求能到达后端，且测试前后生产临时目录所有者和权限保持不变。

图片代理允许受信任 H@H 子域名通过 HTTPS 的非特权自定义端口获取图片；其他来源仍限制标准 HTTPS 端口。域名、公网 DNS、逐跳重定向与不向 H@H 转发 Cookie 的约束保留。

### 每日筛选条件与结果快照

每日规则只配置名称、搜索表达式、分类、页数、最低评分和回溯天数，不再维护独立的展示标签。前台直接显示实际条件；同步发布时将条件与结果一起冻结，之后修改规则不会改写已发布结果的条件说明。

旧配置或历史恢复中的 `filters` 字段会兼容忽略。旧结果优先从匹配的成功任务检查点恢复当时规则；无法恢复时，前台明确标注展示的是当前保存规则，待下次同步后获得完整条件快照。此变更不需要数据库 schema 迁移。


## 跨版本静态资源

`publish-frontend.sh` 将带 hash 的资源先写入 `/srv/nohentai/www/assets`，新 release 的 `assets` 链接到该共享目录，再原子切换 `current`。首次使用会从保留的旧 release 补齐历史资源，旧标签页仍可加载原版本尚未访问的路由，无需通过强制刷新丢弃后台草稿。Nginx 继续使用现有 `current/assets` 路径，不需要覆盖现有 HTTPS 配置。

共享资源暂不自动清理；如需回收磁盘，先制定旧页面保留期与引用检查，不能随 release 切换立即删除旧 hash 文件。`NOHENTAI_WEB_ROOT` 可指定独立的发布目录，自动测试仅使用临时目录，不修改生产 release。
