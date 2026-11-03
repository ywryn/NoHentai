import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { validateOverrides, mergeGalleries, validateDaily, validateTranslate } from '../shared/adminData.js'
const galleries = [{ gid: 123, title: '来源标题', tags: ['artist:test'], category: 'Manga' }]
const daily = JSON.parse(readFileSync(new URL('../config/daily.json', import.meta.url)))

test('source refresh preserves overrides, reset restores source, and empty arrays really clear tags', () => {
  const patches = { 123: { title: '人工标题', tags: [] } }
  assert.equal(mergeGalleries(galleries, patches)[0].title, '人工标题')
  const refreshed = [{ ...galleries[0], title: '来源已更新' }]
  assert.equal(mergeGalleries(refreshed, patches)[0].title, '人工标题')
  assert.equal(mergeGalleries(refreshed, {})[0].title, '来源已更新')
  assert.deepEqual(mergeGalleries(refreshed, patches)[0].tags, [])
  assert.deepEqual(mergeGalleries(galleries, { 123: { hidden: true } }), [])
  assert.equal(mergeGalleries(galleries, { 123: { hidden: true } }, { includeHidden: true }).length, 1)
  assert.throws(() => validateOverrides({ 123: { gid: 456 } }), /不允许/)
  assert.throws(() => validateOverrides(JSON.parse('{"__proto__":{"title":"bad"}}')), /ID/)
  assert.throws(() => mergeGalleries([...galleries, ...galleries], {}), /重复/)
})

test('configuration validation rejects secret leakage, unknown fields and invalid search rules', () => {
  assert.deepEqual(validateDaily(daily), daily)
  for (const patch of [{ cutoffDays: 0 }, { categories: 0 }, { minPages: 900, maxPages: 800 }, { minRating: 1 }, { keyword: 123 }, { apiKey: 'must-not-commit' }]) {
    assert.throws(() => validateDaily([{ ...daily[0], ...patch }]))
  }
  assert.throws(() => validateDaily([daily[0], daily[0]]), /重复/)
  assert.throws(() => validateTranslate({ model: 'test', defaultOcr: 'google', jsonMode: null, apiKey: 'secret' }), /密钥/)
  assert.throws(() => validateTranslate({ model: 'test', defaultOcr: 'unknown', jsonMode: false }), /OCR/)

})


test('tag suggestions respect namespace aliases in public and admin search', async () => {
  const {suggestTags} = await import('../web-static/src/utils/gallerySearch.js')
  const entries=['artist','female'].map(namespace=>({namespace,data:{test:{name:'测试'}}}))
  assert.deepEqual(suggestTags('f:te',entries).map(item=>item.namespace),['female'])
  assert.deepEqual(suggestTags('female:测试',entries).map(item=>item.namespace),['female'])
  assert.deepEqual(suggestTags('title:te',entries),[])
})

test('legacy daily display labels are ignored while real conditions are preserved', () => {
  assert.deepEqual(validateDaily(daily.map(group => ({ ...group, filters: ['obsolete'] }))), daily)
})
