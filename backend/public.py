import json
from . import db, stats
from .validation import merge, books_csv

FILES = {'galleries.json', 'daily_search.json', 'future_digi.csv', 'translations.json', 'translate-config.json', 'stats.json', 'release.json'}


def dataset(name):
    with db.connect() as con:
        con.execute('BEGIN')
        patches, version = db.resource(con, 'overrides')
        if name == 'galleries.json':
            return merge(db.galleries(con), patches)
        if name == 'daily_search.json':
            return [dict(g, galleries=merge(g['galleries'], patches)) for g in db.snapshot(con, 'daily', [])]
        if name == 'future_digi.csv':
            return books_csv([json.loads(r[0]) for r in con.execute('SELECT data FROM books ORDER BY position')])
        if name == 'translations.json':
            return db.snapshot(con, 'translations', {'data': []})
        if name == 'translate-config.json':
            return {'defaultOcr': db.resource(con, 'translate')[0]['defaultOcr']}
        if name == 'stats.json':
            return stats.generate(merge(db.galleries(con), patches), db.snapshot(con, 'translations', {'data': []}))
        if name == 'release.json':
            return db.snapshot(con, 'release', {'commit': version, 'builtAt': db.now()})
    raise KeyError(name)


def books():
    from . import catalog
    with db.connect() as con:
        con.execute('BEGIN')
        rows = con.execute("""SELECT b.id,b.data AS book,g.data AS gallery,p.data AS patch
            FROM books b LEFT JOIN galleries g ON g.gid=b.gallery_gid
            LEFT JOIN gallery_overrides p ON p.gid=g.gid ORDER BY b.position""").fetchall()
        index = catalog.translations(con)
        items = []
        for row in rows:
            gallery = json.loads(row['gallery']) if row['gallery'] else None
            if gallery and row['patch']:
                gallery.update(json.loads(row['patch']))
            if gallery and gallery.get('hidden'):
                gallery = None
            if gallery:
                gallery = {key: gallery.get(key) for key in (*catalog.LIST_FIELDS,'tags','uploader')}
            items.append({'id': row['id'], 'book': json.loads(row['book']), 'gallery': gallery})
        # Only dictionaries used by linked books are returned, never the full tag database.
        used = {tag for item in items if item['gallery'] for tag in item['gallery'].get('tags', [])}
        translation_groups = {}
        for tag in used:
            if tag in index:
                detail = index[tag]
                translation_groups.setdefault(detail['namespace'], {})[detail['value']] = {k: detail.get(k, '') for k in ('name','intro','links')}
        return {'items': items, 'translations': {'data': [{'namespace':ns,'data':data} for ns,data in translation_groups.items()]}}


def daily():
    from . import catalog
    with db.connect() as con:
        con.execute('BEGIN')
        patches, _ = db.resource(con, 'overrides')
        groups = [dict(g, galleries=merge(g.get('galleries', []), patches)) for g in db.snapshot(con, 'daily', [])]
        index = catalog.translations(con)
        tags = {tag for group in groups for g in group['galleries'] for tag in g.get('tags', [])}
        translated = {}
        for tag in tags:
            if tag in index:
                detail = index[tag]
                translated.setdefault(detail['namespace'], {})[detail['value']] = {k:detail.get(k,'') for k in ('name','intro','links')}
        return {'groups': groups, 'translations': {'data':[{'namespace':ns,'data':values} for ns,values in translated.items()]}}
