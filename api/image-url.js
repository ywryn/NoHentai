import { parse } from 'node-html-parser'
import { setCors, handleOptions } from './_cors.js'

function exhentaiCookies() {
  const id = process.env.EXHENTAI_COOKIE_MEMBER_ID
  const hash = process.env.EXHENTAI_COOKIE_PASS_HASH
  const igneous = process.env.EXHENTAI_COOKIE_IGNEOUS
  if (!id || !hash) return null
  let cookie = `ipb_member_id=${id}; ipb_pass_hash=${hash}`
  if (igneous) cookie += `; igneous=${igneous}`
  return cookie
}

function isExhentaiUrl(url) {
  return url.includes('exhentai.org')
}

async function fetchImagePage(pageUrl) {
  const headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml',
  }
  if (isExhentaiUrl(pageUrl)) {
    const cookie = exhentaiCookies()
    if (cookie) headers['Cookie'] = cookie
  }

  const res = await fetch(pageUrl, { headers })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const html = await res.text()

  const root = parse(html)
  const img = root.querySelector('#img')
  if (!img) throw new Error('Image element not found on page')

  const src = img.getAttribute('src')
  if (!src) throw new Error('No src attribute on image element')

  // Also grab the "view original" link if present
  const originalLink = root.querySelector('#loadfail, a[onclick*="nl("]')
  const nlParam = originalLink?.getAttribute('onclick')?.match(/nl\('([^']+)'\)/)?.[1] ?? null

  return { imageUrl: src, nlParam }
}

export default async function handler(req, res) {
  if (handleOptions(req, res)) return
  setCors(req, res)

  const { pageUrl } = req.query
  if (!pageUrl) {
    return res.status(400).json({ error: 'pageUrl is required' })
  }

  try {
    const decoded = decodeURIComponent(pageUrl)
    const { imageUrl, nlParam } = await fetchImagePage(decoded)

    res.setHeader('Cache-Control', 'public, max-age=1800')
    return res.status(200).json({ imageUrl, nlParam })
  } catch (err) {
    return res.status(500).json({ error: err.message })
  }
}
