export async function readTranslationResponse(response) {
  const data = await response.json().catch(() => null)
  if (response.status === 401) {
    const error = new Error('密码已失效')
    error.auth = true
    throw error
  }
  const message = data && typeof data.error === 'string' ? data.error : null
  if (!response.ok) {
    const hints = {
      413: '图片请求过大，请缩小图片后重试',
      429: '请求过于频繁，请稍后重试',
      500: '服务器处理请求失败，请稍后重试',
      502: '识别或翻译服务暂时不可用，请稍后重试',
      503: '识别或翻译服务暂时不可用，请稍后重试',
      504: '识别或翻译请求超时，请稍后重试',
    }
    throw new Error(message || hints[response.status] || `请求失败（HTTP ${response.status}）`)
  }
  if (message) throw new Error(message)
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('服务返回格式异常，请重试')
  return data
}

export function scaleOcrResults(data, scale = 1) {
  if (!Array.isArray(data?.results)) throw new Error('识别服务未返回有效结果，请重试或切换 OCR 服务')
  if (!Number.isFinite(scale) || scale <= 0) throw new Error('图片尺寸无效，请重新加载图片')
  return data.results.map(region => {
    if (!region || typeof region.text !== 'string' || !Array.isArray(region.bbox) || region.bbox.length !== 4 || !region.bbox.every(Number.isFinite)) {
      throw new Error('识别结果缺少有效坐标，请重试或切换 OCR 服务')
    }
    if (region.polygon != null && (!Array.isArray(region.polygon) || !region.polygon.every(point => Array.isArray(point) && point.length === 2 && point.every(Number.isFinite)))) {
      throw new Error('识别结果的坐标格式异常，请重试或切换 OCR 服务')
    }
    return { ...region, bbox: region.bbox.map(value => value * scale), polygon: region.polygon?.map(([x, y]) => [x * scale, y * scale]) ?? null }
  })
}
