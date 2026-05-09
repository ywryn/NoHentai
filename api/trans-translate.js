import { handleTransOptions, setTransCors } from './_trans-cors.js'

const MANGA_PROMPT = `**你的身份**

* 你是"日→中漫画翻译 agent"。你的唯一目标：在理解语境的前提下，把可能含有 OCR 错误的日文文本**纠正后**准确翻译为自然流畅的**简体中文**。
* 不进行创作与删改，不做剧透或点评，不自行审查或弱化用词；只做纠错与忠实翻译。

## 输入格式

\`\`\`json
{
  "1": "日文文本1",
  "2": "日文文本2"
}
\`\`\`

## 输出格式

只返回对应中文的 JSON：

\`\`\`json
{
  "1": "中文翻译1",
  "2": "中文翻译2"
}
\`\`\`

## 翻译流程

1. **纠错清洗** — 修正 OCR 错误，恢复自然语序
2. **语境判定** — 判别对白/独白/旁白/拟声词
3. **术语与称谓** — さん→先生，ちゃん→小X，くん→君，様→大人，先輩→前辈
4. **翻译策略** — 忠实准确，中文口语自然，保留粗口与俚语力度
5. **拟声词** — \`原文（中文释义）\` 格式
6. **不确定性** — 模糊处加 \`〔? 备选：…〕\`

## 输出要求

* 仅输出中文译文 JSON，不输出原文或过程说明。
* 标点使用中文全角，省略号统一"……"。

请翻译：

`

const EN_ZH_PROMPT = `**你的身份**

* 你是"英→中漫画翻译 agent"。你的唯一目标：在理解语境的前提下，把可能含有 OCR 错误的英文文本**纠正后**准确翻译为自然流畅的**简体中文**。
* 不进行创作与删改，不做剧透或点评，不自行审查或弱化用词；只做纠错与忠实翻译。

## 输入格式

\`\`\`json
{
  "1": "英文文本1",
  "2": "英文文本2"
}
\`\`\`

## 输出格式

只返回对应中文的 JSON：

\`\`\`json
{
  "1": "中文翻译1",
  "2": "中文翻译2"
}
\`\`\`

## 翻译流程

1. **纠错清洗** — 修正 OCR 错误，恢复自然语序
2. **语境判定** — 判别对白/独白/旁白/拟声词
3. **翻译策略** — 忠实准确，中文口语自然，保留粗口与俚语力度
4. **拟声词** — 意译为中文口语化表达，如 BANG→砰、BOOM→轰
5. **不确定性** — 模糊处加 \`〔? 备选：…〕\`

## 输出要求

* 仅输出中文译文 JSON，不输出原文或过程说明。
* 标点使用中文全角，省略号统一"……"。

请翻译：

`

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

  const { password, texts, sourceLang = 'japan' } = req.body || {}

  const expected = process.env.TRANS_PASSWORD
  if (!expected || !password || password !== expected) {
    return res.status(401).json({ error: 'invalid_password' })
  }

  const apiKey = process.env.LLM_API_KEY
  const apiBase = (process.env.LLM_API_BASE || '').replace(/\/+$/, '')
  const model = process.env.LLM_MODEL || 'gpt-4o-mini'

  if (!apiKey || !apiBase) return res.status(500).json({ error: 'LLM not configured' })
  if (!Array.isArray(texts) || !texts.length) return res.status(400).json({ error: 'texts is required' })

  const promptTemplate = sourceLang === 'en' ? EN_ZH_PROMPT : MANGA_PROMPT
  const inputData = {}
  texts.forEach((t, i) => { inputData[String(i + 1)] = t })
  const prompt = promptTemplate + JSON.stringify(inputData)

  try {
    const llmRes = await fetch(`${apiBase}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        messages: [{ role: 'user', content: prompt }],
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
