import { handleTransOptions, setTransCors } from './_trans-cors.js'

const PADDLEOCR_URL = 'https://u954f2b0w5nbi33b.aistudio-app.com/ocr'

function parseOcrResponse(data) {
  const results = []
  const ocrResults = data?.result?.ocrResults ?? []
  for (const page of ocrResults) {
    const pruned = page.prunedResult ?? page
    const texts = pruned.rec_texts ?? []
    const scores = pruned.rec_scores ?? []
    const polys = pruned.rec_polys ?? pruned.dt_polys ?? []
    for (let i = 0; i < texts.length; i++) {
      const text = texts[i]?.trim()
      if (!text) continue
      const poly = polys[i] ?? []
      const xs = poly.map(p => p[0])
      const ys = poly.map(p => p[1])
      results.push({
        text,
        confidence: scores[i] ?? 0,
        bbox: [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)],
        polygon: poly.length ? poly : null,
      })
    }
  }
  return results
}

export default async function handler(req, res) {
  if (handleTransOptions(req, res)) return
  setTransCors(req, res)

  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' })

  const { password, imageUrl } = req.body || {}

  const expected = process.env.TRANS_PASSWORD
  if (!expected || !password || password !== expected) {
    return res.status(401).json({ error: 'invalid_password' })
  }

  const apiToken = process.env.PADDLEOCR_API_TOKEN
  if (!apiToken) return res.status(500).json({ error: 'PADDLEOCR_API_TOKEN not configured' })

  if (!imageUrl) return res.status(400).json({ error: 'imageUrl is required' })

  try {
    const imgRes = await fetch(imageUrl, {
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' },
    })
    if (!imgRes.ok) throw new Error(`Failed to fetch image: HTTP ${imgRes.status}`)

    const buffer = await imgRes.arrayBuffer()
    const b64 = Buffer.from(buffer).toString('base64')

    const ocrRes = await fetch(PADDLEOCR_URL, {
      method: 'POST',
      headers: {
        'Authorization': `token ${apiToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        file: b64,
        fileType: 1,
        useDocOrientationClassify: false,
        useDocUnwarping: false,
        useTextlineOrientation: false,
        textRecScoreThresh: 0.7,
      }),
    })

    if (!ocrRes.ok) {
      const text = await ocrRes.text()
      throw new Error(`PaddleOCR error ${ocrRes.status}: ${text.slice(0, 200)}`)
    }

    const data = await ocrRes.json()
    const results = parseOcrResponse(data)
    return res.status(200).json({ results })
  } catch (err) {
    return res.status(500).json({ error: err.message })
  }
}
