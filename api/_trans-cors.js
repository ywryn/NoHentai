const ALLOWED_ORIGINS = [
  'https://nohentai.com',
  'https://www.nohentai.com',
]

export function setTransCors(req, res) {
  const origin = req.headers.origin || ''
  const allowed =
    ALLOWED_ORIGINS.includes(origin) ||
    /^http:\/\/localhost(:\d+)?$/.test(origin)

  if (allowed) {
    res.setHeader('Access-Control-Allow-Origin', origin)
    res.setHeader('Vary', 'Origin')
  }
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type')
}

export function handleTransOptions(req, res) {
  if (req.method === 'OPTIONS') {
    setTransCors(req, res)
    res.status(204).end()
    return true
  }
  return false
}
