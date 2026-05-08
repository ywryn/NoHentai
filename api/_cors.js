const ALLOWED_ORIGINS = [
  'https://nohentai.com',
  'https://www.nohentai.com',
]

export function setCors(req, res) {
  const origin = req.headers.origin || ''
  const allowed =
    ALLOWED_ORIGINS.includes(origin) ||
    /^http:\/\/localhost(:\d+)?$/.test(origin)

  if (allowed) {
    res.setHeader('Access-Control-Allow-Origin', origin)
    res.setHeader('Vary', 'Origin')
  }
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type')
}

export function handleOptions(req, res) {
  if (req.method === 'OPTIONS') {
    setCors(req, res)
    res.status(204).end()
    return true
  }
  return false
}
