import { handleTransOptions, setTransCors } from './_trans-cors.js'

export default async function handler(req, res) {
  if (handleTransOptions(req, res)) return
  setTransCors(req, res)

  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' })

  const { password } = req.body || {}
  const expected = process.env.TRANS_PASSWORD
  if (!expected) return res.status(500).json({ error: 'TRANS_PASSWORD not configured' })
  if (!password || password !== expected) return res.status(401).json({ error: 'invalid_password' })

  return res.status(200).json({ ok: true })
}
