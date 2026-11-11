#!/usr/bin/env python3
"""
EhTagTranslation 标签翻译数据库同步脚本
从 GitHub Releases 下载最新 db.text.json 并写入 translations.json

功能：
  - 下载失败自动重试（默认 3 次）
  - 写入前校验 JSON 合法性
  - 下载失败时保留现有文件，不中断整体同步流程

环境变量（可选）：
  EHTAG_MAX_RETRIES         最大重试次数（默认 3）
  EHTAG_RETRY_DELAY         重试间隔秒数（默认 5.0）
"""

import json
import logging
import os
import time
from pathlib import Path

import requests

# ── 配置 ──────────────────────────────────────────────────────────────────────

DOWNLOAD_URL = "https://github.com/EhTagTranslation/Database/releases/latest/download/db.text.json"

MAX_RETRIES = int(os.getenv("EHTAG_MAX_RETRIES", "3"))
RETRY_DELAY = float(os.getenv("EHTAG_RETRY_DELAY", "5.0"))

DATA_DIR = Path("web-static/public/data")
OUTPUT_FILE = DATA_DIR / "translations.json"

# ── 日志 ──────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── 下载与校验 ────────────────────────────────────────────────────────────────


def download_with_retry() -> bytes:
    """带重试的下载；全部失败时抛出 RuntimeError。"""
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info(f"下载翻译数据库 (第 {attempt}/{MAX_RETRIES} 次)...")
            resp = requests.get(DOWNLOAD_URL, timeout=60, allow_redirects=True)
            resp.raise_for_status()
            log.info(f"下载成功，大小: {len(resp.content) / 1024:.1f} KB")
            return resp.content
        except Exception as exc:
            last_error = exc
            log.warning(f"第 {attempt} 次下载失败: {exc}")
            if attempt < MAX_RETRIES:
                log.info(f"{RETRY_DELAY:.1f}s 后重试...")
                time.sleep(RETRY_DELAY)
    raise RuntimeError(f"重试 {MAX_RETRIES} 次后仍失败") from last_error


def validate_dictionary(data: dict, previous=None) -> dict:
    """Validate the complete consumer contract before replacing a working dictionary."""
    if not isinstance(data, dict) or not isinstance(data.get('data'), list) or not data['data']:
        raise ValueError('标签词典为空或结构不正确')
    namespaces = set()
    count = 0
    for group in data['data']:
        if not isinstance(group, dict) or not isinstance(group.get('namespace'), str) or not group['namespace'] or group['namespace'] in namespaces or not isinstance(group.get('data'), dict):
            raise ValueError('标签词典命名空间结构不正确')
        namespaces.add(group['namespace'])
        for tag, detail in group['data'].items():
            if not isinstance(tag, str) or not tag or not isinstance(detail, dict) or any(not isinstance(detail.get(key, ''), str) for key in ('name', 'intro', 'links')):
                raise ValueError('标签词典条目结构不正确')
            count += 1
    if not count:
        raise ValueError('标签词典没有有效条目')
    if previous:
        try:
            validate_dictionary(previous)
        except ValueError:
            pass  # A valid incoming snapshot must be able to repair an old corrupt one.
        else:
            old_count = sum(len(g['data']) for g in previous['data'])
            if count < old_count * .8:
                raise ValueError('标签词典数量下降超过 20%，保留原数据')
    return data


def validate_and_parse(content: bytes) -> dict:
    return validate_dictionary(json.loads(content))


# ── 主流程 ────────────────────────────────────────────────────────────────────


def main():
    log.info("=" * 50)
    log.info("EhTagTranslation 翻译数据库同步开始")
    log.info("=" * 50)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # 1. 下载（带重试）
        content = download_with_retry()

        # 2. 校验 JSON
        data = validate_and_parse(content)
        version = data.get("version", "unknown")
        ns_count = len(data.get("data", []))
        log.info(f"校验通过：version={version}，namespace 数量={ns_count}")

        # 3. 写入目标文件
        OUTPUT_FILE.write_bytes(content)
        log.info(f"已写入: {OUTPUT_FILE}")

    except Exception as exc:
        log.warning(f"翻译数据库同步失败，保留现有文件: {exc}")
        raise SystemExit(0)   # 不阻断整体 sync workflow

    log.info("同步完成")


if __name__ == "__main__":
    main()
