import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import handler from '../api/printed-books.js'
import { BOOK_FIELDS, parseBooksCSV, serializeBooksCSV } from '../web-static/src/utils/printedBooks.js'
import { findBookMatches } from '../web-static/src/utils/printedMatching.js'

const csv = readFileSync(new URL('../web-static/public/data/future_digi.csv', import.meta.url), 'utf8')
const books = parseBooksCSV(csv)
const sample = { ID: 'TEST-001', '书名': '测试书目', '收价': '180', '原价': '320', '日文名': 'テスト', sid: '123', '备注': '', cover: '' }
const sha = 'a'.repeat(40)

test('existing CSV including duplicate IDs round-trips without loss', () => {
  assert.deepEqual(parseBooksCSV(serializeBooksCSV(books)), books)
  const duplicates = [{ ...sample, ID: '日版' }, { ...sample, ID: '日版', '书名': '第二部' }]
  assert.deepEqual(parseBooksCSV(serializeBooksCSV(duplicates)), duplicates)
})

test('CSV preserves Unicode, commas, multiline notes, quotes and empty fields', () => {
  const row = { ...sample, '书名': '书名,「日本語」', '备注': '第一行\r\n第二行 "quoted"', cover: '' }
  assert.deepEqual(parseBooksCSV('\uFEFF' + serializeBooksCSV([row])), [row])
  assert.deepEqual(parseBooksCSV(serializeBooksCSV([])), [])
  assert.throws(() => parseBooksCSV('ID,书名\n1,test'), /字段/)
  assert.throws(() => parseBooksCSV(BOOK_FIELDS.join(',') + '\n"broken'), /引号/)
  assert.throws(() => serializeBooksCSV([{ ...sample, sid: 'not-a-number' }]), /数字/)
  assert.throws(() => serializeBooksCSV([{ ...sample, cover: '../secret' }]), /文件名/)
  assert.throws(() => serializeBooksCSV([{ ...sample, '新增字段': 'lost' }]), /未知字段/)
})

const galleries = [
  { gid: 123, title: '[Author] 愛情故事 [Chinese]', title_jpn: '恋の物語', uploader: 'alice', category: 'Manga', tags: ['artist:author'] },
  { gid: 456, title: 'A different book', title_jpn: '', uploader: 'bob', tags: ['artist:someone'] },
]
test('matching supports gallery IDs, URLs, names, book IDs, uploader and tags', () => {
  for (const q of ['123', 'gid:123', 'https://exhentai.org/g/123/abc/', '爱情故事', '恋の物語', 'uploader:alice', 'a:author$']) {
    assert.equal(findBookMatches(galleries, q)[0]?.gallery.gid, 123, q)
  }
  assert.equal(findBookMatches(galleries, 'BED-001', { ID: 'BED-001', '日文名': '恋の物語' })[0]?.gallery.gid, 123)
  assert.deepEqual(findBookMatches(galleries, 'unrelated', { '日文名': '恋の物語' }), [])
  assert.deepEqual(findBookMatches(galleries, ''), [])
  assert.equal(findBookMatches(galleries, '999').length, 0)
})

function response() {
  return {
    headers: {}, code: null, data: null,
    setHeader(name, value) { this.headers[name] = value },
    status(code) { this.code = code; return this },
    json(data) { this.data = data; return this },
    end() { return this },
  }
}

test('API authentication, GitHub persistence, concurrency and error handling', async t => {
  const originalFetch = globalThis.fetch
  const originalPassword = process.env.TRANS_PASSWORD
  const originalToken = process.env.PRINTED_GITHUB_TOKEN
  process.env.TRANS_PASSWORD = 'test-password'
  process.env.PRINTED_GITHUB_TOKEN = 'test-token'
  const calls = []
  let upstream
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options })
    return typeof upstream === 'function' ? upstream() : upstream
  }
  const call = async (body, method = 'POST') => {
    const res = response()
    await handler({ method, headers: { origin: 'https://nohentai.com' }, body }, res)
    return res
  }
  try {
    await t.test('unauthorized direct writes and unsupported methods never reach GitHub', async () => {
      assert.equal((await call({ action: 'save', password: 'wrong' })).code, 401)
      assert.equal((await call({ action: 'load' })).code, 401)
      assert.equal((await call({}, 'GET')).code, 405)
      assert.equal((await call({}, 'OPTIONS')).code, 204)
      assert.equal(calls.length, 0)
    })
    await t.test('missing configuration fails closed', async () => {
      delete process.env.PRINTED_GITHUB_TOKEN
      assert.equal((await call({ action: 'load', password: 'test-password' })).code, 503)
      process.env.PRINTED_GITHUB_TOKEN = 'test-token'
      delete process.env.TRANS_PASSWORD
      assert.equal((await call({ action: 'load', password: '' })).code, 503)
      process.env.TRANS_PASSWORD = 'test-password'
      assert.equal(calls.length, 0)
    })
    await t.test('loads current CSV and SHA from master with no browser caching', async () => {
      upstream = new Response(JSON.stringify({ sha, encoding: 'base64', content: Buffer.from(csv).toString('base64') }))
      const res = await call({ action: 'load', password: 'test-password' })
      assert.equal(res.code, 200); assert.deepEqual(res.data.books, books); assert.equal(res.data.sha, sha)
      assert.equal(res.headers['Cache-Control'], 'no-store')
      assert.equal(res.headers['Access-Control-Allow-Origin'], 'https://nohentai.com')
      assert(calls.at(-1).url.endsWith('?ref=master'))
      assert.equal(calls.at(-1).options.headers.Authorization, 'Bearer test-token')
    })
    await t.test('rejects invalid version or fields before attempting writes', async () => {
      const count = calls.length
      assert.equal((await call({ action: 'save', password: 'test-password', books: [sample] })).code, 400)
      assert.equal((await call({ action: 'save', password: 'test-password', sha, books: [{ ...sample, sid: 'bad' }] })).code, 400)
      assert.equal(calls.length, count)
    })
    await t.test('writes only the fixed CSV with optimistic SHA and a deployable commit', async () => {
      upstream = new Response(JSON.stringify({ content: { sha: 'b'.repeat(40) }, commit: { sha: 'c'.repeat(40) } }))
      const rows = [{ ...sample, '备注': 'Edited, safely' }]
      const res = await call({ action: 'save', password: 'test-password', sha, books: rows })
      assert.equal(res.code, 200)
      const { url, options } = calls.at(-1)
      assert.equal(options.method, 'PUT')
      assert.equal(url, 'https://api.github.com/repos/ywryn/NoHentai/contents/web-static/public/data/future_digi.csv')
      const saved = JSON.parse(options.body)
      assert.equal(saved.sha, sha); assert.equal(saved.branch, 'master'); assert(!saved.message.includes('[skip ci]'))
      assert.deepEqual(parseBooksCSV(Buffer.from(saved.content, 'base64').toString('utf8')), rows)
      assert(!options.body.includes('test-password')); assert(!options.body.includes('test-token'))
    })
    await t.test('conflicts, revoked credentials and transport failures do not report success', async () => {
      for (const status of [409, 422, 401, 403, 404, 500]) {
        upstream = new Response('{}', { status })
        const res = await call({ action: 'save', password: 'test-password', sha, books: [sample] })
        assert.equal(res.code, [409, 422].includes(status) ? 409 : [401, 403, 404].includes(status) ? 503 : 502)
      }
      upstream = () => { throw new Error('secret-bearing upstream error') }
      const res = await call({ action: 'load', password: 'test-password' })
      assert.equal(res.code, 502); assert(!JSON.stringify(res.data).includes('secret-bearing'))
    })
  } finally {
    globalThis.fetch = originalFetch
    for (const [name, value] of [['TRANS_PASSWORD', originalPassword], ['PRINTED_GITHUB_TOKEN', originalToken]]) {
      if (value === undefined) delete process.env[name]
      else process.env[name] = value
    }
  }
})
