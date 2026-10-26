import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { createRequire } from 'node:module'
import { spawnSync } from 'node:child_process'
import handler from '../api/printed-books.js'
import { BOOK_FIELDS, parseBooksCSV, serializeBooksCSV } from '../web-static/src/utils/printedBooks.js'
import { findBookMatches } from '../web-static/src/utils/printedMatching.js'

const csv = readFileSync(new URL('../web-static/public/data/future_digi.csv', import.meta.url), 'utf8')
const books = parseBooksCSV(csv)
const sample = { ID: 'TEST-001', '书名': '测试书目', '收价': '180', '原价': '320', '日文名': 'テスト', sid: '123', '备注': '', cover: '' }
const sha = 'a'.repeat(40)

test('backend compiled as CommonJS starts and answers preflight without requiring the frontend ESM package', () => {
  const require = createRequire(new URL('../web-static/package.json', import.meta.url))
  const ts = require('typescript')
  const root = mkdtempSync(join(tmpdir(), 'printed-commonjs-'))
  try {
    for (const path of ['api/printed-books.js', 'api/_trans-cors.js', 'shared/printedBooks.js']) {
      const source = readFileSync(new URL('../' + path, import.meta.url), 'utf8')
      const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText
      const destination = join(root, path)
      mkdirSync(dirname(destination), { recursive: true })
      writeFileSync(destination, compiled)
    }
    const result = spawnSync(process.execPath, ['--no-experimental-require-module', '-e', `
      const assert = require('node:assert/strict');
      const handler = require(${JSON.stringify(join(root, 'api/printed-books.js'))}).default;
      const res = { headers: {}, setHeader(k,v) { this.headers[k]=v }, status(c) { this.code=c;return this }, end() {} };
      handler({method:'OPTIONS', headers:{origin:'https://nohentai.com'}},res).then(() => {
        assert.equal(res.code,204);
        assert.equal(res.headers['Access-Control-Allow-Origin'],'https://nohentai.com');
      }).catch(e => { console.error(e); process.exitCode=1 });
    `], { encoding: 'utf8' })
    assert.equal(result.status, 0, result.stderr)
  } finally { rmSync(root, { recursive: true, force: true }) }
})

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

test('legacy printed API is retired and never accepts translation-password writes', async () => {
  const res = response()
  await handler({ method: 'POST', headers: { origin: 'https://nohentai.com' }, body: { action: 'save', password: 'old-password' } }, res)
  assert.equal(res.code, 410)
  assert.equal(res.headers['Cache-Control'], 'no-store')
})
