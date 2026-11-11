const apiBase = import.meta.env.VITE_API_BASE || ''
async function publicRequest(path, signal) {
  const response = await fetch(`${apiBase}${path}`, { signal })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.error || `加载失败（${response.status}）`)
  }
  return response.json()
}
export function loadGalleryPage(params, signal) {
  return publicRequest(`/api/galleries?${new URLSearchParams(params)}`, signal)
}
export function loadTagSuggestions(token, signal) {
  return publicRequest(`/api/tags/suggestions?${new URLSearchParams({ token })}`, signal)
}

export function loadGallery(gid, source = 'favorites', signal) {
  return publicRequest(`/api/galleries/${encodeURIComponent(gid)}?${new URLSearchParams({ source })}`, signal)
}

// Public screens refresh when revisited without polling background tabs.
export function watchPublicRevision(onChange) {
  let revision = null, busy = false, stopped = false
  async function check() {
    if (busy || stopped || document.visibilityState !== 'visible') return
    busy = true
    try {
      const data = await publicRequest('/api/revision')
      const next = JSON.stringify(data)
      if (revision !== null && revision !== next && !stopped) await onChange()
      revision = next
    } catch { /* Existing content remains available; manual refresh can retry. */ }
    finally { busy = false }
  }
  check()
  window.addEventListener('focus', check)
  document.addEventListener('visibilitychange', check)
  return () => { stopped = true; window.removeEventListener('focus', check); document.removeEventListener('visibilitychange', check) }
}
