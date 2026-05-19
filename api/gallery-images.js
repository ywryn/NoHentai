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
    'Accept-Language': 'en-US,en;q=0.9',
  }
  if (cookie) headers['Cookie'] = cookie
  const res = await fetch(url, { headers, redirect: 'follow' })
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const html = await res.text()
  return { html }
}

// Returns true when the HTML is not a real gallery page (access denied in any form)
function isAccessDenied(html) {
  if (html.includes('sadpanda')) return true
  if (html.includes('Your IP address has been temporarily banned')) return true
  if (html.includes('This gallery has been removed')) return true
  // No image grid = not a valid gallery page (covers all other denial variants)
  if (!html.includes('id="gdt"')) return true
  return false
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

      // Skip non-image page URLs (navigation links, etc.)
      const globalPageMatch = pageUrl.match(/\d+-(\d+)\/?$/)
      if (!globalPageMatch) continue
      const pageNum = parseInt(globalPageMatch[1])

      let thumbSprite = '', thumbX = 0, thumbW = 100, thumbH = 142

      // Prefer the div that actually contains the sprite background (handles nested wrappers)
      const spriteDiv = a.querySelector('div[style*="url("]') || a.querySelector('div')
      if (spriteDiv) {
        const style = spriteDiv.getAttribute('style') || ''
        const bgMatch = style.match(/url\(([^)]+)\)/)
        if (bgMatch) {
          thumbSprite = bgMatch[1].replace(/['"]/g, '')
          // Handle variants: "-Xpx 0 no-repeat", "-Xpx 0px no-repeat", "no-repeat -Xpx 0(px)"
          const xMatch = style.match(/(-?\d+)px\s+0(?:px)?\s+no-repeat/)
              || style.match(/no-repeat\s+(-?\d+)px/)
          thumbX = xMatch ? parseInt(xMatch[1]) : 0
          const wMatch = style.match(/width:(\d+)px/)
          const hMatch = style.match(/height:(\d+)px/)
          thumbW = wMatch ? parseInt(wMatch[1]) : 100
          thumbH = hMatch ? parseInt(hMatch[1]) : 142
        }
      }

      // Fallback: gdtl mode uses <img> instead of a sprite div
      if (!thumbSprite) {
        const img = a.querySelector('img')
        if (img) {
          thumbSprite = img.getAttribute('src') || ''
          thumbX = 0
          const imgStyle = img.getAttribute('style') || ''
          const wMatch = imgStyle.match(/width:(\d+)px/)
          const hMatch = imgStyle.match(/height:(\d+)px/)
          thumbW = wMatch ? parseInt(wMatch[1]) : 100
          thumbH = hMatch ? parseInt(hMatch[1]) : 142
        }
      }

      images.push({ pageNum, pageUrl, thumbSprite, thumbX, thumbW, thumbH })
    }
  }

  return { total, images }
}

async function fetchAllPages(baseUrl, cookie) {
  const first = await fetchPage(`${baseUrl}?nw=always`, cookie)
  if (first === null || isAccessDenied(first.html)) return null

  const firstHtml = first.html
  const firstPage = parseGalleryPage(firstHtml)
  const allImages = [...firstPage.images]
  let total = firstPage.total

  const root = parse(firstHtml)
  const pageNums = []
  for (const td of root.querySelectorAll('.ptt td')) {
    const n = parseInt(td.text.trim())
    if (!isNaN(n)) pageNums.push(n)
  }
  const lastPage = pageNums.length ? Math.max(...pageNums) : 1

  for (let p = 1; p < lastPage; p++) {
    const page = await fetchPage(`${baseUrl}?p=${p}`, cookie)
    if (page === null || isAccessDenied(page.html)) break
    const { images } = parseGalleryPage(page.html)
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
    let source = 'e-hentai'

    // Fall back to exhentai with cookies
    if (!result) {
      const cookie = exhentaiCookies()
      if (!cookie) {
        return res.status(403).json({ error: 'exhentai_blocked', message: 'ExHentai-exclusive gallery: no credentials configured' })
      }
      const exUrl = `${EXHENTAI}/g/${gid}/${token}/`
      result = await fetchAllPages(exUrl, cookie)
      if (!result) {
        return res.status(403).json({ error: 'exhentai_blocked', message: 'ExHentai-exclusive gallery: access denied' })
      }
      source = 'exhentai'
    }

    const images = result.total > 0 ? result.images.slice(0, result.total) : result.images
    res.setHeader('Cache-Control', 'private, max-age=3600')
    return res.status(200).json({ gid, total: result.total, images, source })
  } catch (err) {
    return res.status(500).json({ error: err.message })
  }
}
