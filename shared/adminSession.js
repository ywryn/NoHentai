import { createHmac, randomBytes, timingSafeEqual } from 'node:crypto'

const PREFIX = 'admin.v1'
const TTL = 30 * 24 * 60 * 60 * 1000
function signature(payload, secret) {
  return createHmac('sha256', secret).update(`${PREFIX}.${payload}`).digest('base64url')
}

export function createAdminSession(secret, now = Date.now()) {
  const expiresAt = now + TTL
  const payload = Buffer.from(JSON.stringify({ issuedAt: now, expiresAt, nonce: randomBytes(16).toString('hex') })).toString('base64url')
  return { token: `${PREFIX}.${payload}.${signature(payload, secret)}`, expiresAt }
}

export function readAdminSession(token, secret, now = Date.now()) {
  if (typeof token !== 'string' || token.length > 1024 || !secret) return null
  const parts = token.split('.')
  if (parts.length !== 4 || `${parts[0]}.${parts[1]}` !== PREFIX) return null
  const [, , payload, supplied] = parts
  if (!/^[A-Za-z0-9_-]{43}$/.test(supplied)) return null
  const expected = signature(payload, secret)
  if (supplied.length !== expected.length || !timingSafeEqual(Buffer.from(supplied), Buffer.from(expected))) return null
  try {
    const value = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'))
    if (!Number.isSafeInteger(value.issuedAt) || !Number.isSafeInteger(value.expiresAt) || value.issuedAt > now || value.expiresAt <= now || value.expiresAt - value.issuedAt !== TTL || !/^[a-f0-9]{32}$/.test(value.nonce)) return null
    return { token, expiresAt: value.expiresAt }
  } catch { return null }
}
