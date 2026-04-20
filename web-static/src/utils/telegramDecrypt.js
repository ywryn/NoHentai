/**
 * Telegram 媒体解密工具（浏览器端 Web Crypto API）
 *
 * 加密参数与 sync_telegram.py 完全对应：
 *   算法：AES-256-GCM
 *   密钥派生：PBKDF2-SHA256，100000 次，固定 salt
 *   文件格式：[12 字节 IV] + [GCM 密文+tag]
 *
 * 用法：
 *   import { initKey, decryptToUrl, hasKey } from '@/utils/telegramDecrypt'
 *   await initKey('your-password')
 *   const objectUrl = await decryptToUrl('telegram_media/photos/xxx.webp.enc')
 *   // 用完后 revokeObjectURL(objectUrl)
 */

const SALT = new TextEncoder().encode('NoHentai-Telegram-Salt-v1')
const ITERATIONS = 100_000

let _key = null

/**
 * 用密码派生 AES-GCM key，存入模块内存。
 * 每次页面会话调用一次即可（key 缓存在 sessionStorage 标记中，实体存内存）。
 */
export async function initKey(password) {
  const raw = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(password),
    'PBKDF2',
    false,
    ['deriveKey'],
  )
  _key = await crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt: SALT, iterations: ITERATIONS, hash: 'SHA-256' },
    raw,
    { name: 'AES-GCM', length: 256 },
    false,
    ['decrypt'],
  )
  sessionStorage.setItem('tg_key_ready', '1')
}

/** 当前会话是否已初始化密钥 */
export function hasKey() {
  return _key !== null
}

/** 清除密钥（退出登录时调用） */
export function clearKey() {
  _key = null
  sessionStorage.removeItem('tg_key_ready')
}

/**
 * 下载并解密一个 .enc 文件，返回可直接用于 <img src> 的 Object URL。
 * 调用方负责在不再需要时调用 URL.revokeObjectURL(url) 释放内存。
 *
 * @param {string} encPath  相对于 public/data 的路径，如 'telegram_media/photos/xxx.webp.enc'
 * @param {string} [mimeType='image/webp']
 * @returns {Promise<string>}
 */
export async function decryptToUrl(encPath, mimeType = 'image/webp') {
  if (!_key) throw new Error('解密密钥未初始化，请先调用 initKey()')

  const base = import.meta.env.BASE_URL.replace(/\/$/, '')
  const resp = await fetch(`${base}/data/${encPath}`)
  if (!resp.ok) throw new Error(`加载失败: ${encPath} (${resp.status})`)

  const buf = await resp.arrayBuffer()
  const iv = buf.slice(0, 12)
  const cipher = buf.slice(12)

  let plain
  try {
    plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: new Uint8Array(iv) }, _key, cipher)
  } catch {
    throw new Error('解密失败：密码错误或文件损坏')
  }

  return URL.createObjectURL(new Blob([plain], { type: mimeType }))
}

/**
 * 批量解密，返回 { encPath → objectUrl } Map。
 * 自动并发处理，失败项值为 null。
 */
export async function decryptBatch(encPaths, mimeType = 'image/webp') {
  const entries = await Promise.all(
    encPaths.map(async (p) => {
      try {
        return [p, await decryptToUrl(p, mimeType)]
      } catch (e) {
        console.warn('解密失败:', p, e.message)
        return [p, null]
      }
    }),
  )
  return Object.fromEntries(entries)
}
