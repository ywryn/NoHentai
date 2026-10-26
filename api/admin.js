import { createHash, timingSafeEqual } from 'node:crypto'
import { handleTransOptions, setTransCors } from './_trans-cors.js'
import { RESOURCES, GALLERIES_PATH, validateDaily, validateOverrides, validateTranslate, validateReferences, mergeGalleries } from '../shared/adminData.js'
import { parseBooksCSV, serializeBooksCSV } from '../shared/printedBooks.js'
import { AdminError, github, readRepoFile, writeRepoFile, REPO, BRANCH } from '../shared/adminGithub.js'
import { platformStatus, replaceSecret, redeployBackend, checkHealth } from '../shared/adminPlatforms.js'

const WORKFLOWS = ['deploy.yml', 'sync.yml', 'sync-ex.yml', 'sync-translations.yml']
function authenticate(password) {
  const expected = process.env.ADMIN_PASSWORD
  if (!expected) throw new AdminError(503, '请在 Vercel 配置独立的 ADMIN_PASSWORD')
  const hash = v => createHash('sha256').update(v).digest()
  if (typeof password !== 'string' || password.length > 1024 || !timingSafeEqual(hash(password), hash(expected))) {
    throw new AdminError(401, '管理密码错误，请重新登录')
  }
}
function parse(resource, text) { return resource === 'printed' ? parseBooksCSV(text) : JSON.parse(text) }
function serialize(resource, data) {
  if (resource === 'printed') return serializeBooksCSV(data)
  const validate = { overrides: validateOverrides, daily: validateDaily, translate: validateTranslate }[resource]
  return JSON.stringify(validate(data), null, 2) + '\n'
}

export default async function handler(req, res) {
  if (handleTransOptions(req, res)) return
  setTransCors(req, res)
  res.setHeader('Cache-Control', 'no-store')
  res.setHeader('X-Content-Type-Options', 'nosniff')
  if (req.method !== 'POST') return res.status(405).json({ error: '仅支持 POST 请求' })
  // Reject foreign browser origins as well as omitting CORS headers. No cookie auth.
  const origin = req.headers.origin
  if (origin && !['https://nohentai.com', 'https://www.nohentai.com'].includes(origin) && !/^http:\/\/localhost(:\d+)?$/.test(origin)) {
    return res.status(403).json({ error: '不允许的请求来源' })
  }
  try {
    const body = req.body || {}
    authenticate(body.password)
    const { action, resource } = body
    if (action === 'verify') return res.status(200).json({ ok: true, repo: REPO, branch: BRANCH })
    if (['load', 'save', 'history'].includes(action)) {
      if (!Object.hasOwn(RESOURCES, resource)) throw new AdminError(400, '不允许访问此资源')
      const path = RESOURCES[resource]
      if (action === 'history') {
        const commits = await (await github(`/commits?path=${encodeURIComponent(path)}&sha=${BRANCH}&per_page=15`)).json()
        return res.status(200).json({ commits: commits.map(c => ({ sha: c.sha, message: c.commit.message, date: c.commit.committer.date, url: c.html_url })) })
      }
      if (action === 'load') {
        const file = await readRepoFile(path)
        return res.status(200).json({ data: parse(resource, file.text), sha: file.sha })
      }
      let text
      try { text = serialize(resource, body.data) } catch (error) { throw new AdminError(400, error.message) }
      if (!/^[a-f0-9]{40}$/.test(body.sha || '')) throw new AdminError(400, '缺少文件版本，请重新加载')
      let warnings = []
      if (resource === 'printed') {
        const source = JSON.parse((await readRepoFile(GALLERIES_PATH)).text)
        const missing = validateReferences(body.data, source)
        // Existing books may refer to galleries outside favorites. Preserve them,
        // but reject newly introduced broken references.
        const current = parseBooksCSV((await readRepoFile(path)).text)
        const legacy = new Set(current.map(b => b.sid))
        if (missing.some(b => !legacy.has(b.sid))) throw new AdminError(400, '新增关联的画廊 ID 不在收藏数据中，请重新选择')
        if (missing.length) warnings.push(`保留 ${missing.length} 条已有的站外画廊关联`)
      }
      if (resource === 'overrides') {
        const ids = new Set(JSON.parse((await readRepoFile(GALLERIES_PATH)).text).map(g => String(g.gid)))
        const current = JSON.parse((await readRepoFile(path)).text)
        if (Object.keys(body.data).some(id => !ids.has(id) && !Object.hasOwn(current, id))) throw new AdminError(400, '新增覆盖的画廊 ID 不存在')
      }
      return res.status(200).json({ ...await writeRepoFile(path, text, body.sha, resource), warnings })
    }
    if (action === 'gallery-search') {
      const [raw, patches] = await Promise.all([readRepoFile(GALLERIES_PATH), readRepoFile(RESOURCES.overrides)])
      const source = JSON.parse(raw.text), overrides = JSON.parse(patches.text)
      const query = String(body.query || '').trim().toLowerCase().slice(0, 200)
      const page = Math.max(1, Math.min(10000, Number.parseInt(body.page) || 1))
      const all = mergeGalleries(source, overrides, { includeHidden: true }).filter(g =>
        !query || [g.gid, g.title, g.title_jpn, g.uploader, ...(g.tags || [])].some(v => String(v || '').toLowerCase().includes(query)))
      const originals = new Map(source.map(g => [String(g.gid), g]))
      return res.status(200).json({ total: all.length, page, items: all.slice((page - 1) * 30, page * 30).map(g => ({ gallery: g, source: originals.get(String(g.gid)), override: overrides[String(g.gid)] || {} })) })
    }
    if (action === 'runs') {
      const runs = await (await github(`/actions/runs?branch=${BRANCH}&per_page=30`)).json()
      return res.status(200).json({ runs: runs.workflow_runs.filter(r => WORKFLOWS.includes(r.path?.split('/').pop())).map(r => ({ id: r.id, name: r.name, status: r.status, conclusion: r.conclusion, sha: r.head_sha, createdAt: r.created_at, updatedAt: r.updated_at, url: r.html_url })) })
    }
    if (action === 'dispatch') {
      if (!WORKFLOWS.includes(body.workflow)) throw new AdminError(400, '不允许触发此任务')
      await github(`/actions/workflows/${body.workflow}/dispatches`, { method: 'POST', body: { ref: BRANCH } })
      return res.status(200).json({ accepted: true })
    }
    if (action === 'rerun') {
      if (!Number.isSafeInteger(body.runId) || body.runId < 1) throw new AdminError(400, '任务 ID 不正确')
      const run = await (await github(`/actions/runs/${body.runId}`)).json()
      if (run.head_branch !== BRANCH || !WORKFLOWS.includes(run.path?.split('/').pop()) || run.status !== 'completed') throw new AdminError(400, '只能重跑主分支已完成的管理任务')
      await github(`/actions/runs/${body.runId}/rerun`, { method: 'POST' })
      return res.status(200).json({ accepted: true })
    }
    if (action === 'platforms') return res.status(200).json(await platformStatus())
    if (action === 'replace-secret') return res.status(200).json(await replaceSecret(body))
    if (action === 'redeploy-backend') return res.status(200).json(await redeployBackend())
    if (action === 'health') return res.status(200).json(await checkHealth())
    throw new AdminError(400, '未知管理操作')
  } catch (error) {
    return res.status(error instanceof AdminError ? error.status : 502).json({ error: error instanceof AdminError ? error.message : '管理服务暂时不可用；保存结果不明确时，请先导出草稿再重新加载核对' })
  }
}
