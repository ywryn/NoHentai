const baseUrl = import.meta.env.BASE_URL

let _galleriesPromise = null
let _translationsPromise = null

export function loadGalleries() {
  if (!_galleriesPromise) {
    _galleriesPromise = fetch(`${baseUrl}data/galleries.json`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .catch(e => { _galleriesPromise = null; console.error('loadGalleries:', e); return [] })
  }
  return _galleriesPromise
}

export function loadTranslations() {
  if (!_translationsPromise) {
    _translationsPromise = fetch(`${baseUrl}data/translations.json`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .catch(e => { _translationsPromise = null; console.error('loadTranslations:', e); return null })
  }
  return _translationsPromise
}
