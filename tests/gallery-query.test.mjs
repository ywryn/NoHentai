import test from 'node:test'
import assert from 'node:assert/strict'
import {parseQuery,parsedTerms,removeQueryTerm} from '../web-static/src/utils/gallerySearch.js'

test('removing a search chip uses its original quoted source range', () => {
  for (const q of ['female:"sole female$"', 'a:"asanagi$"', '"中文 短语"', '-f:"full color$"']) {
    const term=parsedTerms(parseQuery(q))[0]
    assert.equal(removeQueryTerm(q,term),'')
  }
  const q='title:漫画 female:"sole female$", ~romance'
  const terms=parsedTerms(parseQuery(q))
  const remaining=removeQueryTerm(q,terms.find(t=>t.namespace==='female'))
  assert.deepEqual(parsedTerms(parseQuery(remaining)).map(t=>t.value),['漫画','romance'])
  const repeated='f:"sole female$" f:"sole female$"'
  assert.equal(parsedTerms(parseQuery(removeQueryTerm(repeated,parsedTerms(parseQuery(repeated))[1]))).length,1)
})

test('autocomplete replaces the token at the caret and preserves following conditions', async () => {
  const {activeToken, applySuggestion} = await import('../web-static/src/utils/gallerySearch.js')
  const query='f:chi -other:webtoon title:book'
  assert.equal(activeToken(query,4).text,'f:chi')
  assert.equal(applySuggestion(query,{namespace:'female',value:'chinese dress'},4),'female:"chinese dress$" -other:webtoon title:book')
  assert.equal(activeToken('f:test ').text,'')
  assert.equal(activeToken('title:"full color"',12).text,'title:"full color"')
})

test('gallery IDs and links share normalization without losing chip source ranges', () => {
  for (const query of ['123','https://exhentai.org/g/123/abcde/','https://e-hentai.org/g/123/abcde/?p=2']) {
    const term=parsedTerms(parseQuery(query))[0]
    assert.equal(term.field,'gid');assert.equal(term.value,'123')
    assert.equal(removeQueryTerm(query,term),'')
  }
})
