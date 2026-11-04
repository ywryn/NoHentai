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
