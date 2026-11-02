"""Immutable uploaded covers outside the web root; metadata lives in SQLite."""
import base64
import io
import re
import secrets
import warnings
from pathlib import Path
from . import db, settings
from .security import fail


def directory():
    path = settings.DATA_DIR / 'uploads'
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def upload(encoded):
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = 20_000_000
    if not isinstance(encoded, str) or len(encoded) > 12*1024*1024:
        fail(400, '封面最大 8MB')
    try:
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > 8*1024*1024:
            fail(400, '封面最大 8MB')
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(raw))
            if image.format not in ('PNG', 'JPEG', 'WEBP'):
                fail(400, '仅支持 PNG、JPEG、WebP 封面')
            image.load()
            image = ImageOps.exif_transpose(image).convert('RGB')
            image.thumbnail((1600, 1600))
        output = io.BytesIO()
        image.save(output, format='WEBP', quality=85)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        fail(400, '图片像素超过 2000 万')
    except (ValueError, OSError):
        fail(400, '图片内容无效')
    record_id = secrets.token_hex(16)
    filename = record_id + '.webp'
    content = output.getvalue()
    path = directory() / filename
    # Files are immutable. A database rollback may leave an unreferenced file,
    # never a record pointing to a half-written image.
    with path.open('xb') as file:
        file.write(content)
    with db.connect() as con:
        con.execute('INSERT INTO media VALUES (?,?,?,?,?,?,?)',
                    (record_id, filename, 'image/webp', len(content), image.width, image.height, db.now()))
    return {'filename': filename, 'url': '/media/' + filename, 'width': image.width, 'height': image.height}


def find(filename):
    if not re.fullmatch(r'[a-f0-9]{32}\.webp', filename):
        fail(404, '封面不存在')
    with db.connect() as con:
        if not con.execute('SELECT 1 FROM media WHERE filename=?', (filename,)).fetchone():
            fail(404, '封面不存在')
    path = directory() / filename
    if not path.is_file():
        fail(404, '封面文件缺失')
    return path


def test_image():
    from PIL import Image, ImageDraw, PngImagePlugin
    image = Image.new('RGB', (320, 80), 'white')
    ImageDraw.Draw(image).text((15, 20), 'NoHentai Test', fill='black', font_size=28)
    info = PngImagePlugin.PngInfo()
    info.add_text('test-id', secrets.token_hex(16))
    stream = io.BytesIO()
    image.save(stream, format='PNG', pnginfo=info)
    return base64.b64encode(stream.getvalue()).decode()
