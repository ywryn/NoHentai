const API = import.meta.env.VITE_API_BASE || ''
let csrf = ''
export async function currentAdmin() {
  const response = await fetch(`${API}/api/admin/session`, { credentials: 'same-origin', cache: 'no-store' })
  if (response.status === 401) { csrf = ''; return null }
  if (!response.ok) throw new Error('管理服务暂时不可用，请稍后重试')
  const result = await response.json()
  csrf = result.session.csrf
  return result.session
}
export async function loginAdmin(password, remember) {
  const response = await fetch(`${API}/api/admin`, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'verify', mode: 'cookie', password, remember }) })
  const result = await response.json()
  if (!response.ok) throw new Error(result.error || '登录失败')
  csrf = result.session.csrf
  return result.session
}
export async function adminRequest(action, data = {}, refreshed = false) {
  const response = await fetch(`${API}/api/admin`, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: JSON.stringify({ action, ...data }) })
  const result = await response.json().catch(() => ({}))
  if (response.status === 403 && !refreshed && result.error?.includes('会话验证')) {
    if (await currentAdmin()) return adminRequest(action, data, true)
  }
  if (!response.ok) {
    const error = new Error(response.status === 401 ? '登录已过期，可在新标签页重新登录后重试，当前草稿仍保留。' : result.error || '请求失败，请稍后重试')
    error.status = response.status
    throw error
  }
  return result
}
export function downloadDraft(name, data) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = name; anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
export const formatDate = value => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '尚无记录'
export const coverUrl = filename => /^[a-f0-9]{32}\.webp$/.test(filename || '') ? `/media/${filename}` : `/printed-cover/${encodeURIComponent(filename || '')}`
