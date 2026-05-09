import { handleTransOptions, setTransCors } from './_trans-cors.js'

const SYSTEM_PROMPT = `你是专业的日漫汉化翻译员。

## 任务
将输入 JSON 的每个 value（日文）翻译为简体中文，返回 key 完全相同、value 替换为中文译文的 JSON。

## 输出格式（最高优先级，不得违反）
- **只输出一个 JSON 对象，不输出任何其他内容**
- 每个 value **只能包含简体中文**（标点/数字除外）
- **严禁在 value 中出现任何日文字符**（平假名・片假名・日文汉字）
- 禁止附加原文对照、注释、解释、翻译过程

示例输入：
{"1":"おはよう","2":"ドカンッ！","3":"お前は何者だ？"}

正确输出：
{"1":"早上好","2":"轰隆！","3":"你是什么人？"}

## 翻译规则
1. 修正 OCR 错误，恢复自然语序
2. 判别对白/独白/旁白/拟声词语境
3. 称谓：さん→先生，ちゃん→小X，くん→（名）君，様→大人，先輩→前辈
4. 口语自然，保留粗口和俚语力度，不做审查
5. 拟声词：译为中文口语化表达，可括注原文，如"轰隆（ドカン）"
6. 模糊处加〔? 备选：…〕`


function parseTranslationJSON(content, fallback) {
  let cleaned = content.trim()
  if (cleaned.startsWith('```json')) {
    cleaned = cleaned.slice(7)
    const end = cleaned.lastIndexOf('```')
    if (end !== -1) cleaned = cleaned.slice(0, end)
  } else if (cleaned.startsWith('```')) {
    cleaned = cleaned.slice(3)
    const end = cleaned.lastIndexOf('```')
    if (end !== -1) cleaned = cleaned.slice(0, end)
  }
  cleaned = cleaned.trim()

  try {
    const parsed = JSON.parse(cleaned)
    return fallback.map((orig, i) => String(parsed[String(i + 1)] ?? orig))
  } catch {
    const start = content.indexOf('{')
    const end = content.lastIndexOf('}') + 1
    if (start >= 0 && end > start) {
      try {
        const parsed = JSON.parse(content.slice(start, end))
        return fallback.map((orig, i) => String(parsed[String(i + 1)] ?? orig))
      } catch {}
    }
    return fallback
  }
}

export default async function handler(req, res) {
  if (handleTransOptions(req, res)) return
  setTransCors(req, res)

  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' })

  const { password, texts } = req.body || {}

  const expected = process.env.TRANS_PASSWORD
  if (!expected || !password || password !== expected) {
    return res.status(401).json({ error: 'invalid_password' })
  }

  const apiKey = process.env.LLM_API_KEY
  const apiBase = (process.env.LLM_API_BASE || '').replace(/\/+$/, '')
  const model = process.env.LLM_MODEL || 'gpt-4o-mini'

  if (!apiKey || !apiBase) return res.status(500).json({ error: 'LLM not configured' })
  if (!Array.isArray(texts) || !texts.length) return res.status(400).json({ error: 'texts is required' })

  const inputData = {}
  texts.forEach((t, i) => { inputData[String(i + 1)] = t })

  try {
    const llmRes = await fetch(`${apiBase}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        messages: [
          { role: 'system', content: SYSTEM_PROMPT },
          { role: 'user', content: JSON.stringify(inputData) },
        ],
        temperature: 0.3,
        max_tokens: 4000,
      }),
    })

    if (!llmRes.ok) {
      const errText = await llmRes.text().catch(() => '')
      throw new Error(`LLM error ${llmRes.status}: ${errText.slice(0, 200)}`)
    }

    const data = await llmRes.json()
    const content = data.choices?.[0]?.message?.content?.trim() ?? ''
    const translations = parseTranslationJSON(content, texts)
    return res.status(200).json({ translations })
  } catch (err) {
    return res.status(500).json({ error: err.message })
  }
}
