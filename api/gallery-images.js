import { parse } from 'node-html-parser'
import { setCors, handleOptions } from './_cors.js'

const EHENTAI = 'https://e-hentai.org'
const EXHENTAI = 'https://exhentai.org'

function exhentaiCookies() {
  const id = process.env.EXHENTAI_COOKIE_MEMBER_ID
  const hash = process.env.EXHENTAI_COOKIE_PASS_HASH
  const igneous = process.env.EXHENTAI_COOKIE_IGNEOUS
  if (!id || !hash) return null
  let cookie = `ipb_member_id=${id}; ipb_pass_hash=${hash}`
  if (igneous) cookie += `; igneous=${igneous}`
  return cookie
}

async function fetchPage(url, cookie) {
  const headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml',
  }
  if (cookie) headers['Cookie'] = cookie
  const res = await fetch(url, { headers })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.text()
}

function isSadPanda(html) {
  return html.includes('sadpanda') || html.includes('Your IP address has been temporarily banned')
}

function parseGalleryPage(html) {
  const root = parse(html)

  // Find "Length:" label, its sibling has "N pages"
  let total = 0
  for (const label of root.querySelectorAll('#gdd .gdt1')) {
    if (label.text.trim() === 'Length:') {
      const m = (label.nextElementSibling?.text || '').match(/(\d+)/)
      if (m) { total = parseInt(m[1]); break }
    }
  }

  // #gdt > a > div[title="Page N: filename"]
  // Thumbnail is sprite: background url(...) -Xpx 0 no-repeat
  const images = []
  const gdt = root.querySelector('#gdt')
  if (gdt) {
    for (const a of gdt.querySelectorAll('a')) {
      const pageUrl = a.getAttribute('href') || ''
      const inner = a.querySelector('div')
      const title = inner?.getAttribute('title') || ''
      const style = inner?.getAttribute('style') || ''

      const pageNumMatch = title.match(/^Page (\d+):/)
      const pageNum = pageNumMatch ? parseInt(pageNumMatch[1]) : images.length + 1

      const bgMatch = style.match(/url\(([^)]+)\)/)
      const thumbSprite = bgMatch ? bgMatch[1] : ''
      const xMatch = style.match(/(-?\d+)px\s+0\s+no-repeat/)
      const thumbX = xMatch ? parseInt(xMatch[1]) : 0
      const wMatch = style.match(/width:(\d+)px/)
      const hMatch = style.match(/height:(\d+)px/)
      const thumbW = wMatch ? parseInt(wMatch[1]) : 200
      const thumbH = hMatch ? parseInt(hMatch[1]) : 283

      images.push({ pageNum, pageUrl, thumbSprite, thumbX, thumbW, thumbH })
    }
  }

  return { total, images }
}

async function fetchAllPages(baseUrl, cookie) {
  const firstHtml = await fetchPage(`${baseUrl}?nw=always`, cookie)
  if (isSadPanda(firstHtml)) return null

  const firstPage = parseGalleryPage(firstHtml)
  const allImages = [...firstPage.images]
  let total = firstPage.total

  // Find total page count from numbered pager cells (.ptt td text = "1","2",...,"N")
  const root = parse(firstHtml)
  const pageNums = []
  for (const td of root.querySelectorAll('.ptt td')) {
    const n = parseInt(td.text.trim())
    if (!isNaN(n)) pageNums.push(n)
  }
  const lastPage = pageNums.length ? Math.max(...pageNums) : 1

  for (let p = 1; p < lastPage; p++) {
    const html = await fetchPage(`${baseUrl}?nw=always&p=${p}`, cookie)
    if (isSadPanda(html)) break
    const { images } = parseGalleryPage(html)
    allImages.push(...images)
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
    const ehUrl = `${EHENTAI}/g/${gid}/${token}/`
    let result = await fetchAllPages(ehUrl, null)

    // Fall back to exhentai with cookies
    if (!result) {
      const cookie = exhentaiCookies()
      if (!cookie) {
        return res.status(403).json({ error: 'Access denied and no exhentai credentials configured' })
      }
      const exUrl = `${EXHENTAI}/g/${gid}/${token}/`
      result = await fetchAllPages(exUrl, cookie)
      if (!result) {
        return res.status(403).json({ error: 'Access denied on both e-hentai and exhentai' })
      }
    }

    res.setHeader('Cache-Control', 'public, max-age=3600')
    return res.status(200).json({ gid, total: result.total, images: result.images })
  } catch (err) {
    return res.status(500).json({ error: err.message })
  }
}
