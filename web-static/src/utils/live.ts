const base = import.meta.env.VITE_API_BASE ?? ''

export function liveUrl(action: string, params: Record<string, string>) {
  return base + '/api/live/' + action + '?' + new URLSearchParams(params)
}

export async function liveData(action: string, params: Record<string, string>) {
  const response = await fetch(liveUrl(action, params))
  if (response.status === 401) window.dispatchEvent(new Event('cost-session-expired'))
  const data = await response.json()
  if (!response.ok) throw new Error(data.error || '请求失败，请重试')
  return data
}
