import test from 'node:test'
import assert from 'node:assert/strict'
import {readTranslationResponse,scaleOcrResults} from '../web-static/src/utils/translationApi.js'

test('OCR transport reports HTML proxy errors instead of returning an empty success object',async()=>{
  for(const status of [413,429,500,502,504]){
    await assert.rejects(readTranslationResponse(new Response('<html>failure</html>',{status})),error=>!error.message.includes('map')&&error.message.length>5)
  }
  await assert.rejects(readTranslationResponse(new Response('<html>failure</html>',{status:200})),/格式异常/)
  await assert.rejects(readTranslationResponse(new Response(JSON.stringify({error:'安全的服务错误'}),{status:503})),/安全的服务错误/)
  await assert.rejects(readTranslationResponse(new Response('unauthorized',{status:401})),error=>error.auth===true)
})

test('OCR responses require a results array and valid coordinates at every image scale',()=>{
  for(const data of [{},null,{results:null},{results:[{text:'a'}]},{results:[{text:'a',bbox:[1,2,3]}]}]){
    assert.throws(()=>scaleOcrResults(data,2),/识别/)
  }
  assert.deepEqual(scaleOcrResults({results:[]}),[])
  const response={results:[{text:'日本語',confidence:1,bbox:[1,2,3,4],polygon:[[1,2],[3,4]]}]}
  assert.deepEqual(scaleOcrResults(response,2)[0].bbox,[2,4,6,8])
  assert.deepEqual(scaleOcrResults(response,2)[0].polygon,[[2,4],[6,8]])
  assert.deepEqual(response.results[0].bbox,[1,2,3,4])
  assert.throws(()=>scaleOcrResults({results:[{text:'a',bbox:[1,2,3,4],polygon:[null]}]}),/坐标/)
})
