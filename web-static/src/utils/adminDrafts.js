// Compare saved meaning, independent of object insertion order.
export function sameContent(left, right) {
  if (Object.is(left, right)) return true
  if (!left || !right || typeof left !== 'object' || typeof right !== 'object') return false
  if (Array.isArray(left) || Array.isArray(right)) {
    return Array.isArray(left) && Array.isArray(right) && left.length === right.length && left.every((value, index) => sameContent(value, right[index]))
  }
  const keys = Object.keys(left)
  return keys.length === Object.keys(right).length && keys.every(key => Object.hasOwn(right, key) && sameContent(left[key], right[key]))
}

function sameGalleryField(field, left, right) {
  return field === 'tags' && Array.isArray(left) && Array.isArray(right)
    ? sameContent([...new Set(left)].sort(), [...new Set(right)].sort())
    : sameContent(left, right)
}

export function recordDraft(kind, data, original = {}, source = {}) {
  const draft = { ...data }
  if (kind === 'gallery') {
    for (const [field, value] of Object.entries(draft)) {
      const inherited = source[field] ?? (field === 'hidden' ? false : field === 'tags' ? [] : '')
      if (!Object.hasOwn(original, field) && sameGalleryField(field, value, inherited)) delete draft[field]
      else if (Object.hasOwn(original, field) && sameGalleryField(field, value, original[field])) draft[field] = original[field]
    }
  } else if (kind === 'book') {
    for (const field of ['ID', 'sid']) if (typeof draft[field] === 'string') draft[field] = draft[field].trim()
  }
  return draft
}

export function serviceChanges(values, original) {
  const normalized = (key, value) => key === 'model' && value === '' ? null : value
  return Object.fromEntries(Object.entries(values).map(([key, value]) => [key, normalized(key, value)])
    .filter(([key, value]) => !sameContent(value, normalized(key, original[key]))))
}

export function scheduleDraft(schedule) {
  const numeric = value => typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value)) ? Number(value) : value
  return { enabled: schedule.enabled, hour: numeric(schedule.hour), minute: numeric(schedule.minute), timezone: schedule.timezone }
}
