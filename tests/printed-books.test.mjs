import { readFileSync } from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'
import { BOOK_FIELDS, parseBooksCSV, serializeBooksCSV } from '../web-static/src/utils/printedBooks.js'
import { findBookMatches } from '../web-static/src/utils/printedMatching.js'
const csv = readFileSync(new URL('../web-static/public/data/future_digi.csv', import.meta.url), 'utf8')
const books = parseBooksCSV(csv)
const sample = { ID: 'TEST-001', '书名': '测试书目', '收价': '180', '原价': '320', '日文名': 'テスト', sid: '123', '备注': '', cover: '' }

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
