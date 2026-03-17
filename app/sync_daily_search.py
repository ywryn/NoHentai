#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日搜索同步脚本 —— 多筛选组
输出：web-static/public/data/daily_search.json，格式为列表 [{...}, {...}, {...}]
直接覆盖，无备份
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))
from exhentai_search import ExHentaiGallerySearch, ExHentaiUrlBuilder

OUTPUT_PATH = Path(__file__).parent.parent / "web-static/public/data/daily_search.json"


def make_cutoff(days: int = 10) -> str:
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")


# ── 筛选组定义 ────────────────────────────────────────────────────────────────

GROUPS = [
    # Group 1：Manga · 80~800p · ★4+  （排除 webtoon / rough TL / full censorship）
    {
        "name": "Manga · 80~800p · ★4+",
        "filters": ["Manga", "Chinese", "80~800p", "★4+", "-webtoon", "-rough TL", "-full censorship"],
        "build": lambda: (
            ExHentaiUrlBuilder()
            .set_keyword(
                "language:chinese$ "
                "-other:webtoon$ "
                '-other:"rough translation$" '
                '-other:"full censorship$"'
            )
            .set_only_category(ExHentaiUrlBuilder.CAT_MANGA)
            .set_page_range(80, 800)
            .set_min_rating(4)
        ),
        "cutoff_days": 10,
    },
    # Group 2：Doujinshi · 8p+ · ★4+  （同样排除 webtoon / rough TL / full censorship）
    # 对应 URL：?f_cats=1021&f_search=language:chinese$+...&advsearch=1&f_spf=8&f_srdd=4
    {
        "name": "Doujinshi · 8p+ · ★4+",
        "filters": ["Doujinshi", "Chinese", "8p+", "★4+", "-webtoon", "-rough TL", "-full censorship"],
        "build": lambda: _build_doujinshi_filtered(),
        "cutoff_days": 5,
    },
    # Group 3：Doujinshi + Manga · Webtoon · CN
    # 对应 URL：?f_cats=1017&f_search=other:webtoon$+language:chinese$&advsearch=1
    # f_cats=1017 → 1023^1017=6=CAT_DOUJINSHI(2)+CAT_MANGA(4)，即同时包含两类
    {
        "name": "Doujinshi+Manga · Webtoon · CN",
        "filters": ["Doujinshi", "Manga", "Chinese", "webtoon"],
        "build": lambda: (
            ExHentaiUrlBuilder()
            .set_keyword("other:webtoon$ language:chinese$")
            .set_only_category(ExHentaiUrlBuilder.CAT_DOUJINSHI | ExHentaiUrlBuilder.CAT_MANGA)
        ),
        "cutoff_days": 10,
    },
]


def _build_doujinshi_filtered() -> ExHentaiUrlBuilder:
    """Group 2：仅设置 min_pages（无 max_pages），直接操作 builder 属性。"""
    builder = ExHentaiUrlBuilder()
    builder.set_keyword(
        "language:chinese$ "
        "-other:webtoon$ "
        '-other:"rough translation$" '
        '-other:"full censorship$"'
    ).set_only_category(ExHentaiUrlBuilder.CAT_DOUJINSHI)
    builder.advsearch = True
    builder.min_pages = 8
    builder.min_rating = 4
    return builder


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    search = ExHentaiGallerySearch()
    output = []

    for i, group in enumerate(GROUPS):
        cutoff = make_cutoff(group["cutoff_days"])
        builder = group["build"]()

        print(f"\n[{i+1}/{len(GROUPS)}] {group['name']}")
        print(f"  URL: {builder.build()}")
        print(f"  截止日期: {cutoff}")

        result = search.search_with_builder(builder, fetch_details=True, cutoff_date=cutoff)

        if not result["success"]:
            print(f"  ✗ 失败: {result['error']}", file=sys.stderr)
            galleries = []
        else:
            galleries = result["galleries"]
            print(f"  ✓ 找到 {len(galleries)} 个画廊")

        output.append({
            "name": group["name"],
            "filters": group["filters"],
            "generatedAt": datetime.now().isoformat(),
            "cutoffDate": cutoff,
            "galleries": galleries,
        })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total = sum(len(g["galleries"]) for g in output)
    print(f"\n已写入 {OUTPUT_PATH}（共 {len(output)} 组，{total} 条画廊）")


if __name__ == "__main__":
    main()
