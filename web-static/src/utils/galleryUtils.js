export const exTypeList = [
  { name: 'Doujinshi',  color: 'red' },
  { name: 'Manga',      color: 'orange' },
  { name: 'Artist CG',  color: 'yellow' },
  { name: 'Game CG',    color: 'green' },
  { name: 'Western',    color: 'gold' },
  { name: 'Non-H',      color: 'lightblue' },
  { name: 'Image Set',  color: 'blue' },
  { name: 'Cosplay',    color: 'purple' },
  { name: 'Asian Porn', color: 'pink' },
  { name: 'Misc',       color: 'gray' },
]

export const exTypeDotColors = {
  'Doujinshi':  '#a22',
  'Manga':      '#d67e22',
  'Artist CG':  '#d6a922',
  'Game CG':    '#4caf50',
  'Western':    '#d4af37',
  'Non-H':      '#4ca3dd',
  'Image Set':  '#2a78d6',
  'Cosplay':    '#7e57c2',
  'Asian Porn': '#d81b60',
  'Misc':       '#757575',
}

export const exTypeClassMap = Object.fromEntries(exTypeList.map(t => [t.name, t.color]))

export function formatTimestamp(timestamp) {
  if (!timestamp) return ''
  const ts = typeof timestamp === 'string' ? parseInt(timestamp) : timestamp
  if (isNaN(ts)) return ''
  const date = ts.toString().length === 10 ? new Date(ts * 1000) : new Date(ts)
  if (isNaN(date.getTime())) return ''
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).replace(/\//g, '-')
}

export function enrichTags(tags, translationData) {
  if (!translationData || !Array.isArray(tags)) return []
  const result = []
  for (const tag of tags) {
    if (typeof tag !== 'string' || !tag.includes(':')) continue
    const [namespace, value] = tag.split(':', 2)
    const detail = translationData.data?.find(item => item.namespace === namespace)?.data?.[value]
    result.push({
      tag, namespace, value,
      tag_cn: detail?.name || '',
      intro:  detail?.intro || '',
      links:  detail?.links || '',
    })
  }
  return result
}
