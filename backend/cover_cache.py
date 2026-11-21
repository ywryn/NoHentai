"""Persistent cache for upstream catalog covers, separate from uploaded media."""
import hashlib
import io
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, ImageOps
from . import db, settings, upstream
from .security import fail


def path_for(digest):
    return settings.DATA_DIR / 'source-covers' / (digest + '.webp')


def cover_url(data):
    value = data.get('thumb') or data.get('image')
    return value if isinstance(value, str) else ''


def enqueue_current(con):
    current = set()
    galleries = db.galleries(con)
    galleries.extend(gallery for group in db.snapshot(con, 'daily', []) for gallery in group.get('galleries', []))
    for gallery in galleries:
        url = cover_url(gallery)
        if not isinstance(url, str) or len(url) > 2000:
            continue
        try:
            parts = urlsplit(url)
        except ValueError:
            continue
        if parts.scheme == 'https' and any(parts.hostname == host or (parts.hostname or '').endswith('.' + host)
                                           for host in upstream.IMAGE_SUFFIXES):
            current.add((str(gallery.get("gid", "")), url))
    urls = {url for _, url in current}
    con.executemany('INSERT OR IGNORE INTO source_covers(url,next_check) VALUES (?,0)', [(url,) for url in sorted(urls)])
    old = {(row['gid'], row['url']): row['previous_url'] for row in con.execute('SELECT * FROM source_cover_refs')}
    ready = {row['url']: row['digest'] for row in con.execute('SELECT url,digest FROM source_covers WHERE digest IS NOT NULL')}
    fallback = {}
    for (gid, url), previous in old.items():
        if url in ready and path_for(ready[url]).is_file():
            fallback[gid] = url
        elif previous in ready and gid not in fallback:
            fallback[gid] = previous
    con.execute('DELETE FROM source_cover_refs')
    con.executemany('INSERT INTO source_cover_refs VALUES (?,?,?)',
                    [(gid, url, old.get((gid, url), fallback.get(gid))) for gid, url in current])
    for url in urls & ready.keys():
        if not path_for(ready[url]).is_file():
            con.execute('UPDATE source_covers SET next_check=0 WHERE url=?', (url,))


def prefer(con, galleries):
    urls = list({cover_url(g) for g in galleries if g and cover_url(g).startswith('https://')})
    cached, prior = {}, {}
    for offset in range(0, len(urls), 500):
        batch = urls[offset:offset + 500]
        params = ','.join('?' for _ in batch)
        for row in con.execute(f'SELECT url,digest FROM source_covers WHERE digest IS NOT NULL AND url IN ({params})', batch):
            if path_for(row['digest']).is_file():
                cached[row['url']] = '/media/source-' + row['digest'] + '.webp'
        if all(url in cached for url in batch):
            continue
        for row in con.execute(f"""SELECT r.gid,r.url,c.digest FROM source_cover_refs r
                JOIN source_covers c ON c.url=r.previous_url
                WHERE c.digest IS NOT NULL AND r.url IN ({params})""", batch):
            if path_for(row['digest']).is_file():
                prior[(row['gid'], row['url'])] = '/media/source-' + row['digest'] + '.webp'
    for gallery in galleries:
        if not gallery:
            continue
        remote = cover_url(gallery)
        if url := cached.get(remote) or prior.get((str(gallery.get('gid')), remote)):
            gallery['thumb'] = url


def find(filename):
    path = path_for(filename.removeprefix('source-').removesuffix('.webp'))
    if not path.is_file():
        fail(404, '封面缓存不存在')
    return path


def refresh(con, gallery):
    url = cover_url(gallery)
    if not con.execute('UPDATE source_covers SET next_check=0,etag=NULL,modified=NULL WHERE url=?', (url,)).rowcount:
        fail(400, '此来源封面不可缓存')


def store_image(content):
    with Image.open(io.BytesIO(content), formats=['JPEG', 'PNG', 'WEBP', 'GIF']) as image:
        if image.width * image.height > 20_000_000:
            raise ValueError('封面尺寸过大')
        image = ImageOps.exif_transpose(image).convert('RGB')
        image.thumbnail((1600, 1600))
        output = io.BytesIO()
        image.save(output, 'WEBP', quality=85)
    content = output.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    path = path_for(digest)
    if not path.is_file():
        path.parent.mkdir(mode=0o700, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
            temporary = file.name
            file.write(content)
        Path(temporary).replace(path)
    return digest


def fetch_next():
    with db.connect() as con:
        row = con.execute('''SELECT * FROM source_covers WHERE next_check<=?
                          AND EXISTS (SELECT 1 FROM source_cover_refs WHERE source_cover_refs.url=source_covers.url)
                          ORDER BY next_check,url LIMIT 1''',
                          (time.time(),)).fetchone()
    if not row:
        return
    digest = row['digest']
    validators = {}
    if digest and path_for(digest).is_file():
        if row['etag']:
            validators['If-None-Match'] = row['etag']
        if row['modified']:
            validators['If-Modified-Since'] = row['modified']
    try:
        content, headers = upstream.fetch(row['url'], image=True, cover_validators=validators)
        if content is not None:
            digest = store_image(content)
        etag = headers.get('etag') or (row['etag'] if content is None else None)
        modified = headers.get('last-modified') or (row['modified'] if content is None else None)
        due = time.time() + 7 * 86400 if etag or modified else None
    except Exception:
        with db.connect() as con:
            con.execute('UPDATE source_covers SET next_check=? WHERE url=? AND next_check IS ?',
                        (time.time() + 86400, row['url'], row['next_check']))
        return
    with db.connect() as con:
        con.execute('UPDATE source_covers SET digest=?,etag=?,modified=?,next_check=? WHERE url=? AND next_check IS ?',
                              (digest, etag, modified, due, row['url'], row['next_check']))
