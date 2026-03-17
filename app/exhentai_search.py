#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ExHentai Gallery Search API Implementation in Python
仅支持 ExHentai.org
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import urlencode

from dotenv import load_dotenv

load_dotenv()

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# 配置信息（仅ExHentai）
# ============================================================================


class Config:
    """ExHentai 配置"""

    # ExHentai 搜索页（需要 cookies）
    DOMAIN = "exhentai.org"
    HOST = f"https://{DOMAIN}/"

    # gdata API 端点（使用 e-hentai 公开端点，无需 cookies）
    GDATA_API_URL = "https://api.e-hentai.org/api.php"

    # gdata 重试配置（从 .env 读取）
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY_SECONDS = float(os.getenv("RETRY_DELAY_SECONDS", "2.0"))

    # 搜索结果输出路径
    OUTPUT_PATH = os.getenv("OUTPUT_PATH", "search_result.json")

    # Cookies配置（ExHentai 搜索页必需）
    COOKIES = {
        "ipb_member_id": os.getenv("EXHENTAI_COOKIE_MEMBER_ID"),
        "ipb_pass_hash": os.getenv("EXHENTAI_COOKIE_PASS_HASH"),
        "igneous": os.getenv("EXHENTAI_COOKIE_IGNEOUS"),
    }


# ============================================================================
# 日期工具函数
# ============================================================================


def _parse_cutoff(cutoff: Union[str, datetime, None]) -> Optional[datetime]:
    """将截止日期参数统一转为 datetime，None 原样返回。"""
    if cutoff is None:
        return None
    if isinstance(cutoff, datetime):
        return cutoff
    # 接受 "YYYY-MM-DD" 或 "YYYY-MM-DD HH:MM"
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(cutoff, fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析截止日期: {cutoff!r}，请使用 'YYYY-MM-DD' 格式")


def _parse_posted(posted: str) -> datetime:
    """
    将 posted 字段解析为 datetime。
    HTML 解析阶段为 "YYYY-MM-DD HH:MM"；
    gdata API 返回 Unix 时间戳字符串（如 "1773635717"）。
    """
    if posted.isdigit():
        return datetime.fromtimestamp(int(posted))
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(posted, fmt)
        except ValueError:
            continue
    return datetime.min  # 无法解析时视为最早时间，不会误过滤


# ============================================================================
# HTTP 请求会话设置
# ============================================================================


class ExHentaiSession:
    """ExHentai HTTP会话管理"""

    def __init__(self):
        self.session = requests.Session()

        # 设置重试策略
        retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # 设置User-Agent
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

        # 添加Cookies（ExHentai必需）
        self._set_cookies()

    def _set_cookies(self):
        """设置Cookies（ExHentai必需）"""
        cookies = {k: v for k, v in Config.COOKIES.items() if v is not None}
        if not cookies or cookies.get("igneous") is None:
            logger.warning("警告：未设置igneous Cookie，ExHentai访问可能被拒绝")
        if cookies:
            self.session.cookies.update(cookies)
            logger.info(f"已设置 {len(cookies)} 个Cookie")

    def get(self, url: str, **kwargs) -> requests.Response:
        """发送GET请求"""
        return self.session.get(url, timeout=30, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        """发送POST请求"""
        return self.session.post(url, timeout=30, **kwargs)


# ============================================================================
# 搜索URL构建器
# ============================================================================


class ExHentaiUrlBuilder:
    """ExHentai 搜索URL构建器"""

    # 搜索模式
    MODE_NORMAL = 0
    MODE_SUBSCRIPTION = 1
    MODE_WATCHED = 2
    MODE_FAVORITE = 3
    MODE_IMAGE_SEARCH = 4

    # 分类位掩码（f_cats 为排除掩码，即值=1023减去要包含的分类之和）
    CAT_MISC = 1
    CAT_DOUJINSHI = 2
    CAT_MANGA = 4
    CAT_ARTIST_CG = 8
    CAT_GAME_CG = 16
    CAT_IMAGE_SET = 32
    CAT_COSPLAY = 64
    CAT_ASIAN_PORN = 128
    CAT_NON_H = 256
    CAT_WESTERN = 512
    CAT_ALL = 1023

    def __init__(self, mode: int = MODE_NORMAL):
        self.mode = mode
        self.keyword = None
        self.page = 0
        self.f_cats = 0  # 排除分类掩码（0=不过滤）
        self.advsearch = False
        self.min_pages = None
        self.max_pages = None
        self.min_rating = None  # 2~5

    def set_keyword(self, keyword: str) -> "ExHentaiUrlBuilder":
        """设置搜索关键词"""
        self.keyword = keyword
        return self

    def set_page(self, page: int) -> "ExHentaiUrlBuilder":
        """设置页码（从0开始）"""
        self.page = page
        return self

    def set_category_exclude(self, exclude_mask: int) -> "ExHentaiUrlBuilder":
        """
        设置分类排除掩码（f_cats）。
        例如只保留 Manga：exclude_mask = CAT_ALL ^ CAT_MANGA = 1019
        """
        self.f_cats = exclude_mask
        return self

    def set_only_category(self, include_mask: int) -> "ExHentaiUrlBuilder":
        """
        设置只包含某些分类（自动计算排除掩码）。
        例如只保留 Manga：set_only_category(CAT_MANGA)
        """
        self.f_cats = self.CAT_ALL ^ include_mask
        return self

    def set_page_range(self, min_pages: int, max_pages: int) -> "ExHentaiUrlBuilder":
        """设置页数范围（需同时启用高级搜索）"""
        self.min_pages = min_pages
        self.max_pages = max_pages
        self.advsearch = True
        return self

    def set_min_rating(self, stars: int) -> "ExHentaiUrlBuilder":
        """设置最低评分（2~5星，需同时启用高级搜索）"""
        self.min_rating = stars
        self.advsearch = True
        return self

    def build(self) -> str:
        """生成完整的搜索URL"""
        params = {}

        if self.keyword:
            params["f_search"] = self.keyword

        if self.f_cats > 0:
            params["f_cats"] = self.f_cats

        if self.page > 0:
            params["page"] = self.page

        if self.advsearch:
            params["advsearch"] = 1
            if self.min_pages is not None:
                params["f_spf"] = self.min_pages
            if self.max_pages is not None:
                params["f_spt"] = self.max_pages
            if self.min_rating is not None:
                params["f_srdd"] = self.min_rating

        if params:
            return f"{Config.HOST}?{urlencode(params)}"
        return Config.HOST

    def get_mode(self) -> int:
        """获取模式"""
        return self.mode


# ============================================================================
# HTML解析器
# ============================================================================


class GalleryListParser:
    """画廊列表HTML解析器"""

    @staticmethod
    def parse(html: str) -> Dict:
        """解析ExHentai画廊列表HTML页面（compact视图：table.itg.gltc）"""
        result = {"galleries": [], "next_url": None, "error": None}

        try:
            soup = BeautifulSoup(html, "html.parser")

            if "sad panda" in html.lower():
                result["error"] = "访问受限（Sad Panda）"
                return result

            # 画廊列表：table.itg 下每个 tr（跳过表头）
            table = soup.find("table", class_="itg")
            if not table:
                logger.warning("未找到画廊列表表格")
                return result

            for row in table.find_all("tr"):
                # 跳过表头行
                if row.find("th"):
                    continue
                try:
                    gallery = GalleryListParser._parse_row(row)
                    if gallery:
                        result["galleries"].append(gallery)
                except Exception as e:
                    logger.warning(f"解析单行失败: {e}")

            # 翻页：ExHentai用游标分页，直接取 a#unext 的完整 href
            next_link = soup.find("a", id="unext")
            if next_link and next_link.get("href"):
                result["next_url"] = next_link["href"]

        except Exception as e:
            result["error"] = f"HTML解析错误: {str(e)}"
            logger.error(f"解析HTML失败: {e}")

        return result

    @staticmethod
    def _parse_row(row) -> Optional[Dict]:
        """解析单个画廊行（compact视图 tr）"""
        # td.gl3c.glname 包含链接、标题、标签
        name_td = row.find("td", class_="gl3c")
        if not name_td:
            return None

        link = name_td.find("a")
        if not link or not link.get("href"):
            return None

        # 从 /g/{gid}/{token}/ 提取
        parts = [p for p in link["href"].rstrip("/").split("/") if p]
        if len(parts) < 2:
            return None
        token = parts[-1]
        gid_str = parts[-2]
        if not gid_str.isdigit():
            return None

        # 标题
        title_elem = name_td.find("div", class_="glink")
        title = title_elem.get_text(strip=True) if title_elem else "Unknown"

        # 标签：div.gt 的 title 属性，如 "female:ahegao"、"language:chinese"
        tags = [t["title"] for t in name_td.find_all("div", class_="gt") if t.get("title")]

        # 缩略图：td.gl2c 里的 img，优先取 data-src（懒加载），否则取 src
        thumb = ""
        thumb_td = row.find("td", class_="gl2c")
        if thumb_td:
            img = thumb_td.find("img")
            if img:
                thumb = img.get("data-src") or img.get("src", "")

        # 上传者、页数：td.gl4c
        uploader, pages = "Unknown", 0
        info_td = row.find("td", class_="gl4c")
        if info_td:
            uploader_a = info_td.find("a")
            if uploader_a:
                uploader = uploader_a.get_text(strip=True)
            divs = info_td.find_all("div")
            for div in divs:
                text = div.get_text(strip=True)
                if "pages" in text:
                    try:
                        pages = int(text.split()[0])
                    except ValueError:
                        pass

        # 发布时间：div#posted_{gid}
        posted = ""
        posted_div = row.find("div", id=f"posted_{gid_str}")
        if posted_div:
            posted = posted_div.get_text(strip=True)

        # 分类：td.gl1c div.cn
        category = ""
        cat_td = row.find("td", class_="gl1c")
        if cat_td:
            cat_div = cat_td.find("div")
            if cat_div:
                category = cat_div.get_text(strip=True)

        return {
            "gid": int(gid_str),
            "token": token,
            "title": title,
            "title_jpn": "",
            "thumb": thumb,
            "uploader": uploader,
            "posted": posted,
            "pages": pages,
            "rating": 0.0,
            "category": category,
            "tags": tags,
        }


# ============================================================================
# gdata API 调用
# ============================================================================


class GalleryApiClient:
    """
    gdata API 客户端
    使用 e-hentai 公开端点（api.e-hentai.org），无需携带 cookies。
    """

    def get_gallery_data(
        self,
        galleries: List[Dict],
        max_retries: int = None,
        retry_delay: float = None,
    ) -> List[Dict]:
        """
        批量获取画廊详细元数据，支持失败重试。
        API 每批最多 25 条。
        """
        if not galleries:
            return galleries

        max_retries = max_retries if max_retries is not None else Config.MAX_RETRIES
        retry_delay = retry_delay if retry_delay is not None else Config.RETRY_DELAY_SECONDS

        batch_results: Dict[int, List[Dict]] = {}
        failed_batches: List[Tuple[int, List[Dict], int]] = []
        total_batches = (len(galleries) + 24) // 25

        logger.info(f"开始获取元数据，共 {total_batches} 批，每批最多 25 条")

        # 第一轮
        for i in range(0, len(galleries), 25):
            batch = galleries[i : i + 25]
            batch_num = i // 25 + 1
            success, data = self._fetch_batch(batch, batch_num)
            if success:
                batch_results[i] = data
            else:
                failed_batches.append((i, batch, batch_num))

        # 重试轮次
        for retry_round in range(1, max_retries + 1):
            if not failed_batches:
                break
            logger.info(f"第 {retry_round} 轮重试，处理 {len(failed_batches)} 个失败批次...")
            remaining: List[Tuple[int, List[Dict], int]] = []
            for i, batch, batch_num in failed_batches:
                time.sleep(retry_delay)
                success, data = self._fetch_batch(batch, batch_num)
                if success:
                    batch_results[i] = data
                else:
                    remaining.append((i, batch, batch_num))
            failed_batches = remaining

        if failed_batches:
            nums = [str(n) for _, _, n in failed_batches]
            logger.error(f"经过 {max_retries} 次重试后，批次 {', '.join(nums)} 仍失败，将保留原始数据")

        # 按原顺序合并：直接用 API 完整 meta 覆盖，严格保留原始字段名
        result = []
        for i in range(0, len(galleries), 25):
            batch = galleries[i : i + 25]
            if i in batch_results:
                for gallery, meta in zip(batch, batch_results[i]):
                    gallery.update(meta)
            result.extend(batch)

        logger.info(f"元数据获取完成，共 {len(result)} 条")
        return result

    def _fetch_batch(self, batch: List[Dict], batch_num: int) -> Tuple[bool, List[Dict]]:
        """单批 API 调用，返回 (success, gmetadata列表)"""
        gidlist = [[g["gid"], g["token"]] for g in batch]
        payload = {"method": "gdata", "gidlist": gidlist, "namespace": 1}
        logger.info(f"请求第 {batch_num} 批，共 {len(batch)} 条")
        try:
            response = requests.post(Config.GDATA_API_URL, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json().get("gmetadata", [])
            if len(data) != len(batch):
                logger.warning(f"第 {batch_num} 批数据不完整：期望 {len(batch)} 条，实际 {len(data)} 条")
            logger.info(f"第 {batch_num} 批成功，获取 {len(data)} 条")
            return True, data
        except Exception as e:
            logger.error(f"第 {batch_num} 批请求失败: {e}")
            return False, []


# ============================================================================
# 主搜索接口
# ============================================================================


class ExHentaiGallerySearch:
    """ExHentai 画廊搜索主类"""

    def __init__(self):
        self.session = ExHentaiSession()
        self.api_client = GalleryApiClient()

    def search(self, keyword: str, page: int = 0, fetch_details: bool = True) -> Dict:
        """
        搜索ExHentai画廊

        Args:
            keyword: 搜索关键词
            page: 页码（从0开始）
            fetch_details: 是否调用API获取详细信息

        Returns:
            搜索结果字典
        """
        result = {"success": False, "galleries": [], "total_pages": 1, "current_page": page, "next_page": None, "error": None}

        try:
            # 构建搜索URL
            url_builder = ExHentaiUrlBuilder()
            url_builder.set_keyword(keyword).set_page(page)
            search_url = url_builder.build()

            logger.info(f"搜索URL: {search_url}")

            # 获取搜索结果页面
            response = self.session.get(search_url)
            response.raise_for_status()

            # 解析HTML
            parse_result = GalleryListParser.parse(response.text)

            if parse_result["error"]:
                result["error"] = parse_result["error"]
                return result

            # 获取画廊列表
            galleries = parse_result["galleries"]
            logger.info(f"找到 {len(galleries)} 个画廊")

            # 可选：调用API获取详细信息
            if fetch_details and galleries:
                logger.info("正在获取详细信息...")
                galleries = self.api_client.get_gallery_data(galleries)

            result["success"] = True
            result["galleries"] = galleries
            result["next_page"] = parse_result.get("next_cursor")

        except requests.exceptions.ConnectionError:
            result["error"] = "网络连接失败"
            logger.error("连接失败")
        except requests.exceptions.Timeout:
            result["error"] = "请求超时"
            logger.error("请求超时")
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"搜索失败: {e}")

        return result

    def search_with_builder(
        self,
        builder: "ExHentaiUrlBuilder",
        fetch_details: bool = True,
        cutoff_date: Union[str, datetime, None] = None,
    ) -> Dict:
        """
        使用已配置好的 ExHentaiUrlBuilder 执行搜索。

        Args:
            builder:      配置好的 URL 构建器
            fetch_details: 是否调用 gdata API 获取完整元数据
            cutoff_date:  截止日期，仅返回该日期之后（含）的画廊。
                          接受 "YYYY-MM-DD" 字符串或 datetime 对象。
                          为 None 时只获取第一页。
        """
        cutoff_dt = _parse_cutoff(cutoff_date)
        result = {"success": False, "galleries": [], "next_page": None, "error": None}

        try:
            all_galleries: List[Dict] = []
            next_url: Optional[str] = builder.build()
            page_num = 0

            while next_url:
                page_num += 1
                logger.info(f"获取第 {page_num} 页: {next_url}")

                response = self.session.get(next_url)
                response.raise_for_status()

                parse_result = GalleryListParser.parse(response.text)
                if parse_result["error"]:
                    result["error"] = parse_result["error"]
                    return result

                galleries = parse_result["galleries"]
                logger.info(f"第 {page_num} 页找到 {len(galleries)} 个画廊")

                if not galleries:
                    break

                all_galleries.extend(galleries)

                # 判断是否需要继续翻页
                if cutoff_dt is None:
                    # 无截止日期，只取一页
                    result["next_page"] = parse_result.get("next_url")
                    break

                last_posted = galleries[-1].get("posted", "")
                if last_posted and _parse_posted(last_posted) < cutoff_dt:
                    # 最后一条已早于截止日期，无需继续
                    logger.info(f"最后一条 posted={last_posted!r} 已早于截止日期，停止翻页")
                    break

                next_url = parse_result.get("next_url")
                if not next_url:
                    break

            # 截止日期过滤
            if cutoff_dt is not None:
                before = len(all_galleries)
                all_galleries = [g for g in all_galleries if _parse_posted(g.get("posted", "")) >= cutoff_dt]
                logger.info(f"截止日期过滤：{before} → {len(all_galleries)} 条")

            # 获取详细元数据
            if fetch_details and all_galleries:
                logger.info("正在获取详细元数据...")
                all_galleries = self.api_client.get_gallery_data(all_galleries)

            result["success"] = True
            result["galleries"] = all_galleries

        except requests.exceptions.ConnectionError:
            result["error"] = "网络连接失败"
        except requests.exceptions.Timeout:
            result["error"] = "请求超时"
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"搜索失败: {e}")

        return result

    def get_popular(self, page: int = 0) -> Dict:
        """获取ExHentai热门画廊"""
        url = f"{Config.HOST}popular"
        if page > 0:
            url += f"?page={page}"

        result = {"success": False, "galleries": [], "error": None}

        try:
            response = self.session.get(url)
            response.raise_for_status()
            parse_result = GalleryListParser.parse(response.text)

            result["success"] = True
            result["galleries"] = parse_result["galleries"]
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"获取热门画廊失败: {e}")

        return result


# ============================================================================
# 使用示例
# ============================================================================


def main():
    """
    筛选案例：Manga分类，中文，80~800页，4星以上，
    排除 webtoon / rough translation / full censorship
    对应URL：https://exhentai.org/?f_cats=1019&f_search=language%3Achinese%24+...
    """
    search = ExHentaiGallerySearch()

    keyword = "language:chinese$ " "-other:webtoon$ " '-other:"rough translation$" ' '-other:"full censorship$"'

    url_builder = ExHentaiUrlBuilder()
    url_builder.set_keyword(keyword).set_only_category(ExHentaiUrlBuilder.CAT_MANGA).set_page_range(80, 800).set_min_rating(4)

    print("搜索URL:", url_builder.build())
    print("=" * 80)

    # cutoff_date：只返回该日期之后的画廊，并自动翻页直到覆盖截止日期
    # 设为 None 则只取第一页
    result = search.search_with_builder(url_builder, fetch_details=True, cutoff_date="2026-03-01")

    if result["success"]:
        galleries = result["galleries"]
        print(f"找到 {len(galleries)} 个画廊  |  下一页游标: {result['next_page']}")

        # 输出前5条预览
        for i, g in enumerate(galleries[:5], 1):
            print(f"\n[{i}] {g['title']}")
            print(f"     GID:{g['gid']}  页数:{g['pages']}  评分:{g['rating']}  上传者:{g['uploader']}")
            lang_tags = [t for t in g.get("tags", []) if t.startswith("language:")]
            print(f"     语言标签: {lang_tags}")

        # 写入 JSON 文件
        output_path = Config.OUTPUT_PATH
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(galleries, f, ensure_ascii=False, indent=2)
        print(f"\n结果已写入 {output_path}（共 {len(galleries)} 条）")
    else:
        print(f"搜索失败: {result['error']}")


if __name__ == "__main__":
    main()
