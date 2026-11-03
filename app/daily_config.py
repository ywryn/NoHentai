"""Daily search configuration shared by the scheduled scraper and admin JSON files."""
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / 'config/daily.json'
FIELDS = {'name', 'keyword', 'categories', 'minPages', 'maxPages', 'minRating', 'cutoffDays'}


def load_groups(path=CONFIG_PATH):
    return validate_groups(json.loads(Path(path).read_text(encoding='utf-8')))


def without_display_labels(group):
    return {key: value for key, value in group.items() if key != 'filters'} if isinstance(group, dict) else group


def conditions(group):
    return {key: group[key] for key in FIELDS - {'name'}}


def validate_groups(groups):
    if not isinstance(groups, list) or not 1 <= len(groups) <= 20:
        raise ValueError('每日筛选需要 1–20 个分组')
    groups = [without_display_labels(group) for group in groups]
    names = set()
    for g in groups:
        if not isinstance(g, dict) or set(g) != FIELDS:
            raise ValueError('每日筛选字段不完整或包含未知字段')
        if not isinstance(g['name'], str) or not g['name'].strip() or len(g['name']) > 120 or g['name'] in names:
            raise ValueError('分组名称为空或重复')
        names.add(g['name'])
        if not isinstance(g['keyword'], str) or len(g['keyword']) > 2000 or '\0' in g['keyword']:
            raise ValueError('搜索关键词不正确')
        for k, lo, hi in [('categories', 1, 1023), ('cutoffDays', 1, 365)]:
            if type(g[k]) is not int or not lo <= g[k] <= hi:
                raise ValueError(f'{k} 超出范围')
        for k, lo, hi in [('minPages', 1, 100000), ('maxPages', 1, 100000), ('minRating', 2, 5)]:
            if g[k] is not None and (type(g[k]) is not int or not lo <= g[k] <= hi):
                raise ValueError(f'{k} 超出范围')
        if g['minPages'] is not None and g['maxPages'] is not None and g['minPages'] > g['maxPages']:
            raise ValueError('最小页数不能大于最大页数')
    return groups
