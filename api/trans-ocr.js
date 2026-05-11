import { handleTransOptions, setTransCors } from './_trans-cors.js'
import { Redis } from '@upstash/redis'

const PADDLEOCR_JOB_URL = 'https://paddleocr.aistudio-app.com/api/v2/ocr/jobs'
const PADDLE_MODEL = 'PP-OCRv5'
const VISION_MONTHLY_LIMIT = 1000

function getRedis() {
  const url = process.env.KV_REST_API_URL
  const token = process.env.KV_REST_API_TOKEN
  if (!url || !token) return null
  return new Redis({ url, token })
}

function monthKey() {
  return `vision_ocr_count_${new Date().toISOString().slice(0, 7)}`
}

async function getAndIncrVisionCount(redis) {
  if (!redis) return VISION_MONTHLY_LIMIT
  const key = monthKey()
  const count = await redis.incr(key)
  if (count === 1) await redis.expire(key, 35 * 24 * 3600)
  return count
}

function parsePaddleResponse(data) {
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

function parseVisionResponse(data) {
  const results = []
  const pages = data?.responses?.[0]?.fullTextAnnotation?.pages ?? []
  for (const page of pages) {
    for (const block of page.blocks ?? []) {
      let text = ''
      for (const para of block.paragraphs ?? []) {
        for (const word of para.words ?? []) {
          for (const symbol of word.symbols ?? []) {
            text += symbol.text
            const breakType = symbol.property?.detectedBreak?.type
            if (breakType === 'SPACE' || breakType === 'EOL_SURE_SPACE') text += ' '
          }
        }
      }
      text = text.trim()
      if (!text) continue
      const verts = block.boundingBox?.vertices ?? []
      const xs = verts.map(v => v.x ?? 0)
      const ys = verts.map(v => v.y ?? 0)
      const x1 = Math.min(...xs), y1 = Math.min(...ys)
      const x2 = Math.max(...xs), y2 = Math.max(...ys)
      const px = (x2 - x1) * 0.12, py = (y2 - y1) * 0.12
      results.push({
        text,
        confidence: block.confidence ?? 0,
        bbox: [x1 - px, y1 - py, x2 + px, y2 + py],
        polygon: verts.length ? verts.map(v => [v.x ?? 0, v.y ?? 0]) : null,
      })
    }
  }
  return results
}

async function callGoogleVision(imageUrl, apiKey) {
  const imgRes = await fetch(imageUrl, {
    headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' },
  })
  if (!imgRes.ok) throw new Error(`Failed to fetch image: HTTP ${imgRes.status}`)
  const b64 = Buffer.from(await imgRes.arrayBuffer()).toString('base64')

  const res = await fetch(
    `https://vision.googleapis.com/v1/images:annotate?key=${apiKey}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        requests: [{
          image: { content: b64 },
          features: [{ type: 'DOCUMENT_TEXT_DETECTION' }],
          imageContext: { languageHints: ['ja'] },
        }],
      }),
    }
  )
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Google Vision error ${res.status}: ${text.slice(0, 200)}`)
  }
  return parseVisionResponse(await res.json())
}

async function callPaddleOCR(imageUrl, apiToken) {
  const authHeader = { 'Authorization': `bearer ${apiToken}` }

  // Submit async job with fileUrl
  const jobRes = await fetch(PADDLEOCR_JOB_URL, {
    method: 'POST',
    headers: { ...authHeader, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      fileUrl: imageUrl,
      model: PADDLE_MODEL,
      optionalPayload: {
        useDocOrientationClassify: false,
        useDocUnwarping: false,
        useTextlineOrientation: false,
      },
    }),
  })
  if (!jobRes.ok) {
    const text = await jobRes.text()
    throw new Error(`PaddleOCR submit error ${jobRes.status}: ${text.slice(0, 200)}`)
  }
  const jobId = (await jobRes.json()).data.jobId

  // Poll until done (max ~50s to stay within 60s function limit)
  let jsonlUrl = null
  for (let i = 0; i < 12; i++) {
    await new Promise(r => setTimeout(r, i === 0 ? 2000 : 4000))
    const pollRes = await fetch(`${PADDLEOCR_JOB_URL}/${jobId}`, { headers: authHeader })
    if (!pollRes.ok) throw new Error(`PaddleOCR poll error ${pollRes.status}`)
    const pollData = (await pollRes.json()).data
    if (pollData.state === 'done') { jsonlUrl = pollData.resultUrl.jsonUrl; break }
    if (pollData.state === 'failed') throw new Error(`PaddleOCR job failed: ${pollData.errorMsg}`)
  }
  if (!jsonlUrl) throw new Error('PaddleOCR job timed out')

  // Fetch and parse JSONL result
  const jsonlRes = await fetch(jsonlUrl)
  if (!jsonlRes.ok) throw new Error(`Failed to fetch PaddleOCR result: ${jsonlRes.status}`)
  const results = []
  for (const line of (await jsonlRes.text()).trim().split('\n')) {
    if (!line.trim()) continue
    results.push(...parsePaddleResponse(JSON.parse(line)))
  }
  return results
}

export default async function handler(req, res) {
  if (handleTransOptions(req, res)) return
  setTransCors(req, res)

  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' })

  const { password, imageUrl, ocrSource } = req.body || {}

  const expected = process.env.TRANS_PASSWORD
  if (!expected || !password || password !== expected) {
    return res.status(401).json({ error: 'invalid_password' })
  }

  const paddleToken = process.env.PADDLEOCR_API_TOKEN
  const visionKey = process.env.GOOGLE_VISION_API_KEY

  if (!imageUrl) return res.status(400).json({ error: 'imageUrl is required' })

  try {
    let results, source

    if (visionKey && ocrSource !== 'paddle') {
      const redis = getRedis()
      const count = await getAndIncrVisionCount(redis)
      if (count <= VISION_MONTHLY_LIMIT) {
        results = await callGoogleVision(imageUrl, visionKey)
        source = 'vision'
      }
    }

    if (!results) {
      if (!paddleToken) return res.status(500).json({ error: 'No OCR backend configured' })
      results = await callPaddleOCR(imageUrl, paddleToken)
      source = 'paddle'
    }

    return res.status(200).json({ results, source })
  } catch (err) {
    return res.status(500).json({ error: err.message })
  }
}
