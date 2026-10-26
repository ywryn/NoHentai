export const REPO = 'ywryn/NoHentai'
export const BRANCH = 'master'

export class AdminError extends Error {
  constructor(status, message) { super(message); this.status = status }
}

export async function github(path, { method = 'GET', body, accept = 'application/vnd.github+json' } = {}) {
  const token = process.env.ADMIN_GITHUB_TOKEN || process.env.PRINTED_GITHUB_TOKEN
  if (!token) throw new AdminError(503, '请配置 ADMIN_GITHUB_TOKEN 仓库凭证')
  const response = await fetch(`https://api.github.com/repos/${REPO}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, Accept: accept, 'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(20000),
    redirect: 'error',
  })
  if (!response.ok) {
    if ([409, 422].includes(response.status)) throw new AdminError(409, '文件或分支已变化，请先导出草稿，再重新加载核对；也请检查分支写入限制')
    if ([401, 403, 404].includes(response.status)) throw new AdminError(503, 'GitHub 访问失败，请检查凭证、所需权限及分支设置')
    throw new AdminError(502, 'GitHub 服务暂时不可用')
  }
  return response
}

export async function readRepoFile(path, ref = BRANCH) {
  const response = await github(`/contents/${path}?ref=${encodeURIComponent(ref)}`)
  const file = await response.json()
  if (!/^[a-f0-9]{40}$/.test(file.sha)) throw new Error('invalid GitHub file')
  // Contents API omits base64 content for files >1 MB. Read the immutable blob,
  // never a download_url supplied by the response or a second moving branch read.
  const text = file.encoding === 'base64'
    ? Buffer.from(file.content || '', 'base64').toString('utf8')
    : await (await github(`/git/blobs/${file.sha}`, { accept: 'application/vnd.github.raw+json' })).text()
  return { sha: file.sha, text }
}

export async function writeRepoFile(path, text, sha, resource) {
  if (!/^[a-f0-9]{40}$/.test(sha || '')) throw new AdminError(400, '缺少文件版本，请重新加载')
  if (Buffer.byteLength(text, 'utf8') > 750000) throw new AdminError(400, '文件过大，无法保存')
  const result = await (await github(`/contents/${path}`, { method: 'PUT', body: {
    branch: BRANCH, sha, message: `feat(admin): update ${resource}`, content: Buffer.from(text).toString('base64'),
  } })).json()
  if (!result.content?.sha || !result.commit?.sha) throw new Error('invalid GitHub write response')
  return { sha: result.content.sha, commit: result.commit.sha, url: `https://github.com/${REPO}/commit/${result.commit.sha}` }
}
