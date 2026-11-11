import csv
import io
import re
from app.daily_config import validate_groups

CATEGORIES = ['Doujinshi', 'Manga', 'Artist CG', 'Game CG', 'Western', 'Non-H', 'Image Set', 'Cosplay', 'Asian Porn', 'Misc']
BOOK_FIELDS = ['ID', '书名', '收价', '原价', '日文名', 'sid', '备注', 'cover']
PATCH_FIELDS = {'title', 'title_jpn', 'tags', 'category', 'uploader', 'hidden', 'thumb'}


def check(value, message):
    if not value:
        raise ValueError(message)


def text(v, size):
    return isinstance(v, str) and len(v) <= size and '\0' not in v


def validate(name, value):
    if name == 'daily':
        return validate_groups(value)
    if name == 'translate':
        check(isinstance(value, dict) and set(value) == {'model', 'defaultOcr', 'jsonMode'}, '翻译配置字段不正确')
        check(value['model'] is None or (text(value['model'], 150) and value['model'].strip()), '模型名不正确')
        check(value['defaultOcr'] in ('google', 'paddle', 'ocrspace'), 'OCR 来源不正确')
        check(value['jsonMode'] is None or type(value['jsonMode']) is bool, 'JSON 模式不正确')
    elif name == 'overrides':
        check(isinstance(value, dict) and len(value) <= 20000, '覆盖格式不正确')
        for gid, patch in value.items():
            check(re.fullmatch(r'[1-9][0-9]{0,14}', gid) and isinstance(patch, dict) and set(patch) <= PATCH_FIELDS, '覆盖 ID 或字段不正确')
            for k, v in patch.items():
                if k == 'hidden':
                    check(type(v) is bool, '隐藏状态必须为布尔值')
                elif k == 'thumb':
                    check(isinstance(v,str) and re.fullmatch(r'/media/[a-f0-9]{32}\.webp',v), '覆盖封面需使用已上传的图片')
                elif k == 'tags':
                    check(isinstance(v, list) and len(v) <= 500 and all(text(t, 200) for t in v), '标签不正确')
                elif k == 'category':
                    check(v in CATEGORIES, '分类不正确')
                else:
                    check(text(v, 5000), '覆盖文字不正确')
    elif name == 'printed':
        check(isinstance(value, list) and len(value) <= 10000, '书单格式不正确')
        result = []
        for book in value:
            check(isinstance(book, dict) and set(book) <= set(BOOK_FIELDS), '书单字段不正确')
            b = {k: book.get(k, '') for k in BOOK_FIELDS}
            check(all(text(v, 5000) for v in b.values()), '书单文字不正确')
            b['ID'], b['sid'] = b['ID'].strip(), b['sid'].strip()
            check(b['ID'] and (b['书名'].strip() or b['日文名'].strip()), '书目缺少 ID 或书名')
            check(not b['sid'] or re.fullmatch(r'[0-9]+', b['sid']), '关联画廊 ID 必须为数字')
            check(not re.search(r'[/\\]', b['cover']) and b['cover'] not in ('.', '..'), '封面应为文件名')
            result.append(b)
        return result
    else:
        raise ValueError('不允许访问此资源')
    return value


def read_books(content):
    reader = csv.DictReader(io.StringIO(content.lstrip('\ufeff')))
    check(reader.fieldnames and set(reader.fieldnames) == set(BOOK_FIELDS), 'CSV 表头不正确')
    return validate('printed', list(reader))


def books_csv(books):
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=BOOK_FIELDS)
    writer.writeheader()
    writer.writerows(books)
    return output.getvalue()


def merge(source, patches, include_hidden=False):
    result = [dict(g, **patches.get(str(g['gid']), {})) for g in source]
    return result if include_hidden else [g for g in result if not g.get('hidden')]
