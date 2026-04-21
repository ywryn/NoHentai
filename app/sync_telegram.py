#!/usr/bin/env python3
"""
sync_telegram.py — 拉取 Telegram Bot 收到的转发消息，压缩加密媒体文件后归档。

流程：
  1. 从 telegram_forwards.json 读取 offset 及历史归档
  2. getUpdates 拉取未消费消息
  3. 过滤转发消息：
     - 图片：下载最大分辨率 → 阶梯压缩至 <100KB → AES-256-GCM 加密
     - 视频：下载 thumbnail → 同上处理
     - 其他类型：仅保存元数据
  4. 追加写入 telegram_forwards.json（增量，offset 同步更新）
  媒体文件由 workflow 负责打包上传至 GitHub Releases
"""

import io
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from PIL import Image

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ── 路径 ───────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "web-static/public/data"
MEDIA_DIR = DATA_DIR / "telegram_media"
PHOTOS_DIR = MEDIA_DIR / "photos"
THUMBNAILS_DIR = MEDIA_DIR / "thumbnails"
FORWARDS_JSON = DATA_DIR / "telegram_forwards.json"
# ── 配置 ───────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ENCRYPTION_PASSWORD = os.environ.get("TELEGRAM_ENCRYPTION_PASSWORD", "")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
FILE_API = f"https://api.telegram.org/file/bot{BOT_TOKEN}"

TARGET_KB = 100
# 固定 salt（公开无妨，安全性由密码本身保证）
PBKDF2_SALT = b"NoHentai-Telegram-Salt-v1"
PBKDF2_ITERATIONS = 100_000


# ── 加密 ───────────────────────────────────────────────────────────────────
def derive_key(password: str) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=PBKDF2_SALT,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode())


def encrypt(data: bytes, key: bytes) -> bytes:
    """返回 [12字节 IV] + [GCM 密文+tag]"""
    iv = os.urandom(12)
    return iv + AESGCM(key).encrypt(iv, data, None)


# ── 图片压缩 ───────────────────────────────────────────────────────────────
def _to_webp(raw: bytes) -> bytes:
    """仅做格式转换，不压缩（用于已在目标大小以内的图片）。"""
    img = Image.open(io.BytesIO(raw))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="WebP", quality=90, method=4)
    return buf.getvalue()


def compress_image(raw: bytes, target_kb: int = TARGET_KB) -> bytes:
    """
    阶梯压缩策略：
      1. 按原始大小设定初始最大边长，缩放图片
      2. 二分搜索 WebP quality，找到不超过 target_kb 的最大质量
      3. 若仍超标，逐步缩小尺寸直到达标
    """
    target = target_kb * 1024
    img = Image.open(io.BytesIO(raw))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    original_size = len(raw)

    # 初始尺寸上限（越大的原图压得越狠）
    if original_size < 500_000:
        max_dim = 1920
    elif original_size < 2_000_000:
        max_dim = 1600
    elif original_size < 10_000_000:
        max_dim = 1280
    else:
        max_dim = 960

    w, h = img.size
    if max(w, h) > max_dim:
        ratio = max_dim / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    def encode(image: Image.Image, quality: int) -> bytes:
        buf = io.BytesIO()
        image.save(buf, format="WebP", quality=quality, method=6)
        return buf.getvalue()

    # 二分搜索最优 quality
    lo, hi, best = 15, 88, None
    for _ in range(10):
        if lo > hi:
            break
        mid = (lo + hi) // 2
        data = encode(img, mid)
        if len(data) <= target:
            best = data
            lo = mid + 1
        else:
            hi = mid - 1

    if best is not None:
        return best

    # 二分结束仍超标：逐步缩小尺寸
    scale = 0.8
    while True:
        w, h = img.size
        nw, nh = max(int(w * scale), 200), max(int(h * scale), 200)
        img = img.resize((nw, nh), Image.LANCZOS)
        data = encode(img, 30)
        if len(data) <= target or max(nw, nh) <= 200:
            return data
        scale = 0.8


# ── Telegram API ───────────────────────────────────────────────────────────
def get_updates(offset: int) -> list:
    r = requests.post(
        f"{TELEGRAM_API}/getUpdates",
        json={"offset": offset, "limit": 100, "timeout": 0},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("result", [])


def get_file_path(file_id: str) -> str | None:
    r = requests.post(f"{TELEGRAM_API}/getFile", json={"file_id": file_id}, timeout=30)
    if r.status_code != 200:
        logger.warning("getFile 失败 %s: %s", file_id, r.text)
        return None
    return r.json()["result"]["file_path"]


def download_file(file_path: str) -> bytes | None:
    r = requests.get(f"{FILE_API}/{file_path}", timeout=60)
    if r.status_code != 200:
        logger.warning("下载失败: %s", file_path)
        return None
    return r.content


# ── 媒体处理 ───────────────────────────────────────────────────────────────
def process_image(file_id: str, file_unique_id: str, key: bytes, subdir: Path, label: str) -> dict | None:
    """下载 → 压缩 → 加密 → 写文件，返回媒体文件元数据。"""
    file_path = get_file_path(file_id)
    if not file_path:
        return None
    raw = download_file(file_path)
    if not raw:
        return None

    original_size = len(raw)
    try:
        # 已在目标大小以内则跳过压缩，直接转 WebP
        compressed = compress_image(raw) if original_size > TARGET_KB * 1024 else _to_webp(raw)
    except Exception as e:
        logger.warning("压缩失败 %s: %s，使用原始数据", file_unique_id, e)
        compressed = raw

    encrypted = encrypt(compressed, key)
    out_path = subdir / f"{file_unique_id}.webp.enc"
    out_path.write_bytes(encrypted)

    rel = out_path.relative_to(DATA_DIR)
    logger.info(
        "%s %s: %d KB → %d KB (%.0f%%)",
        label, file_unique_id,
        original_size // 1024,
        len(compressed) // 1024,
        len(compressed) / original_size * 100,
    )
    return {
        "local_path": str(rel),
        "original_size": original_size,
        "compressed_size": len(compressed),
    }


# ── 消息解析 ───────────────────────────────────────────────────────────────
def parse_message(msg: dict, key: bytes) -> dict | None:
    """将 Telegram message dict 转换为归档记录，非转发消息返回 None。"""
    if not (msg.get("forward_origin") or msg.get("forward_from_chat")):
        return None

    record = {
        "message_id": msg["message_id"],
        "date": msg["date"],
        "forward_origin": msg.get("forward_origin"),
        "forward_from_chat": msg.get("forward_from_chat"),
        "forward_from_message_id": msg.get("forward_from_message_id"),
        "forward_date": msg.get("forward_date"),
        "media_group_id": msg.get("media_group_id"),
        "caption": msg.get("caption"),
        "caption_entities": msg.get("caption_entities"),
        "text": msg.get("text"),
        "type": "unknown",
        "media_meta": {},
        "media_file": None,
    }

    if msg.get("photo"):
        photo = msg["photo"][-1]  # 取最大分辨率
        record["type"] = "photo"
        record["media_meta"] = {
            "file_unique_id": photo.get("file_unique_id"),
            "width": photo.get("width"),
            "height": photo.get("height"),
            "file_size": photo.get("file_size"),
        }
        record["media_file"] = process_image(
            photo["file_id"], photo["file_unique_id"], key, PHOTOS_DIR, "photo"
        )

    elif msg.get("video"):
        video = msg["video"]
        record["type"] = "video"
        record["media_meta"] = {
            "file_unique_id": video.get("file_unique_id"),
            "width": video.get("width"),
            "height": video.get("height"),
            "duration": video.get("duration"),
            "file_size": video.get("file_size"),
            "mime_type": video.get("mime_type"),
            "file_name": video.get("file_name"),
        }
        thumb = video.get("thumbnail") or video.get("thumb")
        if thumb:
            record["media_file"] = process_image(
                thumb["file_id"], thumb["file_unique_id"], key, THUMBNAILS_DIR, "thumbnail"
            )

    elif msg.get("document"):
        doc = msg["document"]
        record["type"] = "document"
        record["media_meta"] = {
            "file_unique_id": doc.get("file_unique_id"),
            "file_name": doc.get("file_name"),
            "mime_type": doc.get("mime_type"),
            "file_size": doc.get("file_size"),
        }
        # document 类型若为图片（image/jpeg 等）也尝试下载封面
        mime = doc.get("mime_type", "")
        if mime.startswith("image/") and doc.get("file_size", 0) <= 20 * 1024 * 1024:
            record["media_file"] = process_image(
                doc["file_id"], doc["file_unique_id"], key, PHOTOS_DIR, "doc-image"
            )
        thumb = doc.get("thumbnail") or doc.get("thumb")
        if thumb and not record["media_file"]:
            record["media_file"] = process_image(
                thumb["file_id"], thumb["file_unique_id"], key, THUMBNAILS_DIR, "doc-thumb"
            )

    elif msg.get("animation"):
        anim = msg["animation"]
        record["type"] = "animation"
        record["media_meta"] = {
            "file_unique_id": anim.get("file_unique_id"),
            "width": anim.get("width"),
            "height": anim.get("height"),
            "duration": anim.get("duration"),
            "file_size": anim.get("file_size"),
        }
        thumb = anim.get("thumbnail") or anim.get("thumb")
        if thumb:
            record["media_file"] = process_image(
                thumb["file_id"], thumb["file_unique_id"], key, THUMBNAILS_DIR, "anim-thumb"
            )

    elif msg.get("text"):
        record["type"] = "text"

    return record


# ── 主流程 ─────────────────────────────────────────────────────────────────
def main() -> None:
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN 未设置")
        sys.exit(1)
    if not ENCRYPTION_PASSWORD:
        logger.error("TELEGRAM_ENCRYPTION_PASSWORD 未设置")
        sys.exit(1)

    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)

    # 加载归档（offset 也存在其中）
    archive: dict = {"offset": 0, "generatedAt": "", "count": 0, "messages": []}
    if FORWARDS_JSON.exists():
        saved = json.loads(FORWARDS_JSON.read_text())
        archive.update(saved)
        archive.setdefault("offset", 0)  # 兼容无 offset 字段的旧文件
    existing_ids = {m["message_id"] for m in archive["messages"]}
    # (来源频道ID, 原始消息ID) 组合去重，防止同一原始消息多次转发重复保存
    existing_origins = {
        (m["forward_from_chat"]["id"], m["forward_from_message_id"])
        for m in archive["messages"]
        if m.get("forward_from_chat") and m.get("forward_from_message_id")
    }

    key = derive_key(ENCRYPTION_PASSWORD)
    updates = get_updates(archive["offset"])
    logger.info("拉取到 %d 条 update（当前 offset=%d）", len(updates), archive["offset"])

    new_records: list[dict] = []
    for update in updates:
        archive["offset"] = update["update_id"] + 1
        msg = update.get("message") or update.get("channel_post")
        if not msg or msg["message_id"] in existing_ids:
            continue
        # 原始来源去重
        origin_key = None
        chat = msg.get("forward_from_chat")
        fwd_msg_id = msg.get("forward_from_message_id")
        if chat and fwd_msg_id:
            origin_key = (chat["id"], fwd_msg_id)
            if origin_key in existing_origins:
                logger.info("跳过重复转发 chat_id=%s fwd_msg_id=%s", chat["id"], fwd_msg_id)
                continue
        record = parse_message(msg, key)
        if record:
            new_records.append(record)
            if origin_key:
                existing_origins.add(origin_key)
            logger.info("已归档 message_id=%d type=%s", record["message_id"], record["type"])

    if new_records:
        archive["messages"].extend(new_records)
        archive["count"] = len(archive["messages"])

    archive["generatedAt"] = datetime.now(timezone.utc).isoformat()
    FORWARDS_JSON.write_text(
        json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if new_records:
        logger.info("新增 %d 条，共 %d 条", len(new_records), archive["count"])
    else:
        logger.info("无新转发消息，offset 已更新至 %d", archive["offset"])


if __name__ == "__main__":
    main()
