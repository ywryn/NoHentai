/**
 * 画廊高级搜索：分词、解析、匹配。
 *
 * 此前 Home.vue 与 Printed.vue 各自复制了一份完全相同的实现，
 * 这正是两个页面搜索行为逐渐分叉的根因。统一到这里。
 *
 * 语法：
 *   空格 / 逗号   AND
 *   -term         排除
 *   ~term         OR（任一命中即可）
 *   "exact words" 短语
 *   term*         前缀通配
 *   tag$          标签精确匹配
 *   field:value   字段限定（title / uploader / category / gid / tag）
 *   ns:value      命名空间标签（female / male / artist … 及其缩写）
 */

export const NAMESPACE_ALIASES = {
  f: 'female',
  m: 'male',
  a: 'artist',
  p: 'parody',
  c: 'character',
  l: 'language',
  g: 'group',
  o: 'other',
  cos: 'cosplayer',
  x: 'mixed',
  r: 'reclass',
}

const GALLERY_FIELDS = ['title', 'uploader', 'category', 'gid', 'tag']

/** 供帮助面板展示的语法说明，同时用作可点击的示例 */
export const SEARCH_SYNTAX_HELP = [
  { syntax: 'A B', desc: '同时包含 A 和 B', example: 'schoolgirl uniform' },
  { syntax: '-A', desc: '排除包含 A 的结果', example: '-webtoon' },
  { syntax: '~A ~B', desc: '包含 A 或 B 任一', example: '~vanilla ~romance' },
  { syntax: '"A B"', desc: '按短语精确匹配', example: '"full color"' },
  { syntax: 'A*', desc: '前缀通配', example: 'school*' },
  { syntax: 'tag$', desc: '标签精确匹配（不做包含）', example: 'tag:"sole female$"' },
  { syntax: 'title:', desc: '限定标题，另有 uploader: / category: / gid:', example: 'category:manga' },
  { syntax: 'f: m: a:', desc: '按命名空间搜标签（female/male/artist…）', example: 'a:"asanagi$"' },
]

export const BOOK_FIELDS = ['id', 'name', 'jpname', 'sid']
export const BOOK_SEARCH_FIELDS = [
  { syntax: 'id:', desc: '书目编号', example: 'id:001' },
  { syntax: 'name:', desc: '中文书名', example: 'name:"中文书名"' },
  { syntax: 'jpname:', desc: '日文书名', example: 'jpname:"日本語"' },
  { syntax: 'sid:', desc: '关联画廊 ID', example: 'sid:123456' },
]

export function matchBookTerm(book, gallery, term, expand) {
  if (term.field === 'id') return String(book.ID || '').toLowerCase().includes(term.value)
  if (term.field === 'name') return matchText(book['书名'], term, expand)
  if (term.field === 'jpname') return matchText(book['日文名'], term, expand)
  if (term.field === 'sid') return String(book.sid || '') === term.value
  if (term.field !== 'any') return matchGalleryTerm(gallery, term, expand)
  return [book.ID, book['书名'], book['日文名'], book['备注'], book['收价'], book['原价']].some(value => matchText(value, term, expand)) || matchGalleryTerm(gallery, term, expand)
}

export function galleryLookup(query) {
  const value = query.trim()
  if (/^[0-9]+$/.test(value)) return value
  const match = value.match(/^https?:\/\/(?:e-hentai|exhentai)\.org\/g\/([0-9]+)\/[a-zA-Z0-9]+\/?(?:[?#].*)?$/i)
  return match ? match[1] : null
}

export function tokenizeQuery(query) {
  const tokens = []
  let buffer = '', inQuote = false, wasQuoted = false, start = -1
  function push(end) {
    if (buffer) tokens.push({ text: buffer, quoted: wasQuoted, start, end, raw: query.slice(start, end) })
    buffer = ''; wasQuoted = false; start = -1
  }
  for (let i = 0; i < query.length; i++) {
    const ch = query[i]
    if (!inQuote && (ch === ' ' || ch === ',')) { push(i); continue }
    if (start < 0) start = i
    if (ch === '"') { inQuote = !inQuote; wasQuoted = true }
    else buffer += ch
  }
  push(query.length)
  return tokens
}

export function removeQueryTerm(query, term) {
  if (query.slice(term.start, term.end) !== term.raw) return query
  return (query.slice(0, term.start) + query.slice(term.end)).replace(/^[ ,]+|[ ,]+$/g, '').trim()
}

/**
 * @param {string} query
 * @param {string[]} extraFields 页面专有字段（如 Printed 的 id/name/jpname/sid）
 */
export function parseQuery(query, extraFields = []) {
  const include = []
  const exclude = []
  const orTerms = []
  const lookup = extraFields.length ? null : galleryLookup(query)

  for (const token of tokenizeQuery(query)) {
    let raw = token.text.trim()
    if (!raw) continue

    let mode = 'include'
    if (raw.startsWith('-')) {
      mode = 'exclude'
      raw = raw.slice(1)
    } else if (raw.startsWith('~')) {
      mode = 'or'
      raw = raw.slice(1)
    }

    raw = raw.replace(/_/g, ' ').trim()
    if (!raw) continue

    let exactTag = false
    if (raw.endsWith('$')) {
      exactTag = true
      raw = raw.slice(0, -1)
    }

    let wildcard = false
    if (raw.endsWith('*') || raw.endsWith('%')) {
      wildcard = true
      raw = raw.slice(0, -1)
    }

    let field = 'any'
    let namespace = null
    let value = raw

    if (raw.includes(':')) {
      const [prefixRaw, rest] = raw.split(':', 2)
      const prefix = prefixRaw.toLowerCase()
      if (GALLERY_FIELDS.includes(prefix) || extraFields.includes(prefix)) {
        field = prefix
        value = rest || ''
      } else {
        field = 'tag'
        namespace = NAMESPACE_ALIASES[prefix] || prefix
        value = rest || ''
      }
    }

    if (lookup !== null) { field = 'gid'; namespace = null; value = lookup }
    value = value.trim().toLowerCase()
    if (!value) continue

    const term = {
      field,
      value,
      wildcard,
      exactTag,
      namespace,
      quoted: token.quoted,
      mode,
      /** 原始 token，供「当前筛选条件」chip 回显与移除 */
      raw: token.raw,
      start: token.start,
      end: token.end,
    }
    if (mode === 'exclude') exclude.push(term)
    else if (mode === 'or') orTerms.push(term)
    else include.push(term)
  }

  return { include, exclude, orTerms }
}

/** 所有条件按出现顺序摊平，供 UI 回显 */
export function parsedTerms(parsed) {
  return [...parsed.include, ...parsed.orTerms, ...parsed.exclude]
}

/**
 * @param {string} text
 * @param {object} term
 * @param {(v: string) => string} [expand] 额外的等价写法（如简→繁）
 */
export function matchText(text, term, expand) {
  if (!text) return false
  const target = String(text).toLowerCase()
  const hit = value => {
    if (!value) return false
    return term.wildcard ? target.startsWith(value) : target.includes(value)
  }
  if (hit(term.value)) return true
  if (!expand) return false
  const alt = expand(term.value)
  return alt !== term.value && hit(alt)
}

export function matchTagList(tags, term) {
  if (!Array.isArray(tags)) return false
  for (const tag of tags) {
    if (typeof tag !== 'string') continue
    const tagLower = tag.toLowerCase()
    if (term.namespace) {
      if (!tagLower.startsWith(`${term.namespace}:`)) continue
      const tagValue = tagLower.slice(term.namespace.length + 1)
      if (term.exactTag) {
        if (tagValue === term.value) return true
      } else if (term.wildcard) {
        if (tagValue.startsWith(term.value)) return true
      } else if (tagValue.includes(term.value)) return true
    } else {
      const tagValue = tagLower.includes(':') ? tagLower.split(':', 2)[1] : tagLower
      if (term.exactTag) {
        if (tagValue === term.value) return true
      } else if (term.wildcard) {
        if (tagValue.startsWith(term.value)) return true
      } else if (tagLower.includes(term.value)) return true
    }
  }
  return false
}

/** 标准画廊对象的单条件匹配 */
export function matchGalleryTerm(item, term, expand) {
  if (!item) return false
  if (term.field === 'gid') return String(item.gid || '') === term.value
  if (term.field === 'title') {
    return matchText(item.title, term, expand) || matchText(item.title_jpn, term, expand)
  }
  if (term.field === 'uploader') return matchText(item.uploader, term, expand)
  if (term.field === 'category') return matchText(item.category, term, expand)
  if (term.field === 'tag') return matchTagList(item.tags, term)
  return (
    matchText(item.title, term, expand) ||
    matchText(item.title_jpn, term, expand) ||
    matchText(item.uploader, term, expand) ||
    matchText(item.category, term, expand) ||
    matchTagList(item.tags, term)
  )
}

/** 用 include / exclude / or 三组条件裁决单个条目 */
export function passesQuery(item, parsed, matcher) {
  if (!parsed.include.every(term => matcher(item, term))) return false
  if (parsed.exclude.some(term => matcher(item, term))) return false
  if (parsed.orTerms.length > 0 && !parsed.orTerms.some(term => matcher(item, term))) return false
  return true
}

/** 输入过程中光标所在的那个 token（用于标签联想） */
export function activeToken(query, caret = query.length) {
  const position = Math.max(0, Math.min(query.length, caret))
  const token = tokenizeQuery(query).find(item => item.start <= position && position <= item.end)
  return token ? { text: token.raw, start: token.start, end: token.end } : { text: '', start: position, end: position }
}

/** Replace only the token at the caret; keep all following conditions intact. */
export function applySuggestion(query, suggestion, caret = query.length) {
  const { start, end } = activeToken(query, caret)
  const replacement = `${suggestion.namespace}:"${suggestion.value}$"`
  const suffix = query.slice(end)
  return `${query.slice(0, start)}${replacement}${suffix || ' '}`
}

/** 从 translations.json 里按输入前缀打分排序，取前 N 条 */
export function suggestTags(token, translations, limit = 8) {
  const normalizedToken = token.trim().toLowerCase()
  if (!normalizedToken || !translations || normalizedToken.length < 2) return []
  if (normalizedToken.includes('$') || normalizedToken.startsWith('-') || normalizedToken.startsWith('~')) {
    return []
  }

  const needle = (
    normalizedToken.includes(':') ? normalizedToken.split(':', 2)[1] : normalizedToken
  ).replace(/^"|"$/g, '')
  if (!needle) return []

  const prefix = normalizedToken.includes(':') ? normalizedToken.split(':', 1)[0] : null
  if (prefix && GALLERY_FIELDS.includes(prefix) && prefix !== 'tag') return []
  const requestedNamespace = prefix && prefix !== 'tag' ? (NAMESPACE_ALIASES[prefix] || prefix) : null
  const out = []
  for (const entry of translations) {
    const namespace = entry.namespace
    const nsLower = namespace.toLowerCase()
    if (requestedNamespace && nsLower !== requestedNamespace) continue
    for (const [value, detail] of Object.entries(entry.data || {})) {
      const valueLower = value.toLowerCase()
      const cnLower = (detail?.name || '').toLowerCase()
      const score =
        valueLower === needle ? 0
        : valueLower.startsWith(needle) ? 1
        : cnLower.startsWith(needle) ? 2
        : nsLower.startsWith(needle) ? 3
        : valueLower.includes(needle) ? 4
        : cnLower.includes(needle) ? 5
        : -1
      if (score === -1) continue
      out.push({ tag: `${namespace}:${value}`, namespace, value, tag_cn: detail?.name || '', score })
    }
  }

  return out
    .sort(
      (a, b) =>
        a.score - b.score ||
        a.namespace.localeCompare(b.namespace) ||
        a.value.localeCompare(b.value)
    )
    .slice(0, limit)
}
