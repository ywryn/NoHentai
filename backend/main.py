"""Run with: uvicorn backend.main:app --host 127.0.0.1 --port 8000"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Body, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from . import admin, db, settings, public, media, translation, security, catalog, services, media_store, operations, stats, observability
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
                   allow_headers=['Content-Type', 'X-CSRF-Token'], allow_credentials=False)


@app.middleware('http')
async def protect(request, call_next):
    request_id, marker = observability.bind_request()
    try:
        origin = request.headers.get('origin')
        if request.method == 'POST' and origin and origin not in settings.origins():
            response = JSONResponse({'error': '不允许的请求来源'}, status_code=403)
        elif request.method == 'POST':
            # Bound chunked bodies too, before parsing JSON or allocating OCR buffers.
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 16 * 1024 * 1024:
                    response = JSONResponse({'error': '请求体超过 16MB'}, status_code=413)
                    break
                chunks.append(chunk)
            else:
                request._body = b''.join(chunks)
                response = await call_next(request)
        else:
            response = await call_next(request)
        response.headers['X-Request-ID'] = request_id
        response.headers['X-Content-Type-Options'] = 'nosniff'
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response
    finally:
        observability.reset_request(marker)


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
        observability.log_failure(getattr(fn, '__name__', type(fn).__name__), exc)
        raise HTTPException(502, '上游数据格式异常，请稍后重试') from None
    except Exception as exc:
        observability.log_failure(getattr(fn, '__name__', type(fn).__name__), exc)
        raise HTTPException(502, '服务暂时不可用，请检查服务器配置与任务记录') from None


@app.get('/api/health')
def health():
    with db.connect() as con:
        con.execute('SELECT 1')
    return {'ok': True}


@app.get('/api/admin/session')
def current_session(request: Request):
    session = security.session(request.cookies.get(security.COOKIE))
    return {'ok': True, 'session': {k: session[k] for k in ('expiresAt', 'csrf')}}


@app.post('/api/admin')
def admin_api(request: Request, body: dict = Body(...)):
    body = dict(body)
    cookie_mode = body.get('mode') == 'cookie' or not body.get('password')
    if body.get('action') == 'verify' and body.get('mode') == 'cookie':
        session = safely(security.login, body.get('password'), request.client.host, body.get('remember') is True, request.headers.get('user-agent', ''))
        response = JSONResponse({'ok': True, 'session': {k: session[k] for k in ('expiresAt', 'csrf')}})
        response.set_cookie(security.COOKIE, session['token'], httponly=True, secure=request.url.scheme == 'https',
                            samesite='strict', path='/api', max_age=30*86400 if body.get('remember') is True else None)
        return response
    if not body.get('password'):
        token = request.cookies.get(security.COOKIE)
        session = security.session(token)
        if not request.headers.get('x-csrf-token') or not security.hmac.compare_digest(request.headers['x-csrf-token'], session['csrf']):
            raise HTTPException(403, '会话验证失败，请刷新页面重试')
        body['password'] = token
    result = safely(admin.handle, body, request.client.host)
    response = JSONResponse(result)
    if cookie_mode and (body.get('action') in ('logout', 'logout-all', 'change-password') or result.get('relogin')):
        response.delete_cookie(security.COOKIE, path='/api', httponly=True, secure=request.url.scheme == 'https', samesite='strict')
    return response


@app.get('/api/admin/backups/{name}')
def download_backup(request: Request, name: str):
    security.session(request.cookies.get(security.COOKIE))
    return FileResponse(operations.backup_file(name), filename=name, media_type='application/octet-stream', headers={'Cache-Control': 'no-store'})


@app.get('/media/{filename}')
def cover_file(filename: str):
    return FileResponse(media_store.find(filename), media_type='image/webp', headers={'Cache-Control': 'public, max-age=31536000, immutable'})


@app.get('/api/revision')
def revision():
    with db.connect() as con:
        return {'catalog': db.snapshot(con, 'catalog-revision'), 'content': db.snapshot(con, 'release', {}).get('commit')}


@app.get('/api/daily')
def daily_api():
    return safely(public.daily)


@app.get('/api/tags')
def tag_page_api(namespace: str = Query('all', max_length=100), q: str = Query('', max_length=200), page: int = Query(1, ge=1, le=100000)):
    return safely(catalog.tags_page, namespace, q, page)


@app.get('/api/stats')
def statistics_api():
    return safely(stats.current)


@app.get('/api/books')
def books_api():
    return safely(public.books)


@app.get('/api/galleries')
def catalog_api(q: str = Query('', max_length=2000), types: str = Query('', max_length=1000),
                page: int = Query(1, ge=1, le=100000), per_page: int = Query(30, ge=1, le=100)):
    return safely(catalog.list_galleries, q, types, page, per_page)


@app.get('/api/galleries/{gid}')
def detail_api(gid: str, source: str = Query('favorites', pattern='^(favorites|daily)$')):
    return safely(catalog.gallery_detail, gid, source)


@app.get('/api/tags/suggestions')
def suggestions_api(token: str = Query('', max_length=2000)):
    return safely(catalog.suggest_tags, token)


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
def image_url_api(request: Request, pageUrl: str, refresh: bool = False):
    limit(request, 'image-url', 180)
    if refresh:
        limit(request, 'image-refresh', 30)
    return safely(media.image_url, pageUrl, refresh)


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
    with services.slot('translate'):
        return safely(translation.translate, body)


@app.post('/api/trans-ocr')
def ocr_api(request: Request, body: dict = Body(...)):
    trans_auth(request, body)
    limit(request, 'ocr', 30)
    with services.slot('ocr'):
        return safely(translation.ocr, body)


@app.api_route('/api/printed-books', methods=['GET', 'POST'])
def obsolete():
    raise HTTPException(410, '请使用独立管理后台')
