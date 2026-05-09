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

export default async function handler(req, res) {
  if (handleOptions(req, res)) return
  setCors(req, res)

  const { imageUrl } = req.query
  if (!imageUrl) return res.status(400).json({ error: 'imageUrl is required' })

  const decoded = decodeURIComponent(imageUrl)

  const headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'image/webp,image/avif,image/*,*/*',
    'Referer': 'https://e-hentai.org/',
  }
  if (decoded.includes('exhentai.org') || decoded.includes('hath.network')) {
    const cookie = exhentaiCookies()
    if (cookie) headers['Cookie'] = cookie
  }

  const upstream = await fetch(decoded, { headers })
  if (!upstream.ok) {
    return res.status(upstream.status).json({ error: `upstream ${upstream.status}` })
  }

  const contentType = upstream.headers.get('content-type') || 'image/jpeg'
  const cacheControl = upstream.headers.get('cache-control') || 'public, max-age=3600'

  res.setHeader('Content-Type', contentType)
  res.setHeader('Cache-Control', cacheControl)
  res.setHeader('X-Content-Type-Options', 'nosniff')

  const buf = await upstream.arrayBuffer()
  res.status(200).send(Buffer.from(buf))
}
