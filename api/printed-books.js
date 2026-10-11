import { handleTransOptions, setTransCors } from './_trans-cors.js'
import { parseBooksCSV, serializeBooksCSV } from '../shared/printedBooks.js'

const CONTENTS_URL = 'https://api.github.com/repos/ywryn/NoHentai/contents/web-static/public/data/future_digi.csv'
const BRANCH = 'master'

async function github(token, method, body) {
  return fetch(`${CONTENTS_URL}${method === 'GET' ? `?ref=${BRANCH}` : ''}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'Content-Type': 'application/json',
    },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(20000),
  })
}

export default async function handler(req, res) {
  if (handleTransOptions(req, res)) return
  setTransCors(req, res)
  res.setHeader('Cache-Control', 'no-store')
  if (req.method !== 'POST') return res.status(405).json({ error: '仅支持 POST 请求' })

  const { password, action, books, sha } = req.body || {}
  if (!process.env.TRANS_PASSWORD) return res.status(503).json({ error: '书单编辑密码尚未配置' })
  if (typeof password !== 'string' || password !== process.env.TRANS_PASSWORD) {
    return res.status(401).json({ error: '密码错误，请重新登录' })
  }
  if (!['load', 'save'].includes(action)) return res.status(400).json({ error: '未知操作' })
  const token = process.env.PRINTED_GITHUB_TOKEN
  if (!token) return res.status(503).json({ error: '书单保存服务尚未配置，请联系管理员配置仓库写入权限' })

  try {
    if (action === 'load') {
      const response = await github(token, 'GET')
      if (!response.ok) return upstreamError(response, res)
      const file = await response.json()
      if (file.encoding !== 'base64' || !file.content || !file.sha) throw new Error('invalid file')
      const csv = Buffer.from(file.content, 'base64').toString('utf8')
      return res.status(200).json({ books: parseBooksCSV(csv), sha: file.sha })
    }

    if (typeof sha !== 'string' || !/^[a-f0-9]{40}$/.test(sha)) return res.status(400).json({ error: '缺少文件版本，请重新加载书单' })
    let csv
    try { csv = serializeBooksCSV(books) }
    catch (error) { return res.status(400).json({ error: error.message }) }
    if (Buffer.byteLength(csv, 'utf8') > 500000) return res.status(400).json({ error: '书单过大，无法保存' })

    const response = await github(token, 'PUT', {
      message: 'feat(printed): update book list from editor',
      branch: BRANCH,
      sha,
      content: Buffer.from(csv, 'utf8').toString('base64'),
    })
    if (!response.ok) return upstreamError(response, res)
    const saved = await response.json()
    if (!saved.content?.sha || !saved.commit?.sha) throw new Error('invalid save response')
    return res.status(200).json({ sha: saved.content.sha, commit: saved.commit.sha })
  } catch {
    return res.status(502).json({ error: '暂时无法访问书单存储服务，请稍后重试；若保存结果不明确，请先导出备份再重新加载核对' })
  }
}

function upstreamError(response, res) {
  if (response.status === 409 || response.status === 422) return res.status(409).json({ error: '保存未完成，文件可能已更新或分支限制了直接写入。请先导出修改，再重新加载核对' })
  if ([401, 403, 404].includes(response.status)) return res.status(503).json({ error: '仓库访问失败，请检查写入凭据、分支权限及凭据有效期' })
  return res.status(502).json({ error: '书单存储服务暂时不可用，请稍后重试' })
}
