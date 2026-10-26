const KEY = 'nohentai-admin-session-v1'

export function clearAdminLogin() {
  for (const storage of ['localStorage', 'sessionStorage']) {
    try { window[storage].removeItem(KEY) } catch { /* Storage can be disabled. */ }
  }
}

export function readAdminLogin(now = Date.now()) {
  for (const storage of ['localStorage', 'sessionStorage']) {
    try {
      const value = JSON.parse(window[storage].getItem(KEY) || 'null')
      if (typeof value?.token === 'string' && value.token.startsWith('admin.v1.') && Number.isSafeInteger(value.expiresAt) && value.expiresAt > now) {
        return { ...value, remember: storage === 'localStorage' }
      }
      window[storage].removeItem(KEY)
    } catch { /* Missing, invalid or inaccessible storage does not block login. */ }
  }
  return null
}

export function saveAdminLogin(session, remember) {
  clearAdminLogin()
  try {
    window[remember ? 'localStorage' : 'sessionStorage'].setItem(KEY, JSON.stringify({ token: session.token, expiresAt: session.expiresAt }))
    return true
  } catch { return false }
}
