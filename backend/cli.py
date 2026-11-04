"""Local administration. Does not contact GitHub/Vercel or modify source data."""
import argparse
import json
import os
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from . import db, settings
from .validation import read_books, validate


def initialize_data(source=None):
    root = Path(source or settings.ROOT)
    directory = root / 'web-static/public/data'
    read = lambda path: json.loads(path.read_text(encoding='utf-8'))
    # Validate everything before opening the write transaction.
    resources = {name: validate(name, read(root / f'config/{name}.json')) for name in ('daily', 'translate')}
    resources['overrides'] = validate('overrides', read(directory / 'gallery-overrides.json'))
    resources['printed'] = read_books((directory / 'future_digi.csv').read_text(encoding='utf-8-sig'))
    galleries = read(directory / 'galleries.json')
    daily, translations = read(directory / 'daily_search.json'), read(directory / 'translations.json')
    from app.sync_translations import validate_dictionary
    validate_dictionary(translations)
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        if con.execute('SELECT 1 FROM resources LIMIT 1').fetchone() or con.execute('SELECT 1 FROM resource_versions LIMIT 1').fetchone():
            raise RuntimeError('数据库已导入，拒绝重复导入覆盖线上编辑')
        db.replace_galleries(con, galleries)
        for name, value in resources.items():
            db.put_resource(con, name, value, '初次导入')
        db.put_snapshot(con, 'daily', daily)
        db.put_snapshot(con, 'translations', translations)
        db.put_snapshot(con, 'release', {'commit': 'initial-import', 'builtAt': db.now()})
    print(f'已导入 {len(galleries)} 个收藏画廊、{len(resources["printed"])} 条书目')


def backup():
    directory = settings.DATA_DIR / 'backups'
    directory.mkdir(mode=0o700, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    path = directory / f'nohentai-{stamp}.sqlite3'
    with db.connect() as source:
        target = sqlite3.connect(path)
        try:
            source.backup(target)
        finally:
            target.close()
    os.chmod(path, 0o600)
    uploads = settings.DATA_DIR / 'uploads'
    if uploads.exists() and any(uploads.iterdir()):
        media_path = path.with_suffix('.media.zip')
        with zipfile.ZipFile(media_path, 'w', compression=zipfile.ZIP_STORED) as archive:
            for file in uploads.glob('*.webp'):
                archive.write(file, arcname=file.name)
        os.chmod(media_path, 0o600)
    # Encrypted credentials are included; encryption key is intentionally separate.
    for old in sorted(directory.glob('nohentai-*.sqlite3'), reverse=True)[7:]:
        media_path = old.with_suffix('.media.zip')
        if media_path.exists():
            media_path.unlink()
        old.unlink()
    return path


def main():
    parser = argparse.ArgumentParser(description='NoHentai 服务器管理')
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--source', type=Path)
    sub.add_parser('backup')
    sub.add_parser('generate-key')
    reset = sub.add_parser('reset-admin')
    reset.add_argument('--password-file', type=Path, required=True)
    queue = sub.add_parser('enqueue')
    queue.add_argument('kind', choices=['all', 'favorites', 'translations', 'daily'])
    worker = sub.add_parser('worker')
    worker.add_argument('--once', action='store_true')
    sync = sub.add_parser('sync')
    sync.add_argument('kind', choices=['all', 'favorites', 'translations', 'daily'])
    sync.add_argument('--allow-favorites-shrink', action='store_true')
    execute = sub.add_parser('_execute')
    execute.add_argument('id', type=int)
    execute.add_argument('--allow-favorites-shrink', action='store_true')
    args = parser.parse_args()
    if args.command == 'generate-key':
        from cryptography.fernet import Fernet
        print(Fernet.generate_key().decode())
        return
    db.initialize()
    if args.command == 'reset-admin':
        from .security import hash_password, credential, digest
        import hmac
        password = args.password_file.read_text().strip()
        if not 16 <= len(password) <= 1024 or password.startswith('replace_with_'):
            raise ValueError('密码需为 16–1024 字符的独立密码')
        if hmac.compare_digest(digest(password), digest(credential('TRANS_PASSWORD'))):
            raise ValueError('管理密码不能与翻译密码相同')
        with db.connect() as con:
            con.execute('INSERT OR REPLACE INTO accounts VALUES (1,?,?)', (hash_password(password), db.now()))
            con.execute('DELETE FROM sessions')
        print('管理密码已重置，全部会话已撤销')
    elif args.command == 'init':
        initialize_data(args.source)
    elif args.command == 'backup':
        print(backup())
    elif args.command == 'enqueue':
        from .jobs import enqueue
        print(f'任务已排队：{enqueue(args.kind)}')
    elif args.command == 'worker':
        from .jobs import work
        work(args.once)
    elif args.command == 'sync':
        from .jobs import run_foreground
        print(f'同步完成：{run_foreground(args.kind, args.allow_favorites_shrink)}')
    elif args.command == '_execute':
        from .jobs import execute, JobFailure, JobCancelled, record_failure
        try:
            execute(args.id, args.allow_favorites_shrink)
        except JobCancelled as exc:
            record_failure(args.id, str(exc), 'cancelled')
            raise SystemExit(1)
        except JobFailure as exc:
            record_failure(args.id, str(exc))
            raise SystemExit(1)
        except Exception:
            record_failure(args.id, '同步失败，保留原数据；请检查上游可达性、凭证及数据完整性')
            raise SystemExit(1)


if __name__ == '__main__':
    main()
