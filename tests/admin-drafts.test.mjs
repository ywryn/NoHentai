import test from 'node:test'
import assert from 'node:assert/strict'
import {sameContent,recordDraft,serviceChanges,scheduleDraft} from '../web-static/src/utils/adminDrafts.js'

test('gallery edits reverted to inherited values leave no override or dirty state', () => {
  const source={title:'source',category:'Manga',tags:['artist:a','female:b']}
  assert.deepEqual(recordDraft('gallery',{title:'source',category:'Manga',hidden:false,tags:['female:b','artist:a']},{},source),{})
  assert.deepEqual(recordDraft('gallery',{title:'changed'},{},source),{title:'changed'})
  assert.deepEqual(recordDraft('gallery',{title:'source',title_jpn:''},{},source),{})
})

test('existing override ownership remains meaningful even when its text equals source', () => {
  const original={title:'source',tags:['artist:a','female:b']},source={title:'source'}
  assert.ok(!sameContent(recordDraft('gallery',{},original,source),original))
  assert.deepEqual(recordDraft('gallery',{tags:['female:b','artist:a','artist:a'],title:'source'},original,source),original)
  assert.ok(sameContent({b:2,a:1},{a:1,b:2}))
  assert.ok(!sameContent({hidden:false},{}))
})

test('book normalization matches saved IDs without hiding real text changes', () => {
  const original={ID:'book',sid:'123','书名':'Title'}
  assert.ok(sameContent(recordDraft('book',{...original,ID:' book ',sid:'123 '}),original))
  assert.ok(!sameContent(recordDraft('book',{...original,'书名':'Title '}),original))
})

test('service saves include only actual public changes and preserve inheritance', () => {
  const original={model:null,jsonMode:null,LLM_TIMEOUT_SECONDS:90}
  assert.deepEqual(serviceChanges({LLM_TIMEOUT_SECONDS:90,jsonMode:null,model:''},original),{})
  assert.deepEqual(serviceChanges({...original,LLM_TIMEOUT_SECONDS:100},original),{LLM_TIMEOUT_SECONDS:100})

})

test('schedule numbers round-trip but blank input stays invalid instead of becoming midnight', () => {
  assert.ok(sameContent(scheduleDraft({enabled:true,hour:'04',minute:'00',timezone:'UTC'}),{enabled:true,hour:4,minute:0,timezone:'UTC'}))
  assert.equal(scheduleDraft({hour:'',minute:0}).hour,'')
})

test('service drafts compare visible values including cleared secrets', () => {
  const original={model:'inherited-model',LLM_API_KEY:'configured-key'}
  assert.deepEqual(serviceChanges({...original},original),{})
  assert.deepEqual(serviceChanges({...original,LLM_API_KEY:''},original),{LLM_API_KEY:''})
})
