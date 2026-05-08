import { setCors, handleOptions } from './_cors.js'

const EHENTAI  = 'https://e-hentai.org'
const EXHENTAI = 'https://exhentai.org'

function exhentaiCookies() {
  const id      = process.env.EXHENTAI_COOKIE_MEMBER_ID
  const hash    = process.env.EXHENTAI_COOKIE_PASS_HASH
  const igneous = process.env.EXHENTAI_COOKIE_IGNEOUS
  if (!id || !hash) return null
  let cookie = `ipb_member_id=${id}; ipb_pass_hash=${hash}`
  if (igneous) cookie += `; igneous=${igneous}`
  return cookie
}

function makeHeaders(cookie, base) {
  const h = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': `${base}/`,
  }
  if (cookie) h['Cookie'] = cookie
  return h
}

async function fetchPage(url, cookie) {
  const base = url.startsWith('https://exhentai') ? EXHENTAI : EHENTAI
  const res = await fetch(url, { headers: makeHeaders(cookie, base) })
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.text()
}

function isAccessDenied(html) {
  if (!html || html.length < 100) return true
  if (html.includes('sadpanda')) return true
  if (html.includes('Your IP address has been temporarily banned')) return true
  if (html.includes('This gallery has been removed')) return true
  if (!html.includes('id="gdt"')) return true
  return false
}

function parseTotalPages(html) {
  const m = html.match(/class="gdt2">(\d+)\s+pages?</i)
  return m ? parseInt(m[1], 10) : 0
}

function parseImages(html) {
  const images = []
  // matches: href=".../s/{ptoken}/{gid}-{pageNum}"><div title="Page N: ..." style="width:Wpx;height:Hpx;background:...url(SPRITE) -Xpx 0 no-repeat
  const re = /href="([^"]+\/s\/([0-9a-f]+)\/(\d+)-(\d+))"[^>]*><div[^>]*title="Page (\d+):[^"]*"[^>]*style="[^"]*width:(\d+)px[^"]*height:(\d+)px[^"]*url\(([^)]+)\)[^"]*?(-?\d+)px\s+0\s+no-repeat/g
  let m
  while ((m = re.exec(html)) !== null) {
    const [, pageUrl, , , , pageNum, thumbW, thumbH, thumbSprite, thumbX] = m
    images.push({
      pageNum:     parseInt(pageNum, 10),
      pageUrl,
      thumbSprite,
      thumbX:      parseInt(thumbX, 10),
      thumbW:      parseInt(thumbW, 10),
      thumbH:      parseInt(thumbH, 10),
    })
  }
  return images
}

function getLastPage(html) {
  const pttBlock = (html.match(/class="ptt"[\s\S]*?<\/table>/) || [''])[0]
  const nums = []
  const re = />(\d+)<\//g
  let m
  while ((m = re.exec(pttBlock)) !== null) {
    nums.push(parseInt(m[1], 10))
  }
  return nums.length ? Math.max(...nums) : 1
}

async function fetchAllPages(baseUrl, cookie) {
  const firstHtml = await fetchPage(baseUrl, cookie)
  if (firstHtml === null || isAccessDenied(firstHtml)) return null

  const total     = parseTotalPages(firstHtml)
  const allImages = parseImages(firstHtml)
  const lastPage  = getLastPage(firstHtml)

  for (let p = 1; p < lastPage; p++) {
    const html = await fetchPage(`${baseUrl}?p=${p}`, cookie)
    if (html === null || isAccessDenied(html)) break
    allImages.push(...parseImages(html))
  }

  return { total: total || allImages.length, images: allImages }
}

export default async function handler(req, res) {
  if (handleOptions(req, res)) return
  setCors(req, res)

  const { gid, token } = req.query
  if (!gid || !token) {
    return res.status(400).json({ error: 'gid and token are required' })
  }

  try {
    // Try e-hentai first (no cookies)
    let result = await fetchAllPages(`${EHENTAI}/g/${gid}/${token}/`, null)

    // Fall back to exhentai with cookies
    if (!result) {
      const cookie = exhentaiCookies()
      if (!cookie) {
        return res.status(403).json({ error: 'exhentai_blocked', message: 'ExHentai-exclusive gallery: no credentials configured' })
      }
      result = await fetchAllPages(`${EXHENTAI}/g/${gid}/${token}/`, cookie)
      if (!result) {
        return res.status(403).json({ error: 'exhentai_blocked', message: 'ExHentai-exclusive gallery: access denied' })
      }
    }

    const images = result.total > 0 ? result.images.slice(0, result.total) : result.images
    res.setHeader('Cache-Control', 'public, max-age=3600')
    return res.status(200).json({ gid, total: result.total, images })
  } catch (err) {
    return res.status(500).json({ error: err.message })
  }
}
