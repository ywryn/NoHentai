"""Run with: uvicorn backend.main:app --host 127.0.0.1 --port 8000"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from . import admin, db, settings, public, media, translation, security
from cryptography.fernet import Fernet


@asynccontextmanager
async def lifespan(app):
    db.initialize()
    security.password_fingerprint()
    Fernet(settings.encryption_key())
    with db.connect() as con:
        for name in admin.RESOURCES:
            db.resource(con, name)
    yield


app = FastAPI(title='NoHentai', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware, allow_origins=settings.origins(), allow_methods=['GET', 'POST'],
                   allow_headers=['Content-Type'], allow_credentials=False)


@app.middleware('http')
async def protect(request, call_next):
    origin = request.headers.get('origin')
    if request.method == 'POST' and origin and origin not in settings.origins():
        return JSONResponse({'error': '不允许的请求来源'}, status_code=403)
    if request.method == 'POST':
        # Bound chunked bodies too, before parsing JSON or allocating OCR buffers.
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > 16 * 1024 * 1024:
                return JSONResponse({'error': '请求体超过 16MB'}, status_code=413)
            chunks.append(chunk)
        request._body = b''.join(chunks)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse({'error': exc.detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse({'error': '请求参数格式不正确'}, status_code=400)


def safely(fn, *args):
    try:
        return fn(*args)
    except HTTPException:
        raise
    except ValueError as exc:
        # Only our local validation returns input errors. Upstream parsing errors
        # must not echo provider responses or URLs containing keys.
        if fn is admin.handle:
            raise HTTPException(400, str(exc)) from None
        raise HTTPException(502, '上游数据格式异常，请稍后重试') from None
    except Exception:
        raise HTTPException(502, '服务暂时不可用，请检查服务器配置与任务记录') from None


@app.get('/api/health')
def health():
    with db.connect() as con:
        con.execute('SELECT 1')
    return {'ok': True}


@app.post('/api/admin')
def admin_api(request: Request, body: dict = Body(...)):
    return safely(admin.handle, body, request.client.host)


@app.get('/data/{name}')
def data_api(name: str):
    if name not in public.FILES:
        raise HTTPException(404, '数据不存在')
    result = safely(public.dataset, name)
    if name.endswith('.csv'):
        return Response(result, media_type='text/csv', headers={'Cache-Control': 'no-store'})
    return JSONResponse(result, headers={'Cache-Control': 'no-store'})


def limit(request, key, count=60):
    if not db.reserve(key + ':' + request.client.host, count, 60):
        raise HTTPException(429, '请求过多，请稍后重试')


@app.get('/api/gallery-images')
def gallery_api(request: Request, gid: str, token: str):
    limit(request, 'gallery', 30)
    return safely(media.gallery_images, gid, token)


@app.get('/api/image-url')
def image_url_api(request: Request, pageUrl: str):
    limit(request, 'image-url', 180)
    return safely(media.image_url, pageUrl)


@app.get('/api/image-proxy')
def image_proxy_api(request: Request, imageUrl: str):
    limit(request, 'image-proxy', 180)
    content, mime = safely(media.fetch, imageUrl, False, True)
    if not mime.lower().startswith('image/') or mime.split(';')[0].lower() == 'image/svg+xml':
        raise HTTPException(502, '上游未返回位图图片')
    return Response(content, media_type=mime, headers={'Cache-Control': 'private, max-age=3600', 'X-Content-Type-Options': 'nosniff'})


@app.get('/api/jmdict-lookup')
def lookup_api(request: Request, word: str):
    limit(request, 'lookup')
    return safely(media.lookup, word)


def trans_auth(request, body):
    safely(security.trans_auth, body.get('password'), request.client.host)


@app.post('/api/trans-verify')
def verify_api(request: Request, body: dict = Body(...)):
    trans_auth(request, body)
    return {'ok': True}


@app.post('/api/trans-translate')
def translate_api(request: Request, body: dict = Body(...)):
    trans_auth(request, body)
    limit(request, 'translate', 30)
    return safely(translation.translate, body)


@app.post('/api/trans-ocr')
def ocr_api(request: Request, body: dict = Body(...)):
    trans_auth(request, body)
    limit(request, 'ocr', 30)
    return safely(translation.ocr, body)


@app.api_route('/api/printed-books', methods=['GET', 'POST'])
def obsolete():
    raise HTTPException(410, '请使用独立管理后台')
