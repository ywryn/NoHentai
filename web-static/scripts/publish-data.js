import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFileSync } from 'node:child_process'
import { mergeGalleries, validateDaily, validateTranslate, validateReferences } from '../../shared/adminData.js'
import { parseBooksCSV } from '../../shared/printedBooks.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = name => JSON.parse(fs.readFileSync(path.join(root, name), 'utf8'))
const source = read('web-static/public/data/galleries.json')
const overrides = read('web-static/public/data/gallery-overrides.json')
validateDaily(read('config/daily.json'))
validateTranslate(read('config/translate.json'))
const galleries = mergeGalleries(source, overrides)
const books = parseBooksCSV(fs.readFileSync(path.join(root, 'web-static/public/data/future_digi.csv'), 'utf8'))
const missing = validateReferences(books, source)
if (missing.length) console.warn(`保留 ${missing.length} 条已有的站外 printed 关联；Admin 保存时会校验新增关联。`)
const output = path.join(root, 'web-static/dist/data')
fs.mkdirSync(output, { recursive: true })
const write = (name, value) => fs.writeFileSync(path.join(output, name), JSON.stringify(value))
write('galleries.json', galleries)
const daily = read('web-static/public/data/daily_search.json')
write('daily_search.json', daily.map(g => ({ ...g, galleries: mergeGalleries(g.galleries, overrides) })))
write('translate-config.json', { defaultOcr: read('config/translate.json').defaultOcr })
let commit = process.env.GITHUB_SHA || ''
try { commit = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim() } catch {}
write('release.json', { commit, builtAt: new Date().toISOString() })
// The frontend needs only merged data. Do not ship a second copy of overrides.
fs.rmSync(path.join(output, 'gallery-overrides.json'), { force: true })
console.log(`发布数据已生成：${galleries.length} 个画廊，源文件未修改。`)
