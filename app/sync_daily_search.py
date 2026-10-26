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


from daily_config import load_groups


def build_group(group):
    builder = ExHentaiUrlBuilder().set_keyword(group['keyword']).set_only_category(group['categories'])
    builder.min_pages = group['minPages']
    builder.max_pages = group['maxPages']
    builder.min_rating = group['minRating']
    builder.advsearch = any(group[k] is not None for k in ('minPages', 'maxPages', 'minRating'))
    return builder


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    groups = load_groups()
    search = ExHentaiGallerySearch()
    output = []

    for i, group in enumerate(groups):
        cutoff = make_cutoff(group["cutoffDays"])
        builder = build_group(group)

        print(f"\n[{i+1}/{len(groups)}] {group['name']}")
        print(f"  URL: {builder.build()}")
        print(f"  截止日期: {cutoff}")

        result = search.search_with_builder(builder, fetch_details=True, cutoff_date=cutoff)

        if not result["success"]:
            print(f"  ✗ 失败: {result['error']}", file=sys.stderr)
            return 1  # Keep the previous complete snapshot on any group failure.
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
    sys.exit(main() or 0)
