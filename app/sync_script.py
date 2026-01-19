import json
import logging
import os
import re
import shutil
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Read configuration from environment variables
EXHENTAI_BASE_URL = os.getenv("EXHENTAI_BASE_URL")
EXHENTAI_COOKIE_MEMBER_ID = os.getenv("EXHENTAI_COOKIE_MEMBER_ID")
EXHENTAI_COOKIE_PASS_HASH = os.getenv("EXHENTAI_COOKIE_PASS_HASH")
EXHENTAI_COOKIE_IGNEOUS = os.getenv("EXHENTAI_COOKIE_IGNEOUS")

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
RETRY_DELAY_SECONDS = float(os.getenv("RETRY_DELAY_SECONDS", "2.0"))
BACKUP_KEEP_COUNT = int(os.getenv("BACKUP_KEEP_COUNT", "5"))

OUTPUT_RELATIVE_PATH = os.getenv("OUTPUT_RELATIVE_PATH", "web-static/public/data/galleries.json")
BACKUP_RELATIVE_DIR = os.getenv("BACKUP_RELATIVE_DIR", "web-static/public/data/backup_data")

ROOT_DIR = Path(__file__).resolve().parent.parent


class ExHentaiUtils:
    def __init__(self, base_url: str, cookies: dict, logger: logging.Logger):
        self.base_url = base_url
        self.cookies = cookies
        self.logger = logger
        self.session = requests.Session()
        self.session.cookies.update(cookies)

    def extract_favorites(self) -> list:
        result = []
        next_page = self.base_url

        while next_page:
            self.logger.info(f"正在爬取: {next_page}")
            response = self.session.get(next_page, timeout=30)
            if response.status_code != 200:
                self.logger.error(f"请求失败，状态码: {response.status_code}")
                break

            soup = BeautifulSoup(response.content, "html.parser")
            rows = soup.select("table.itg tr")

            for row in rows:
                try:
                    link = row.select_one('a[href*="/g/"]')
                    if not link:
                        continue
                    match = re.search(r"/g/(\d+)/(\w+)", link["href"])
                    if not match:
                        continue
                    gid, token = match.groups()

                    fav_category_elem = row.select_one("div[title]")
                    fav_category = fav_category_elem["title"].strip() if fav_category_elem else "Unknown"

                    fav_time_elem = row.select("td.glfc p")
                    fav_time = " ".join(p.text.strip() for p in fav_time_elem) if fav_time_elem else "Unknown"

                    result.append(
                        {
                            "gid": gid,
                            "token": token,
                            "favCategory": fav_category,
                            "favTime": fav_time,
                        }
                    )
                except Exception:
                    self.logger.exception("解析错误")

            next_link = soup.select_one("div.searchnav a#unext")
            if next_link and "href" in next_link.attrs:
                next_page = (
                    next_link["href"]
                    if next_link["href"].startswith("http")
                    else self.base_url.rsplit("/", 1)[0] + next_link["href"]
                )
            else:
                next_page = None

        return result

    def _fetch_single_batch_with_result(self, url: str, batch: list, batch_num: int) -> tuple:
        gidlist = [[int(f["gid"]), f["token"]] for f in batch]
        payload = {"method": "gdata", "gidlist": gidlist, "namespace": 1}

        self.logger.info(f"正在请求第 {batch_num} 批，共 {len(batch)} 条数据...")

        try:
            res = requests.post(url, json=payload, timeout=30)
            res.raise_for_status()
            data = res.json().get("gmetadata", [])

            if len(data) != len(batch):
                self.logger.warning(f"第 {batch_num} 批返回数据不完整：期望 {len(batch)} 条，实际 {len(data)} 条")

            self.logger.info(f"第 {batch_num} 批成功，获取 {len(data)} 条数据")
            return True, data
        except Exception as exc:
            self.logger.error(f"第 {batch_num} 批请求失败: {exc}")
            return False, []

    def fetch_gallery_metadatas(self, favorites: list, max_retries: int = 5, retry_delay: float = 2.0) -> list:
        import time as _time

        url = "https://api.e-hentai.org/api.php"
        batch_results = {}
        failed_batches = []
        total_batches = (len(favorites) + 24) // 25

        self.logger.info(f"开始获取元数据，共 {total_batches} 批，每批最多25条")

        for i in range(0, len(favorites), 25):
            batch = favorites[i : i + 25]
            batch_num = i // 25 + 1

            success, batch_data = self._fetch_single_batch_with_result(url, batch, batch_num)
            if success:
                batch_results[i] = batch_data
            else:
                failed_batches.append((i, batch, batch_num))

        if failed_batches:
            self.logger.warning(f"第一轮完成，有 {len(failed_batches)} 个批次失败，开始重试...")

            for retry_round in range(1, max_retries + 1):
                if not failed_batches:
                    break

                self.logger.info(f"第 {retry_round} 轮重试，处理 {len(failed_batches)} 个失败批次...")
                remaining_failed = []

                for i, batch, batch_num in failed_batches:
                    self.logger.info(f"重试第 {batch_num} 批（第{retry_round}次重试）...")
                    _time.sleep(retry_delay)

                    success, batch_data = self._fetch_single_batch_with_result(url, batch, batch_num)
                    if success:
                        batch_results[i] = batch_data
                    else:
                        remaining_failed.append((i, batch, batch_num))

                failed_batches = remaining_failed

                if failed_batches:
                    self.logger.warning(f"第 {retry_round} 轮重试完成，还有 {len(failed_batches)} 个批次失败")
                else:
                    self.logger.info(f"第 {retry_round} 轮重试完成，所有批次成功！")
                    break

        if failed_batches:
            failed_batch_nums = [str(batch_num) for _, _, batch_num in failed_batches]
            error_msg = (
                f"经过 {max_retries} 次重试后，仍有 {len(failed_batches)} 个批次失败"
                f"（批次: {', '.join(failed_batch_nums)}），为保证数据完整性，同步已终止"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

        # 合并元数据和收藏信息（favCategory、favTime）
        all_metadata = []
        for i in range(0, len(favorites), 25):
            if i in batch_results:
                batch_metadata = batch_results[i]
                batch_favorites = favorites[i : i + 25]

                # 将 favCategory 和 favTime 合并到元数据中
                for meta, fav in zip(batch_metadata, batch_favorites):
                    meta["favCategory"] = fav.get("favCategory", "Unknown")
                    meta["favTime"] = fav.get("favTime", "Unknown")

                all_metadata.extend(batch_metadata)

        self.logger.info(f"所有批次处理完成，成功获取 {len(all_metadata)} 条元数据（顺序已保持，已合并收藏信息）")
        return all_metadata

    def get_favorites_metadata(self, max_retries: int = 5, retry_delay: float = 2.0) -> list:
        favorites = self.extract_favorites()
        if not favorites:
            raise RuntimeError("收藏列表为空，可能是 cookies 无效或未通过 ExHentai 认证。")
        return self.fetch_gallery_metadatas(favorites, max_retries=max_retries, retry_delay=retry_delay)


def build_logger() -> logging.Logger:
    logger = logging.getLogger("sync_static_galleries")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(handler)
    return logger


def backup_json_file(target_file: Path, backup_dir: Path, keep_count: int = 5, prefix: str = "ex_backup") -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_file = backup_dir / f"{prefix}_{timestamp}.json"

    if target_file.exists():
        shutil.copy2(target_file, backup_file)

    backups = sorted(
        [p for p in backup_dir.iterdir() if p.name.startswith(f"{prefix}_") and p.suffix == ".json"],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old_file in backups[keep_count:]:
        old_file.unlink()


def main() -> int:
    logger = build_logger()

    if not all([EXHENTAI_COOKIE_MEMBER_ID, EXHENTAI_COOKIE_PASS_HASH, EXHENTAI_COOKIE_IGNEOUS]):
        logger.error("请先在脚本顶部配置 ExHentai cookies。")
        return 1

    cookies = {
        "ipb_member_id": EXHENTAI_COOKIE_MEMBER_ID,
        "ipb_pass_hash": EXHENTAI_COOKIE_PASS_HASH,
        "igneous": EXHENTAI_COOKIE_IGNEOUS,
    }

    output_path = ROOT_DIR / OUTPUT_RELATIVE_PATH
    backup_dir = ROOT_DIR / BACKUP_RELATIVE_DIR
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("开始同步 ExHentai 收藏数据")
    client = ExHentaiUtils(EXHENTAI_BASE_URL, cookies, logger=logger)

    try:
        data = client.get_favorites_metadata(max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY_SECONDS)
    except RuntimeError as exc:
        logger.error(f"同步失败: {exc}")
        return 1

    backup_json_file(output_path, backup_dir, keep_count=BACKUP_KEEP_COUNT)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"同步完成，共 {len(data)} 项，已写入 {OUTPUT_RELATIVE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
