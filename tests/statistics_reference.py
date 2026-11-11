"""Independent Python test oracle for SQL statistics; not a runtime implementation."""
from collections import Counter
from datetime import datetime, timedelta, timezone
import re
from backend.validation import CATEGORIES
from backend.db import now

def generate(galleries, translations):
    categories = Counter(g.get('category') for g in galleries)
    namespaces = {item['namespace']: item.get('data', {}) for item in translations.get('data', [])}
    tags = {}
    for kind in ('artist', 'other', 'female', 'male', 'character', 'parody'):
        counter = Counter(t for g in galleries for t in g.get('tags', []) if t.startswith(kind + ':'))
        tags[kind] = []
        for tag, count in counter.most_common(20):
            namespace, value = tag.split(':', 1)
            detail = namespaces.get(namespace, {}).get(value, {})
            tags[kind].append({'tag': tag, 'namespace': namespace, 'value': value, 'count': count,
                               'tag_cn': detail.get('name', ''), 'intro': detail.get('intro', ''), 'links': detail.get('links', '')})
    posted, fav, days = Counter(), Counter(), Counter()
    for g in galleries:
        try:
            date = datetime.fromtimestamp(int(g['posted']), timezone.utc)
            posted[f'{date.year}-Q{(date.month - 1) // 3 + 1}'] += 1
        except (KeyError, ValueError, OverflowError, OSError, TypeError):
            pass
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})', str(g.get('favTime', '')))
        if m:
            year, month, _ = map(int, m.groups())
            fav[f'{year}-Q{(month - 1) // 3 + 1}'] += 1
            days[m[0]] += 1
    today = datetime.now(timezone.utc).date()
    try:
        start = today.replace(year=today.year - 1)
    except ValueError:
        start = today.replace(year=today.year - 1, day=28)
    start -= timedelta(days=(start.weekday() + 1) % 7)
    matrix = []
    date = start
    while date <= today:
        matrix.append({'x': (date - start).days // 7, 'y': (date.weekday() + 1) % 7, 'v': days[date.isoformat()], 'd': date.isoformat()})
        date += timedelta(days=1)
    return {'generatedAt': now(), 'stats': {'total_count': len(galleries), 'categories': {c: categories[c] for c in CATEGORIES}},
            'tags': tags, 'quarterly': [{'quarter': q, 'postedCount': posted[q], 'favTimeCount': fav[q]} for q in sorted(posted.keys() | fav.keys())],
            'heatmap': {'data': matrix, 'maxValue': max([1] + [d['v'] for d in matrix])}}
