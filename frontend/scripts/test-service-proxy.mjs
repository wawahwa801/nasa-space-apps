import {test} from 'node:test';
import assert from 'node:assert/strict';
import {proxyService} from '../lib/service-proxy.js';

test('hybrid proxy preserves model pin, query and simulation body', async () => {
 const originalFetch=globalThis.fetch, previous=process.env.BACKEND_URL;
 process.env.BACKEND_URL='http://backend.example';
 try {
  globalThis.fetch=async (url, options)=>{
   assert.equal(url.href,'http://backend.example/api/hybrid/simulate?test=1');
   assert.equal(options.headers['X-Model-ID'],'42');
   assert.equal(options.body,'{"controls":{}}');
   return Response.json({model:{id:42,source:'s3'}});
  };
  const request=new Request('http://frontend/hybrid/simulate?test=1',{
   method:'POST',headers:{'X-Model-ID':'42'},body:'{"controls":{}}'});
  const response=await proxyService(request,'hybrid/simulate','BACKEND_URL','http://127.0.0.1:5000');
  assert.equal(response.status,200);
  assert.equal((await response.json()).model.source,'s3');
  assert.equal(response.headers.get('Cache-Control'),'no-store');
 } finally {
  globalThis.fetch=originalFetch;
  if(previous===undefined)delete process.env.BACKEND_URL;else process.env.BACKEND_URL=previous;
 }
});

test('upstream failure stays unavailable without a local-model retry', async () => {
 const originalFetch=globalThis.fetch;let calls=0;
 try {
  globalThis.fetch=async ()=>{calls++;throw Error('private server details');};
  const response=await proxyService(new Request('http://frontend/hybrid/runs'),
   'hybrid/runs','BACKEND_URL','http://127.0.0.1:5000');
  assert.equal(response.status,503);assert.equal(calls,1);
  assert.ok(!(await response.text()).includes('private server details'));
 } finally {globalThis.fetch=originalFetch;}
});
