export const BOOK_FIELDS = ['ID', '书名', '收价', '原价', '日文名', 'sid', '备注', 'cover']

export function parseBooksCSV(text) {
  const rows = []
  let row = [], value = '', quoted = false
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (ch === '"') {
      if (quoted && text[i + 1] === '"') { value += '"'; i++ }
      else quoted = !quoted
    } else if (!quoted && ch === ',') { row.push(value); value = '' }
    else if (!quoted && (ch === '\r' || ch === '\n')) {
      if (row.length || value) rows.push([...row, value])
      row = []; value = ''
      if (ch === '\r' && text[i + 1] === '\n') i++
    } else value += ch
  }
  if (quoted) throw new Error('CSV 引号未闭合')
  if (row.length || value) rows.push([...row, value])
  if (!rows.length) throw new Error('书单数据为空')
  const headers = rows.shift().map((h, i) => i === 0 ? h.replace(/^\uFEFF/, '') : h)
  if (headers.length !== BOOK_FIELDS.length || BOOK_FIELDS.some(f => !headers.includes(f))) {
    throw new Error('书单字段不符合预期，请检查 CSV 表头')
  }
  return rows.map((r, i) => {
    if (r.length !== headers.length) throw new Error(`CSV 第 ${i + 2} 行字段数量不正确`)
    return Object.fromEntries(headers.map((h, j) => [h, r[j]]))
  })
}

export function validateBooks(books) {
  if (!Array.isArray(books) || books.length > 10000) throw new Error('书单格式不正确或条目过多')
  return books.map((book, index) => {
    if (!book || typeof book !== 'object' || Array.isArray(book)) throw new Error(`第 ${index + 1} 条书目格式不正确`)
    if (Object.keys(book).some(k => !BOOK_FIELDS.includes(k))) throw new Error(`第 ${index + 1} 条书目包含未知字段`)
    const result = Object.fromEntries(BOOK_FIELDS.map(field => {
      const value = book[field] ?? ''
      if (typeof value !== 'string' || value.length > 5000 || value.includes('\0')) throw new Error(`第 ${index + 1} 条书目的 ${field} 不合法`)
      return [field, value]
    }))
    result.ID = result.ID.trim()
    result.sid = result.sid.trim()
    if (!result.ID) throw new Error(`第 ${index + 1} 条书目缺少 ID`)
    if (!result['书名'].trim() && !result['日文名'].trim()) throw new Error(`书目 ${result.ID} 缺少书名`)
    if (result.sid && !/^\d+$/.test(result.sid)) throw new Error(`书目 ${result.ID} 的关联画廊 ID 必须是数字`)
    if (result.cover && (/[/\\]/.test(result.cover) || result.cover === '.' || result.cover === '..')) throw new Error(`书目 ${result.ID} 的封面应为文件名`)
    return result
  })
}

export function serializeBooksCSV(books) {
  const escape = value => /[",\r\n]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value
  return [BOOK_FIELDS.join(','), ...validateBooks(books).map(book => BOOK_FIELDS.map(f => escape(book[f])).join(','))].join('\r\n') + '\r\n'
}
