# 服务器每日同步

systemd 的 `nohentai-sync.timer` 每天 UTC 20:00（北京时间次日 04:00）向 SQLite 队列加入全量同步，`Persistent=true` 可在关机错过时间后补触发。独立 `nohentai-worker` 持续处理任务，API 不执行长时间抓取。无 GitHub Actions、Git 提交或前端重新构建。

运行过程：

1. 使用 SQLite Backup API 建立一致性备份。
2. 收藏抓取复用 `app/sync_script.py` 的分页和完整元数据检查。
3. 下载并验证 EhTagTranslation 数据。
4. 使用数据库中的每日规则抓取全部分组，元数据缺失、重复条目或分页循环均失败。
5. 在一个 SQLite 事务内校验收藏数量、规则版本，再发布全部结果及数据版本。

任一步失败，上一份完整数据保留。单项任务只替换自己的数据。人工覆盖、书单与凭证不受同步影响。抓取阶段不持有数据库写锁。

收藏分页 HTTP 错误、没有可解析条目、分页循环、重复画廊、缺失元数据批次都会失败。比当前数据库减少超过 20% 时拒绝提交。旧脚本的 `ALLOW_FAVORITES_SHRINK` 环境变量不会绕过新后端保护。确认主动批量删除时，先备份并停止 worker，由本机维护人员执行 `sync favorites --allow-favorites-shrink` 显式放行，详见部署文档。

同步不再写入仓库中的 `web-static/public/data`。该目录只作为初次导入的种子数据；旧备份 JSON 不会发布到新网站。`app/` 中旧脚本的独立文件输出模式仅保留作离线维护兼容，生产任务使用 `backend/jobs.py` 的数据库发布逻辑。

```sh
# 本地环境或已加载生产环境变量的维护终端
.venv/bin/python -m backend.cli enqueue all
.venv/bin/python -m backend.cli worker --once
```

`worker --once` 仅在无常驻 worker 时使用，单实例文件锁防止两个 worker 同时处理队列。收藏完整性测试见 `tests/test_sync_script.py`，事务发布和失败保留测试见 `tests/test_backend.py`。
