#!/usr/bin/env python3
"""
Google Sheets 数据同步脚本
拉取「未来数位数据统计」表并写入 web-static/public/data/future_digi.json

功能：
  - 失败自动重试（默认 3 次）
  - 全部重试失败时回退到上一份备份
  - 备份历史数据（默认保留最近 5 份）

环境变量（写入 .env 或 GitHub Secrets）：
  GOOGLE_SERVICE_ACCOUNT_JSON   服务账号 JSON 文件的完整内容（必填）
  FUTURE_DIGI_SPREADSHEET_ID    表格 ID（有默认值）
  FUTURE_DIGI_GID               工作表 gid（有默认值）
  SHEETS_MAX_RETRIES            最大重试次数（默认 3）
  SHEETS_RETRY_DELAY            重试间隔秒数（默认 2.0）
  SHEETS_BACKUP_KEEP_COUNT      保留备份数量（默认 5）
"""

import json
import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

# ── 配置 ──────────────────────────────────────────────────────────────────────

load_dotenv()

SPREADSHEET_ID = os.getenv("FUTURE_DIGI_SPREADSHEET_ID", "1lRJep59n157L7Qs0XqRsENDX6UVgTT_jPWCPHcKO_P4")
WORKSHEET_GID = int(os.getenv("FUTURE_DIGI_GID", "1621827636"))

MAX_RETRIES = int(os.getenv("SHEETS_MAX_RETRIES", "3"))
RETRY_DELAY = float(os.getenv("SHEETS_RETRY_DELAY", "2.0"))
BACKUP_KEEP_COUNT = int(os.getenv("SHEETS_BACKUP_KEEP_COUNT", "5"))

DATA_DIR = Path("web-static/public/data")
OUTPUT_FILE = DATA_DIR / "future_digi.json"
BACKUP_DIR = DATA_DIR / "backup_data"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# ── 日志 ──────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── 备份管理 ──────────────────────────────────────────────────────────────────


def create_backup(source: Path) -> Path | None:
    """备份当前输出文件，返回备份路径；文件不存在则返回 None。"""
    if not source.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"future_digi_backup_{timestamp}.json"
    shutil.copy2(source, backup_path)
    log.info(f"已备份当前数据: {backup_path}")
    return backup_path


def rotate_backups():
    """删除超出 BACKUP_KEEP_COUNT 数量的旧备份（按文件名排序，删最旧的）。"""
    backups = sorted(BACKUP_DIR.glob("future_digi_backup_*.json"))
    excess = backups[: max(0, len(backups) - BACKUP_KEEP_COUNT)]
    for f in excess:
        f.unlink()
        log.info(f"已删除过期备份: {f.name}")


def restore_from_latest_backup() -> bool:
    """从最新备份恢复数据文件，成功返回 True，无备份返回 False。"""
    backups = sorted(BACKUP_DIR.glob("future_digi_backup_*.json"))
    if not backups:
        log.warning("无可用备份，无法回退。")
        return False
    latest = backups[-1]
    shutil.copy2(latest, OUTPUT_FILE)
    log.info(f"已回退到备份: {latest.name}")
    return True


# ── 数据拉取 ──────────────────────────────────────────────────────────────────


def _load_credentials() -> Credentials:
    """从 GOOGLE_SERVICE_ACCOUNT_JSON 环境变量读取服务账号 JSON 内容并加载凭证。"""
    json_content = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not json_content:
        raise EnvironmentError("未设置环境变量 GOOGLE_SERVICE_ACCOUNT_JSON，" "请将服务账号 JSON 内容写入 .env 文件。")
    return Credentials.from_service_account_info(json.loads(json_content), scopes=SCOPES)


def fetch_sheet_data() -> list[dict]:
    """通过服务账号连接 Google Sheets，返回工作表全部行数据。"""
    creds = _load_credentials()
    gc = gspread.authorize(creds)

    spreadsheet = gc.open_by_key(SPREADSHEET_ID)

    worksheet = spreadsheet.get_worksheet_by_id(WORKSHEET_GID)
    if worksheet is None:
        raise ValueError(f"未找到 gid={WORKSHEET_GID} 的工作表")

    # 空单元格统一为 None（JSON 中输出 null）
    records = worksheet.get_all_records(default_blank=None)
    log.info(f"成功获取 {len(records)} 行数据（工作表: {worksheet.title}）")
    return records


def fetch_with_retry() -> list[dict]:
    """带指数退避重试的数据拉取；全部失败时抛出 RuntimeError。"""
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info(f"拉取数据 (第 {attempt}/{MAX_RETRIES} 次)...")
            return fetch_sheet_data()
        except Exception as exc:
            last_error = exc
            log.warning(f"第 {attempt} 次失败: {exc}")
            if attempt < MAX_RETRIES:
                delay = RETRY_DELAY * attempt  # 简单线性退避
                log.info(f"{delay:.1f}s 后重试...")
                time.sleep(delay)
    raise RuntimeError(f"重试 {MAX_RETRIES} 次后仍失败") from last_error


# ── 主流程 ────────────────────────────────────────────────────────────────────


def main():
    log.info("=" * 50)
    log.info("未来数位 Google Sheets 数据同步开始")
    log.info("=" * 50)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 备份当前文件（同步前保存快照，便于回退）
    backup_path = create_backup(OUTPUT_FILE)

    try:
        # 2. 拉取数据（带重试）
        records = fetch_with_retry()

        # 3. 写入新数据
        output = {
            "generatedAt": datetime.now().isoformat(),
            "count": len(records),
            "data": records,
        }
        OUTPUT_FILE.write_text(
            json.dumps(output, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.info(f"已写入: {OUTPUT_FILE}（{len(records)} 条记录）")

        # 4. 备份轮转（保留最近 N 份）
        rotate_backups()

    except Exception as exc:
        log.error(f"同步失败: {exc}")

        # 5. 回退：恢复到上一份备份（若有）
        if backup_path:
            log.info("正在回退数据...")
            restore_from_latest_backup()
        else:
            log.warning("同步失败且无历史备份，输出文件未变更。")

        raise SystemExit(1)

    log.info("同步完成")


if __name__ == "__main__":
    main()
