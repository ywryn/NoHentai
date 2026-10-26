import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, mkdirSync, writeFileSync, symlinkSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { createRequire } from 'node:module'
import { spawnSync } from 'node:child_process'
import sodium from 'libsodium-wrappers'
import handler from '../api/admin.js'
import { RESOURCES, GALLERIES_PATH, validateOverrides, mergeGalleries, validateDaily, validateTranslate } from '../shared/adminData.js'
import { translateConfig } from '../shared/translateConfig.js'
import { serializeBooksCSV } from '../shared/printedBooks.js'
import { createAdminSession, readAdminSession } from '../shared/adminSession.js'

const sha = 'a'.repeat(40), newSha = 'b'.repeat(40), commit = 'c'.repeat(40)
const book = { ID: 'TEST', '书名': '测试', '日文名': '', '收价': '', '原价': '', sid: '123', '备注': '', cover: '' }
const galleries = [{ gid: 123, title: '来源标题', tags: ['artist:test'], category: 'Manga' }]
const daily = JSON.parse(readFileSync(new URL('../config/daily.json', import.meta.url)))
function response() { return { headers: {}, code: null, data: null, setHeader(k, v) { this.headers[k] = v }, status(c) { this.code = c; return this }, json(v) { this.data = v; return this }, end() {} } }
const json = (v, status = 200) => new Response(JSON.stringify(v), { status })
const file = text => json({ encoding: 'base64', content: Buffer.from(text).toString('base64'), sha })

test('Admin and platform helpers can start when bundled as CommonJS serverless functions', () => {
  const require = createRequire(new URL('../web-static/package.json', import.meta.url))
  const ts = require('typescript')
  const root = mkdtempSync(join(tmpdir(), 'admin-commonjs-'))
  try {
    symlinkSync(new URL('../node_modules', import.meta.url).pathname, join(root, 'node_modules'), 'dir')
    for (const path of ['api/admin.js', 'api/_trans-cors.js', 'shared/adminData.js', 'shared/adminGithub.js', 'shared/adminPlatforms.js', 'shared/adminSession.js', 'shared/printedBooks.js']) {
      const compiled = ts.transpileModule(readFileSync(new URL('../' + path, import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true } }).outputText
      mkdirSync(dirname(join(root, path)), { recursive: true })
      writeFileSync(join(root, path), compiled)
    }
    const result = spawnSync(process.execPath, ['--no-experimental-require-module', '-e', `
      const assert = require('node:assert/strict');
      const handler = require(${JSON.stringify(join(root, 'api/admin.js'))}).default;
      const res = { setHeader() {}, status(c) { this.code=c;return this }, end() {} };
      handler({method:'OPTIONS',headers:{origin:'https://nohentai.com'}},res).then(() => assert.equal(res.code,204)).catch(e => {console.error(e);process.exitCode=1});
    `], { encoding: 'utf8' })
    assert.equal(result.status, 0, result.stderr)
  } finally { rmSync(root, { recursive: true, force: true }) }
})

test('remembered sessions expire, reject tampering and are invalidated by password rotation', () => {
  const now = Date.now()
  const session = createAdminSession('test-secret', now)
  assert.deepEqual(readAdminSession(session.token, 'test-secret', now), session)
  assert.equal(readAdminSession(session.token, 'different-secret', now), null)
  assert.equal(readAdminSession(session.token, 'test-secret', session.expiresAt), null)
  assert.equal(readAdminSession(session.token, 'test-secret', now - 1), null)
  const parts = session.token.split('.')
  parts[2] = Buffer.from(JSON.stringify({ expiresAt: session.expiresAt + 100000 })).toString('base64url')
  assert.equal(readAdminSession(parts.join('.'), 'test-secret', now), null)
  assert.equal(readAdminSession(session.token.slice(0, -43) + '中'.repeat(43), 'test-secret', now), null)
  assert.equal(session.token.includes('test-secret'), false)
})

test('source refresh preserves overrides, reset restores source, and empty arrays really clear tags', () => {
  const patches = { 123: { title: '人工标题', tags: [] } }
  assert.equal(mergeGalleries(galleries, patches)[0].title, '人工标题')
  const refreshed = [{ ...galleries[0], title: '来源已更新' }]
  assert.equal(mergeGalleries(refreshed, patches)[0].title, '人工标题')
  assert.equal(mergeGalleries(refreshed, {})[0].title, '来源已更新')
  assert.deepEqual(mergeGalleries(refreshed, patches)[0].tags, [])
  assert.deepEqual(mergeGalleries(galleries, { 123: { hidden: true } }), [])
  assert.equal(mergeGalleries(galleries, { 123: { hidden: true } }, { includeHidden: true }).length, 1)
  assert.throws(() => validateOverrides({ 123: { gid: 456 } }), /不允许/)
  assert.throws(() => validateOverrides(JSON.parse('{"__proto__":{"title":"bad"}}')), /ID/)
  assert.throws(() => mergeGalleries([...galleries, ...galleries], {}), /重复/)
})

test('configuration validation rejects secret leakage, unknown fields and invalid search rules', () => {
  assert.deepEqual(validateDaily(daily), daily)
  for (const patch of [{ cutoffDays: 0 }, { categories: 0 }, { minPages: 900, maxPages: 800 }, { minRating: 1 }, { keyword: 123 }, { apiKey: 'must-not-commit' }]) {
    assert.throws(() => validateDaily([{ ...daily[0], ...patch }]))
  }
  assert.throws(() => validateDaily([daily[0], daily[0]]), /重复/)
  assert.throws(() => validateTranslate({ model: 'test', defaultOcr: 'google', jsonMode: null, apiKey: 'secret' }), /密钥/)
  assert.throws(() => validateTranslate({ model: 'test', defaultOcr: 'unknown', jsonMode: false }), /OCR/)
  const old = process.env.LLM_MODEL
  try { process.env.LLM_MODEL = 'legacy-model'; assert.equal(translateConfig().model, 'legacy-model') }
  finally { if (old === undefined) delete process.env.LLM_MODEL; else process.env.LLM_MODEL = old }
})

test('Admin API authentication, allowlists, file versions, platform changes and error isolation', async t => {
  const fetchBefore = globalThis.fetch
  const names = ['ADMIN_PASSWORD', 'ADMIN_GITHUB_TOKEN', 'PRINTED_GITHUB_TOKEN', 'TRANS_PASSWORD', 'ADMIN_VERCEL_TOKEN', 'ADMIN_VERCEL_PROJECT_ID', 'ADMIN_VERCEL_TEAM_ID']
  const before = Object.fromEntries(names.map(n => [n, process.env[n]]))
  Object.assign(process.env, { ADMIN_PASSWORD: 'admin-test', ADMIN_GITHUB_TOKEN: 'github-test', TRANS_PASSWORD: 'translation-test', ADMIN_VERCEL_TOKEN: 'vercel-test', ADMIN_VERCEL_PROJECT_ID: 'project-test' })
  delete process.env.ADMIN_VERCEL_TEAM_ID
  const calls = []
  let route = () => { throw new Error('Unexpected upstream call') }
  globalThis.fetch = async (url, options) => { calls.push({ url, options }); return route(url, options) }
  async function call(body, { method = 'POST', origin = 'https://nohentai.com' } = {}) {
    const res = response(); await handler({ method, headers: { origin }, body: { password: 'admin-test', ...body } }, res); return res
  }
  const repoFileRoute = (url, options) => {
    if (options.method === 'PUT') return json({ content: { sha: newSha }, commit: { sha: commit } })
    if (url.includes(`/contents/${GALLERIES_PATH}?`)) return file(JSON.stringify(galleries))
    if (url.includes(`/contents/${RESOURCES.overrides}?`)) return file('{}')
    if (url.includes(`/contents/${RESOURCES.printed}?`)) return file(serializeBooksCSV([book]))
    if (url.includes(`/contents/${RESOURCES.daily}?`)) return file(JSON.stringify(daily))
    throw new Error('unexpected path')
  }
  try {
    await t.test('all writes require independent admin auth and permitted browser origins', async () => {
      assert.equal((await call({ action: 'verify', password: 'translation-test' })).code, 401)
      assert.equal((await call({ action: 'verify', password: null })).code, 401)
      assert.equal((await call({ action: 'verify' }, { origin: 'https://evil.example' })).code, 403)
      assert.equal((await call({}, { method: 'GET' })).code, 405)
      assert.equal((await call({}, { method: 'OPTIONS' })).code, 204)
      delete process.env.ADMIN_PASSWORD
      assert.equal((await call({ action: 'verify' })).code, 503)
      process.env.ADMIN_PASSWORD = 'admin-test'
      assert.equal(calls.length, 0)
      const verified = await call({ action: 'verify' })
      assert.equal(verified.code, 200)
      assert.equal(verified.headers['Cache-Control'], 'no-store')
    })
    await t.test('resource and workflow paths cannot be supplied by callers', async () => {
      const count = calls.length
      for (const resource of ['../.env', 'constructor', '__proto__', 'unknown']) assert.equal((await call({ action: 'save', resource, data: {} })).code, 400)
      assert.equal((await call({ action: 'dispatch', workflow: '../other.yml' })).code, 400)
      assert.equal((await call({ action: 'replace-secret', platform: 'vercel', name: 'ADMIN_PASSWORD', value: 'new' })).code, 400)
      assert.equal(calls.length, count)
    })
    await t.test('login issues a reusable credential without returning the password; old sessions fail after rotation', async () => {
      const verified = await call({ action: 'verify' })
      assert.equal(verified.code, 200)
      const session = verified.data.session
      assert(!JSON.stringify(session).includes('admin-test'))
      assert.equal((await call({ action: 'verify', password: session.token })).data.session.token, session.token)
      process.env.ADMIN_PASSWORD = 'rotated-password'
      assert.equal((await call({ action: 'verify', password: session.token })).code, 401)
      process.env.ADMIN_PASSWORD = 'admin-test'
      const expired = createAdminSession('admin-test', Date.now() - 31 * 86400000)
      assert.equal((await call({ action: 'verify', password: expired.token })).code, 401)
    })
    await t.test('large gallery files load via their immutable blob SHA and results are paginated', async () => {
      const many = Array.from({ length: 45 }, (_, i) => ({ ...galleries[0], gid: i + 1 }))
      route = (url, options) => {
        if (url.includes(`/contents/${GALLERIES_PATH}`)) return json({ sha, encoding: 'none', content: '' })
        if (url.endsWith(`/git/blobs/${sha}`)) { assert.equal(options.headers.Accept, 'application/vnd.github.raw+json'); return new Response(JSON.stringify(many)) }
        return file('{"1":{"title":"覆盖","tags":[]}}')
      }
      const result = await call({ action: 'gallery-search', page: 1 })
      assert.equal(result.code, 200)
      assert.equal(result.data.total, 45); assert.equal(result.data.items.length, 30)
      assert.equal(result.data.items[0].gallery.title, '覆盖'); assert.equal(result.data.items[0].source.title, '来源标题')
      assert.equal((await call({ action: 'gallery-search', page: 2 })).data.items.length, 15)
    })
    await t.test('valid saves write only the fixed file, with expected SHA and a deployable commit', async () => {
      route = repoFileRoute
      const loaded = await call({ action: 'load', resource: 'daily' })
      assert.equal(loaded.code, 200); assert.deepEqual(loaded.data.data, daily)
      const result = await call({ action: 'save', resource: 'overrides', sha, data: { 123: { title: '新的标题' } } })
      assert.equal(result.code, 200); assert.equal(result.data.commit, commit)
      const last = calls.at(-1), saved = JSON.parse(last.options.body)
      assert.equal(last.url, `https://api.github.com/repos/ywryn/NoHentai/contents/${RESOURCES.overrides}`)
      assert.equal(saved.sha, sha); assert.equal(saved.branch, 'master'); assert(!saved.message.includes('[skip ci]'))
      assert.deepEqual(JSON.parse(Buffer.from(saved.content, 'base64').toString()), { 123: { title: '新的标题' } })
      assert(!last.options.body.includes('admin-test')); assert(!last.options.body.includes('github-test'))
      assert.equal((await call({ action: 'save', resource: 'overrides', sha, data: { 999: { title: '不存在' } } })).code, 400)
      const count = calls.length
      assert.equal((await call({ action: 'save', resource: 'daily', sha: 'bad', data: daily })).code, 400)
      assert.equal(calls.length, count)
    })
    await t.test('printed accepts valid references and rejects newly introduced missing galleries', async () => {
      route = repoFileRoute
      assert.equal((await call({ action: 'save', resource: 'printed', sha, data: [book] })).code, 200)
      assert.equal((await call({ action: 'save', resource: 'printed', sha, data: [{ ...book, sid: '999' }] })).code, 400)
    })
    await t.test('stale writes, revoked credentials and network failures never report success or expose errors', async () => {
      for (const status of [409, 422, 401, 403, 404, 500]) {
        route = () => json({ error: 'sensitive upstream body' }, status)
        const result = await call({ action: 'save', resource: 'daily', sha, data: daily })
        assert.equal(result.code, [409, 422].includes(status) ? 409 : [401, 403, 404].includes(status) ? 503 : 502)
        assert(!JSON.stringify(result.data).includes('sensitive'))
      }
      route = () => { throw new Error('contains credential') }
      const result = await call({ action: 'load', resource: 'daily' }); assert.equal(result.code, 502); assert(!JSON.stringify(result.data).includes('credential'))
    })
    await t.test('GitHub secret values are encrypted for the repository and never committed as files', async () => {
      await sodium.ready
      const pair = sodium.crypto_box_keypair()
      route = (url, options) => {
        if (url.endsWith('/actions/secrets/public-key')) return json({ key_id: 'test-key', key: sodium.to_base64(pair.publicKey, sodium.base64_variants.ORIGINAL) })
        assert(url.endsWith('/actions/secrets/EXHENTAI_COOKIE_IGNEOUS'))
        const payload = JSON.parse(options.body)
        assert(!options.body.includes('private-cookie'))
        const decoded = sodium.crypto_box_seal_open(sodium.from_base64(payload.encrypted_value, sodium.base64_variants.ORIGINAL), pair.publicKey, pair.privateKey)
        assert.equal(sodium.to_string(decoded), 'private-cookie')
        return new Response(null, { status: 204 })
      }
      const result = await call({ action: 'replace-secret', platform: 'github', name: 'EXHENTAI_COOKIE_IGNEOUS', value: 'private-cookie' })
      assert.equal(result.code, 200); assert(!JSON.stringify(result.data).includes('private-cookie'))
    })
    await t.test('Vercel status strips values; rotation only changes independent production entries', async () => {
      route = url => url.includes('api.vercel.com') ? json({ envs: [{ id: 'env-test', key: 'LLM_API_KEY', value: 'do-not-expose', target: ['production', 'preview'] }] }) : json({ secrets: [] })
      const status = await call({ action: 'platforms' })
      assert.equal(status.code, 200); assert(!JSON.stringify(status.data).includes('do-not-expose'))
      assert.equal((await call({ action: 'replace-secret', platform: 'vercel', name: 'LLM_API_KEY', value: 'new-key' })).code, 409)
      route = (url, options) => {
        if (options.method === 'GET') return json({ envs: [{ id: 'env-test', key: 'LLM_API_KEY', target: ['production'] }] })
        assert(url.endsWith('/env/env-test')); assert.equal(options.method, 'PATCH')
        assert.deepEqual(JSON.parse(options.body).target, ['production'])
        return json({})
      }
      assert.equal((await call({ action: 'replace-secret', platform: 'vercel', name: 'LLM_API_KEY', value: 'new-key' })).code, 200)
    })
    await t.test('Vercel diagnostics distinguish missing configuration, authentication, access and network errors', async () => {
      delete process.env.ADMIN_VERCEL_TOKEN
      route = () => json({ secrets: [] })
      const missing = await call({ action: 'platforms' })
      assert.equal(missing.data.vercel.code, 'not_configured')
      assert.deepEqual(missing.data.vercel.missing, ['ADMIN_VERCEL_TOKEN'])
      assert(missing.data.vercel.error.includes('ADMIN_VERCEL_TOKEN'))
      assert(!missing.data.vercel.error.includes('ADMIN_VERCEL_PROJECT_ID'))
      process.env.ADMIN_VERCEL_TOKEN = 'vercel-test'
      for (const [status, code] of [[401, 'unauthorized'], [403, 'forbidden'], [404, 'project_not_found'], [429, 'rate_limited'], [500, 'upstream_error']]) {
        route = url => url.includes('api.vercel.com') ? json({ error: 'must-not-expose' }, status) : json({ secrets: [] })
        const result = await call({ action: 'platforms' })
        assert.equal(result.code, 200)
        assert.equal(result.data.vercel.available, false)
        assert.equal(result.data.vercel.code, code)
        assert.equal(result.data.github.available, true)
        assert(!JSON.stringify(result.data).includes('must-not-expose'))
      }
      route = url => { if (url.includes('api.vercel.com')) throw new Error('secret upstream text'); return json({ secrets: [] }) }
      const result = await call({ action: 'platforms' })
      assert.equal(result.data.vercel.code, 'unreachable')
      assert(!JSON.stringify(result.data).includes('secret upstream text'))
    })
    await t.test('task dispatch uses fixed workflows and rerun verifies branch and completion', async () => {
      route = (url, options) => {
        if (options.method === 'POST') return new Response(null, { status: 204 })
        return json({ head_branch: 'untrusted', status: 'completed', path: '.github/workflows/sync.yml' })
      }
      assert.equal((await call({ action: 'dispatch', workflow: 'sync.yml' })).code, 200)
      assert.equal((await call({ action: 'rerun', runId: 42 })).code, 400)
    })
    await t.test('health checks only fixed endpoints and never make paid OCR or translation calls', async () => {
      const count = calls.length
      route = (url, options) => new Response('', { status: options.method === 'POST' ? 401 : 200 })
      const result = await call({ action: 'health', url: 'http://169.254.169.254' })
      assert.equal(result.code, 200); assert(result.data.checks.every(c => c.ok))
      assert.equal(calls.length - count, 3)
      assert(calls.slice(count).every(c => !c.url.includes('169.254') && !c.url.includes('trans-ocr') && !c.url.includes('trans-translate')))
    })
  } finally {
    globalThis.fetch = fetchBefore
    for (const [name, value] of Object.entries(before)) { if (value === undefined) delete process.env[name]; else process.env[name] = value }
  }
})
