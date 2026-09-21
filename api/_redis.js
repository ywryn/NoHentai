import { createHash } from 'node:crypto'
import { Redis } from '@upstash/redis'

let _client = null

/** Upstash Redis；未配置时返回 null，调用方按「无缓存」降级 */
export function getRedis() {
  if (_client) return _client
  const url = process.env.KV_REST_API_URL
  const token = process.env.KV_REST_API_TOKEN
  if (!url || !token) return null
  _client = new Redis({ url, token })
  return _client
}

export function sha1(input) {
  return createHash('sha1').update(input).digest('hex')
}

export async function cacheGet(key) {
  const redis = getRedis()
  if (!redis) return null
  try { return await redis.get(key) } catch { return null }
}

export async function cacheSet(key, value, ttlSeconds) {
  const redis = getRedis()
  if (!redis) return
  try { await redis.set(key, value, { ex: ttlSeconds }) } catch {}
}
