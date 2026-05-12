export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type')
  if (req.method === 'OPTIONS') return res.status(204).end()
  if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' })

  const { word } = req.query
  if (!word) return res.status(400).json({ error: 'word is required' })

  try {
    const url = `https://jisho.org/api/v1/search/words?keyword=${encodeURIComponent(word)}`
    const upstream = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; nohentai-study/1.0)',
        'Accept': 'application/json',
      },
    })
    if (!upstream.ok) throw new Error(`Jisho error ${upstream.status}`)
    const data = await upstream.json()

    const results = (data.data || []).slice(0, 5).map(entry => ({
      word: entry.japanese?.[0]?.word || entry.slug,
      reading: entry.japanese?.[0]?.reading || null,
      is_common: !!entry.is_common,
      jlpt: (entry.jlpt || []).map(j => j.replace('jlpt-', '').toUpperCase()),
      senses: (entry.senses || []).slice(0, 6).map(s => ({
        parts_of_speech: s.parts_of_speech || [],
        english_definitions: s.english_definitions || [],
        tags: s.tags || [],
        info: s.info || [],
      })),
    }))

    return res.status(200).json({ results })
  } catch (e) {
    return res.status(500).json({ error: e.message })
  }
}
