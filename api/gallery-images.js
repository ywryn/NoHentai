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

  // Get total image count
  const countEl = root.querySelector('#gdd .gdt1')
  let total = 0
  if (countEl) {
    const text = countEl.nextElementSibling?.text || ''
    total = parseInt(text) || 0
  }

  // Fallback: count from page nav
  if (!total) {
    const pager = root.querySelector('#gpc')
    if (pager) {
      const m = pager.text.match(/(\d+)\s+images/)
      if (m) total = parseInt(m[1])
    }
  }

  const images = []
  const gdt = root.querySelectorAll('#gdt .gdtm, #gdt .gdtl')
  for (const cell of gdt) {
    const a = cell.querySelector('a')
    const img = cell.querySelector('img')
    if (!a) continue
    const pageUrl = a.getAttribute('href') || ''
    const thumbUrl = img?.getAttribute('src') || ''
    const pageNumMatch = pageUrl.match(/\/s\/[^/]+\/(\d+)-(\d+)$/)
    const pageNum = pageNumMatch ? parseInt(pageNumMatch[2]) : images.length + 1
    images.push({ pageNum, thumbUrl, pageUrl })
  }

  // Detect next page link
  const nextEl = root.querySelector('a[onclick*="next"], td.ptds a, #unfiltered_image_count')
  // Use paging links
  const pagerLinks = root.querySelectorAll('.ptt td a')
  let lastPageUrl = null
  for (const el of pagerLinks) {
    const href = el.getAttribute('href')
    if (href && href.includes('?p=')) lastPageUrl = href
  }

  return { total, images, lastPageUrl }
}

async function fetchAllPages(baseUrl, cookie) {
  const firstHtml = await fetchPage(`${baseUrl}?nw=always`, cookie)
  if (isSadPanda(firstHtml)) return null

  const firstPage = parseGalleryPage(firstHtml)
  const allImages = [...firstPage.images]
  let total = firstPage.total

  // Determine how many pages there are
  const root = parse(firstHtml)
  const pttCells = root.querySelectorAll('.ptt td')
  const pageNums = []
  for (const td of pttCells) {
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
