const KEY = 'nohentai-admin-session-v1'

export function clearAdminLogin() {
  for (const storage of ['localStorage', 'sessionStorage']) {
    try { window[storage].removeItem(KEY) } catch { /* Storage can be disabled. */ }
  }
}
