import sodium from 'libsodium-wrappers'
import { AdminError, github } from './adminGithub.js'

export const GITHUB_SECRETS = ['EXHENTAI_BASE_URL', 'EXHENTAI_COOKIE_MEMBER_ID', 'EXHENTAI_COOKIE_PASS_HASH', 'EXHENTAI_COOKIE_IGNEOUS']
export const VERCEL_SECRETS = ['EXHENTAI_COOKIE_MEMBER_ID', 'EXHENTAI_COOKIE_PASS_HASH', 'EXHENTAI_COOKIE_IGNEOUS', 'LLM_API_KEY', 'LLM_API_BASE', 'LLM_MODEL', 'LLM_JSON_MODE', 'GOOGLE_VISION_API_KEY', 'PADDLEOCR_API_TOKEN', 'OCR_SPACE_KEY', 'TRANS_PASSWORD']

async function vercel(path, { method = 'GET', body } = {}) {
  const missing = ['ADMIN_VERCEL_TOKEN', 'ADMIN_VERCEL_PROJECT_ID'].filter(name => !process.env[name])
  if (missing.length) throw platformError('not_configured', `尚未连接 Vercel，请配置 ${missing.join('、')}`, { missing })
  const team = process.env.ADMIN_VERCEL_TEAM_ID
  let response
  try {
    response = await fetch(`https://api.vercel.com${path}${team ? `${path.includes('?') ? '&' : '?'}teamId=${encodeURIComponent(team)}` : ''}`, {
      method, headers: { Authorization: `Bearer ${process.env.ADMIN_VERCEL_TOKEN}`, 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(15000), redirect: 'error',
    })
  } catch { throw platformError('unreachable', '暂时无法连接 Vercel，请稍后重试') }
  if (!response.ok) {
    const errors = {
      401: ['unauthorized', 'Vercel Token 无效或已过期，请在部署平台替换'],
      403: ['forbidden', 'Vercel 权限不足，请检查 Token 授权范围和项目所属 Team'],
      404: ['project_not_found', '未找到 Vercel 项目，请检查项目 ID 和 Team ID'],
      429: ['rate_limited', 'Vercel 请求过于频繁，请稍后重试'],
    }
    const [code, message] = errors[response.status] || ['upstream_error', 'Vercel 平台暂时异常，请稍后重试']
    throw platformError(code, message)
  }
  return response.json()
}
function platformError(code, message, details = {}) {
  return Object.assign(new AdminError(503, message), { code, ...details })
}
function projectPath() { return `/v9/projects/${encodeURIComponent(process.env.ADMIN_VERCEL_PROJECT_ID || '')}` }

export async function platformStatus() {
  const [gh, vc] = await Promise.allSettled([
    github('/actions/secrets?per_page=100').then(r => r.json()),
    vercel(`${projectPath()}/env?decrypt=false`),
  ])
  return {
    github: { available: gh.status === 'fulfilled', error: gh.status === 'rejected' ? '无法读取 GitHub Secrets；需要 Secrets 权限' : null,
      secrets: GITHUB_SECRETS.map(name => ({ name, configured: gh.status === 'fulfilled' ? gh.value.secrets.some(s => s.name === name) : null })) },
    vercel: { available: vc.status === 'fulfilled',
      code: vc.status === 'rejected' ? vc.reason.code || 'upstream_error' : 'connected',
      missing: vc.status === 'rejected' ? vc.reason.missing || [] : [],
      error: vc.status === 'rejected' ? vc.reason instanceof AdminError ? vc.reason.message : 'Vercel 返回了无法识别的响应，请稍后重试' : null,
      secrets: VERCEL_SECRETS.map(name => ({ name, configured: vc.status === 'fulfilled' ? vc.value.envs.some(e => e.key === name && e.target?.includes('production')) : null })) },
  }
}

export async function replaceSecret({ platform, name, value }) {
  const allowed = platform === 'github' ? GITHUB_SECRETS : platform === 'vercel' ? VERCEL_SECRETS : []
  if (!allowed.includes(name) || typeof value !== 'string' || !value.trim() || value.length > 16000 || /[\r\n\0]/.test(value)) {
    throw new AdminError(400, '凭证名称或内容不正确；仅允许替换列出的单行配置')
  }
  if (platform === 'github') {
    const key = await (await github('/actions/secrets/public-key')).json()
    await sodium.ready
    const encrypted = sodium.crypto_box_seal(sodium.from_string(value), sodium.from_base64(key.key, sodium.base64_variants.ORIGINAL))
    await github(`/actions/secrets/${name}`, { method: 'PUT', body: { key_id: key.key_id, encrypted_value: sodium.to_base64(encrypted, sodium.base64_variants.ORIGINAL) } })
    return { updated: true, message: 'GitHub Secret 已替换，后续启动的任务使用新值。' }
  }
  const all = await vercel(`${projectPath()}/env?decrypt=false`)
  const existing = all.envs.filter(e => e.key === name && e.target?.includes('production'))
  // Updating a shared Production/Preview entry could unexpectedly rotate Preview.
  if (existing.length > 1 || existing.some(e => e.target.length !== 1 || e.gitBranch || e.customEnvironmentIds?.length)) {
    throw new AdminError(409, '此变量跨环境共用或存在多个版本，请先在 Vercel 控制台拆分为独立的 Production 变量')
  }
  const payload = { key: name, value, type: 'encrypted', target: ['production'] }
  if (existing.length) await vercel(`${projectPath()}/env/${encodeURIComponent(existing[0].id)}`, { method: 'PATCH', body: payload })
  else await vercel(`/v10/projects/${encodeURIComponent(process.env.ADMIN_VERCEL_PROJECT_ID)}/env`, { method: 'POST', body: payload })
  return { updated: true, message: 'Vercel Production 变量已替换，需要重新部署后端才能应用。' }
}

export async function redeployBackend() {
  const id = encodeURIComponent(process.env.ADMIN_VERCEL_PROJECT_ID || '')
  const deployments = await vercel(`/v6/deployments?projectId=${id}&target=production&state=READY&limit=1`)
  const latest = deployments.deployments?.[0]
  if (!latest) throw new AdminError(400, '没有可重新部署的 Production 版本，请前往 Vercel 控制台部署')
  const result = await vercel('/v13/deployments', { method: 'POST', body: { name: latest.name, project: process.env.ADMIN_VERCEL_PROJECT_ID, deploymentId: latest.uid, target: 'production' } })
  return { accepted: true, id: result.id, url: result.url ? `https://${result.url}` : null }
}

export async function checkHealth() {
  const checks = [
    { name: 'GitHub Pages 首页', url: 'https://nohentai.com/', expected: [200] },
    { name: '画廊数据', url: 'https://nohentai.com/data/galleries.json', expected: [200] },
    { name: 'Vercel 鉴权接口', url: 'https://no-hentai.vercel.app/api/trans-verify', expected: [401], method: 'POST' },
  ]
  return { checkedAt: new Date().toISOString(), checks: await Promise.all(checks.map(async c => {
    const start = Date.now()
    try {
      const r = await fetch(c.url, { method: c.method || 'GET', headers: c.method ? { 'Content-Type': 'application/json' } : {}, body: c.method ? '{}' : undefined, signal: AbortSignal.timeout(8000), redirect: 'error' })
      await r.body?.cancel()
      return { name: c.name, url: c.url, ok: c.expected.includes(r.status), status: r.status, ms: Date.now() - start }
    } catch { return { name: c.name, url: c.url, ok: false, status: null, ms: Date.now() - start } }
  })) }
}
