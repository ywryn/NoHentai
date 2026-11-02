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
