import base64
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from . import db, settings
from .security import credential, fail
from .upstream import json_request, fetch


def config():
    with db.connect() as con:
        value, _ = db.resource(con, 'translate')
    return {'model': value['model'] or credential('LLM_MODEL') or 'gpt-4o-mini',
            'jsonMode': value['jsonMode'] if value['jsonMode'] is not None else credential('LLM_JSON_MODE') == '1',
            'defaultOcr': value['defaultOcr']}


def cache_key(prefix, value):
    return prefix + hashlib.sha256(db.dumps(value).encode()).hexdigest()


def context_message(body):
    parts = []
    context = body.get('context') or {}
    if not isinstance(context, dict):
        fail(400, 'context 不正确')
    if context.get('title'):
        parts.append('本作标题：' + str(context['title'])[:200])
    if isinstance(context.get('tags'), list) and context['tags']:
        parts.append('本作标签：' + '，'.join(map(str, context['tags'][:40])))
    glossary = body.get('glossary') or {}
    if not isinstance(glossary, dict) or any(not isinstance(v, str) or len(v) > 500 for v in glossary.values()):
        fail(400, '术语表格式不正确')
    if glossary:
        parts.append('术语表（原文→译文，必须遵守）：\n' + '\n'.join(f'{k} → {v}' for k, v in list(glossary.items())[:60]))
    previous = body.get('previous') or []
    if not isinstance(previous, list) or any(not isinstance(p, list) or len(p) != 2 or any(not isinstance(v, str) or len(v) > 5000 for v in p) for p in previous):
        fail(400, '上一页对照格式不正确')
    if previous:
        parts.append('上一页的翻译对照（保持人名、称谓、口吻一致）：\n' + '\n'.join(f'{ja} ⇒ {zh}' for ja, zh in previous[-12:]))
    return '\n\n'.join(parts)


def translate(body):
    texts = body.get('texts')
    if not isinstance(texts, list) or not 1 <= len(texts) <= 200 or any(not isinstance(t, str) or len(t) > 5000 for t in texts) or sum(map(len, texts)) > 50000:
        fail(400, 'texts 应包含 1–200 条文字，总长度最多 50000')
    cfg = config()
    api_key, base = credential('LLM_API_KEY'), credential('LLM_API_BASE').rstrip('/')
    if not api_key or not base:
        fail(503, 'LLM 未配置')
    context = context_message(body)
    # Include gateway and key fingerprint: rotating providers cannot reuse another
    # provider's result under the same model label.
    key = cache_key('tr:v3:', [base, hashlib.sha256(api_key.encode()).hexdigest(), cfg, texts, context])
    cached = db.get_cache(key)
    if cached:
        return dict(cached, cached=True)
    messages = [{'role': 'system', 'content': (settings.ROOT / 'backend/translate-prompt.txt').read_text()}]
    if context:
        messages.append({'role': 'system', 'content': context})
    messages.append({'role': 'user', 'content': db.dumps({str(i + 1): t for i, t in enumerate(texts)})})
    payload = {'model': cfg['model'], 'messages': messages, 'temperature': .3, 'max_tokens': 4000}
    if cfg['jsonMode']:
        payload['response_format'] = {'type': 'json_object'}
    data = json_request('POST', base + '/chat/completions', headers={'Authorization': 'Bearer ' + api_key}, json=payload)
    content = data['choices'][0]['message']['content']
    try:
        parsed = json.loads(content[content.index('{'):content.rindex('}') + 1])
        if not isinstance(parsed, dict):
            raise ValueError()
    except (ValueError, TypeError):
        fail(502, '翻译服务返回的内容不是 JSON 对象')
    translations = []
    for i, original in enumerate(texts):
        raw = parsed.get(str(i + 1))
        obj = {'t': raw} if isinstance(raw, str) else raw if isinstance(raw, dict) else {}
        t = str(obj.get('t') or obj.get('translation') or '').strip()
        if not t or t == original:
            translations.append(None)
            continue
        kind = obj.get('k') or obj.get('kind')
        alt = obj.get('a') or obj.get('alt')
        translations.append({'t': t, 'kind': kind if kind in ('dialogue', 'narration', 'sfx') else 'dialogue',
                             'alt': str(alt).strip() if alt and str(alt).strip() != t else None,
                             'ja_leak': bool(re.search(r'[\u3040-\u30ff]', t))})
    result = {'translations': translations}
    if all(translations):
        db.set_cache(key, result, 7 * 86400)
    return result


def bounds(points):
    if not points:
        return [0, 0, 12, 12]
    xs, ys = zip(*points)
    return [min(xs), min(ys), max(xs), max(ys)]


def parse_paddle(data):
    results = []
    for page in data.get('result', {}).get('ocrResults', []):
        pruned = page.get('prunedResult', page)
        polys = pruned.get('rec_polys', pruned.get('dt_polys', []))
        scores = pruned.get('rec_scores', [])
        for i, text in enumerate(pruned.get('rec_texts', [])):
            if not text.strip():
                continue
            poly = polys[i] if i < len(polys) else []
            results.append({'text': text.strip(), 'confidence': scores[i] if i < len(scores) else 0,
                            'bbox': bounds(poly), 'polygon': poly or None})
    return results


def parse_vision(data):
    response = data.get('responses', [{}])[0]
    if response.get('error'):
        fail(502, 'Google Vision 返回识别错误')
    results = []
    for page in response.get('fullTextAnnotation', {}).get('pages', []):
        for block in page.get('blocks', []):
            text = ''
            for para in block.get('paragraphs', []):
                for word in para.get('words', []):
                    for symbol in word.get('symbols', []):
                        text += symbol.get('text', '')
                        if symbol.get('property', {}).get('detectedBreak', {}).get('type') in ('SPACE', 'EOL_SURE_SPACE'):
                            text += ' '
            if not text.strip():
                continue
            poly = [[v.get('x', 0), v.get('y', 0)] for v in block.get('boundingBox', {}).get('vertices', [])]
            bbox = bounds(poly)
            for index in (0, 1):
                if bbox[index + 2] - bbox[index] < 12:
                    d = (12 - (bbox[index + 2] - bbox[index])) / 2
                    bbox[index] -= d
                    bbox[index + 2] += d
            results.append({'text': text.strip(), 'confidence': block.get('confidence', 0), 'bbox': bbox, 'polygon': poly or None})
    return results


def paddle(image):
    key = credential('PADDLEOCR_API_TOKEN')
    if not key:
        fail(503, 'PaddleOCR 未配置')
    url = 'https://paddleocr.aistudio-app.com/api/v2/ocr/jobs'
    headers = {'Authorization': 'bearer ' + key}
    job = json_request('POST', url, headers=headers, files={'file': ('image.jpg', image, 'image/jpeg')},
                       data={'model': 'PP-OCRv5', 'optionalPayload': json.dumps({'useDocOrientationClassify': False, 'useDocUnwarping': False, 'useTextlineOrientation': True})})
    job_id = str(job['data']['jobId'])
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', job_id):
        fail(502, 'PaddleOCR 任务 ID 不正确')
    for i in range(25):
        time.sleep(2 if i == 0 else 4)
        poll = json_request('GET', url + '/' + job_id, headers=headers)['data']
        if poll['state'] == 'failed':
            fail(502, 'PaddleOCR 识别失败')
        if poll['state'] == 'done':
            content, _ = fetch(poll['resultUrl']['jsonUrl'])
            return [item for line in content.decode().splitlines() if line.strip() for item in parse_paddle(json.loads(line))]
    fail(504, 'PaddleOCR 超时')


def ocr(body):
    b64 = body.get('imageBase64')
    if not isinstance(b64, str) or not b64 or len(b64) > 12 * 1024 * 1024:
        fail(400, 'imageBase64 为空或超过 12MB')
    try:
        image = base64.b64decode(b64, validate=True)
    except ValueError:
        fail(400, '图片 Base64 格式不正确')
    selected = body.get('ocrSource') or config()['defaultOcr']
    if selected not in ('google', 'paddle', 'ocrspace'):
        fail(400, 'OCR 来源不正确')
    key = cache_key('ocr:v2:', [selected, b64])
    cached = db.get_cache(key)
    if cached:
        return dict(cached, cached=True)
    source = 'paddle'
    if selected == 'ocrspace':
        token = credential('OCR_SPACE_KEY')
        if not token:
            fail(503, 'OCR.Space 未配置')
        mime = 'image/png' if image.startswith(b'\x89PNG') else 'image/gif' if image.startswith(b'GIF') else 'image/webp' if image.startswith(b'RIFF') else 'image/jpeg'
        data = json_request('POST', 'https://api.ocr.space/parse/image', headers={'apikey': token}, data={
            'base64Image': f'data:{mime};base64,{b64}', 'language': 'jpn', 'isOverlayRequired': 'true', 'OCREngine': '2', 'detectOrientation': 'true'})
        if data.get('IsErroredOnProcessing'):
            fail(502, 'OCR.Space 识别失败')
        results = []
        for page in data.get('ParsedResults', []):
            if page.get('FileParseExitCode') != 1:
                fail(502, 'OCR.Space 页面识别失败')
            for line in page.get('TextOverlay', {}).get('Lines', []):
                words = line.get('Words', [])
                if words:
                    points = [[w['Left'], w['Top']] for w in words] + [[w['Left'] + w['Width'], w['Top'] + w['Height']] for w in words]
                    results.append({'text': ''.join(w['WordText'] for w in words), 'confidence': .85, 'bbox': bounds(points), 'polygon': None})
        source = 'ocrspace'
    elif selected == 'google' and credential('GOOGLE_VISION_API_KEY') and db.reserve(
            'vision:' + datetime.now(timezone.utc).strftime('%Y-%m'), 1000, 35 * 86400):
        # Reserve BEFORE the request so concurrent requests cannot exceed quota.
        data = json_request('POST', 'https://vision.googleapis.com/v1/images:annotate',
                            params={'key': credential('GOOGLE_VISION_API_KEY')}, json={'requests': [{
                                'image': {'content': b64}, 'features': [{'type': 'DOCUMENT_TEXT_DETECTION'}],
                                'imageContext': {'languageHints': ['ja']}}]})
        results, source = parse_vision(data), 'vision'
    else:
        results = paddle(image)
    result = {'results': results, 'source': source}
    db.set_cache(key, result, 30 * 86400)
    return result
