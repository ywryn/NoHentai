import { handleTransOptions, setTransCors } from './_trans-cors.js'
import { sha1, cacheGet, cacheSet } from './_redis.js'

const TRANSLATE_CACHE_TTL = 7 * 24 * 3600
const MAX_PREVIOUS_PAIRS = 12
const MAX_GLOSSARY = 60
const KINDS = new Set(['dialogue', 'narration', 'sfx'])

const SYSTEM_PROMPT = `你是专业的日漫汉化翻译员。

## 任务
将输入 JSON 的每个 value（日文 OCR 文本）翻译为简体中文。输入按漫画阅读顺序（右→左、上→下）排列，相邻条目通常来自同一页面、同一场景。

## 输出格式（最高优先级，不得违反）
- **只输出一个 JSON 对象**，key 与输入完全相同，不得增减
- 每个 value 是对象：{"t": 译文, "k": 类型, "a": 备选译文或 null}
  - "t"：简体中文译文，**只能包含简体中文与标点/数字**，严禁出现假名或日文汉字，不要括注原文，不要解释
  - "k"："dialogue"（对白/独白）| "narration"（旁白/说明文字）| "sfx"（拟声词/效果音）
  - "a"：仅当原文含义模糊、有明显不同的另一种译法时给出备选译文，否则为 null
- 禁止输出 JSON 以外的任何内容（含 markdown 代码块）

示例输入：
{"1":"おはよう","2":"ドカンッ！","3":"お前は何者だ？"}

正确输出：
{"1":{"t":"早上好","k":"dialogue","a":null},"2":{"t":"轰隆！","k":"sfx","a":null},"3":{"t":"你是什么人？","k":"dialogue","a":null}}

## 翻译规则
1. 修正 OCR 错误（形近字、断行、多余空格），恢复自然语序
2. 判别对白/独白/旁白/拟声词语境，口吻与人物身份匹配
3. 称谓：さん→先生/小姐视语境，ちゃん→小X，くん→（名）君，様→大人，先輩→前辈；若术语表另有规定以术语表为准
4. 口语自然，保留粗口和俚语力度，不做审查、不弱化
5. 拟声词译为中文口语化表达（如「轰隆」「咚」「哗啦」），不要留日文
6. 人名、专有名词与上一页对照及术语表保持一致`

function buildContextMessage({ context, previous, glossary }) {
  const parts = []
  if (context?.title) parts.push(`本作标题：${String(context.title).slice(0, 200)}`)
  if (Array.isArray(context?.tags) && context.tags.length) {
    parts.push(`本作标签（用于把握题材、人物与口吻）：${context.tags.slice(0, 40).join('，')}`)
  }
  const gl = glossary && typeof glossary === 'object' ? Object.entries(glossary).slice(0, MAX_GLOSSARY) : []
  if (gl.length) {
    parts.push('术语表（原文→译文，必须遵守）：\n' + gl.map(([k, v]) => `${k} → ${v}`).join('\n'))
  }
  const prev = Array.isArray(previous) ? previous.slice(-MAX_PREVIOUS_PAIRS) : []
  if (prev.length) {
    parts.push('上一页的翻译对照（保持人名、称谓、口吻一致）：\n' +
      prev.map(([ja, zh]) => `${ja} ⇒ ${zh}`).join('\n'))
  }
  return parts.length ? parts.join('\n\n') : null
}

function extractJSON(content) {
  let cleaned = content.trim()
  const fence = cleaned.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/)
  if (fence) cleaned = fence[1].trim()
  try { return JSON.parse(cleaned) } catch {}
  const start = content.indexOf('{')
  const end = content.lastIndexOf('}') + 1
  if (start >= 0 && end > start) {
    try { return JSON.parse(content.slice(start, end)) } catch {}
  }
  return null
}

const JA_RE = /[぀-ゟ゠-ヿ]/

/** 归一化一条译文；模型漏项 / 空串 / 原样吐回日文时返回 null，前端据此标「未翻译」并可补译 */
function normalizeItem(raw, original) {
  if (raw == null) return null
  const obj = typeof raw === 'string' ? { t: raw } : raw
  const t = String(obj.t ?? obj.translation ?? '').trim()
  if (!t || t === original) return null
  const kind = KINDS.has(obj.k) ? obj.k : KINDS.has(obj.kind) ? obj.kind : 'dialogue'
  const altRaw = obj.a ?? obj.alt
  const alt = altRaw && String(altRaw).trim() && String(altRaw).trim() !== t ? String(altRaw).trim() : null
  return { t, kind, alt, ja_leak: JA_RE.test(t) }
}

export default async function handler(req, res) {
  if (handleTransOptions(req, res)) return
  setTransCors(req, res)

  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' })

  const { password, texts, context, previous, glossary } = req.body || {}

  const expected = process.env.TRANS_PASSWORD
  if (!expected || !password || password !== expected) {
    return res.status(401).json({ error: 'invalid_password' })
  }

  const apiKey = process.env.LLM_API_KEY
  const apiBase = (process.env.LLM_API_BASE || '').replace(/\/+$/, '')
  const model = process.env.LLM_MODEL || 'gpt-4o-mini'
  // 部分 OpenAI 兼容网关不认 response_format，默认不带；确认支持后设 LLM_JSON_MODE=1
  const jsonMode = process.env.LLM_JSON_MODE === '1'

  if (!apiKey || !apiBase) return res.status(500).json({ error: 'LLM not configured' })
  if (!Array.isArray(texts) || !texts.length) return res.status(400).json({ error: 'texts is required' })

  const contextMessage = buildContextMessage({ context, previous, glossary })
  const cacheKey = `tr:v2:${sha1(JSON.stringify({ model, texts, contextMessage }))}`
  const cached = await cacheGet(cacheKey)
  if (cached?.translations) return res.status(200).json({ ...cached, cached: true })

  const inputData = {}
  texts.forEach((t, i) => { inputData[String(i + 1)] = t })

  const messages = [{ role: 'system', content: SYSTEM_PROMPT }]
  if (contextMessage) messages.push({ role: 'system', content: contextMessage })
  messages.push({ role: 'user', content: JSON.stringify(inputData) })

  try {
    const llmRes = await fetch(`${apiBase}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        messages,
        temperature: 0.3,
        max_tokens: 4000,
        ...(jsonMode ? { response_format: { type: 'json_object' } } : {}),
      }),
    })

    if (!llmRes.ok) {
      const errText = await llmRes.text().catch(() => '')
      throw new Error(`LLM error ${llmRes.status}: ${errText.slice(0, 200)}`)
    }

    const data = await llmRes.json()
    const content = data.choices?.[0]?.message?.content?.trim() ?? ''
    const parsed = extractJSON(content)
    if (!parsed) throw new Error('LLM 返回内容不是合法 JSON')

    const translations = texts.map((orig, i) => normalizeItem(parsed[String(i + 1)], orig))
    const payload = { translations }
    // 有漏项就不缓存，让补译有机会拿到完整结果
    if (translations.every(Boolean)) await cacheSet(cacheKey, payload, TRANSLATE_CACHE_TTL)
    return res.status(200).json(payload)
  } catch (err) {
    return res.status(500).json({ error: err.message })
  }
}
