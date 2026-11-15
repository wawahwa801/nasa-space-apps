// Optional QA: NODE_PATH=/path/to/node_modules TEST_BASE_URL=http://127.0.0.1:3012 node scripts/check-demo-variation-ui.mjs
// Controlled responses exercise cancellation/failure races without a model service.
import { createRequire } from 'node:module';
import assert from 'node:assert/strict';
const { chromium } = createRequire(import.meta.url)('playwright');
const base = process.env.TEST_BASE_URL || 'http://127.0.0.1:3012';
const pixel = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=';
const info = {runs:[{id:'run-a', label:'Demo fuel', values:{n0:1.123456789, n1:25}}],
  numeric:[{key:'n0',label:'Pressure',unit:'kPa',min:1.123456789,max:200.987654321,step:'any'},
           {key:'n1',label:'Temperature',unit:'°C',min:20,max:30,step:'any'}],categories:[]};
const browser = await chromium.launch({headless:true});
try {
  const page = await browser.newPage({viewport:{width:1200,height:1000}});
  const calls=[]; let delay=0, fail=false;
  await page.route('**/hybrid/runs',r=>r.fulfill({json:info}));
  await page.route('**/hybrid/compare?*',async route=>{
    const q=Object.fromEntries(new URL(route.request().url()).searchParams); calls.push(q);
    if(delay) await new Promise(resolve=>setTimeout(resolve,delay));
    try { await route.fulfill(fail ? {status:503,json:{error:'Fixture service unavailable'}} : {json:{hybrid:pixel,cnn:pixel,retrieval:pixel,conditions:`Pressure ${q.n0}; temperature ${q.n1}`,model_note:'Fixture prediction'}}); } catch { /* An expected cancellation can close this request. */ }
  });
  await page.goto(base);
  const paused=page.getByRole('button',{name:'Pause variations',exact:true});
  const slider=page.locator('.demo-variation-controls input[type=range]');
  const range=page.locator('.demo-variation-controls input[type=number]');
  await paused.waitFor();
  assert.equal(await page.getByRole('button',{name:'Generate variations',exact:true}).count(),0);
  assert.equal(await page.locator('.demo-flame-image').evaluate(e=>getComputedStyle(e).animationName),'none');
  const visited=await slider.evaluate(e=>new Promise(resolve=>{const values=new Set();const timer=setInterval(()=>values.add(e.value),30);setTimeout(()=>{clearInterval(timer);resolve([...values]);},450);}));
  assert.ok(visited.length>=3,'Playback must advance quickly without a click');
  await paused.click();
  const held=await slider.inputValue(); await page.waitForTimeout(900); assert.equal(await slider.inputValue(),held);
  await range.fill('20'); calls.length=0; await paused.waitFor();
  assert.equal(calls.length,8);
  for(const q of calls){assert.equal(q.run,'run-a');assert.ok(+q.n0>=info.numeric[0].min&&+q.n0<=info.numeric[0].max);assert.ok(+q.n1>=20&&+q.n1<=30);}
  await paused.click(); await slider.fill('7'); assert.equal(await slider.inputValue(),'7');
  await page.waitForTimeout(500);assert.equal(calls.length,8,'Playback uses cached frames');
  await page.getByRole('button',{name:'Selected prediction',exact:true}).click();assert.equal(await slider.count(),0);
  assert.equal(await page.locator('.demo-flame-image').evaluate(e=>getComputedStyle(e).animationName),'none');
  // Cancel an automatically started delayed sweep; late answers cannot restore it.
  delay=400; await range.fill('10'); await page.getByRole('button',{name:'Cancel animation',exact:true}).click();
  await page.waitForTimeout(500); assert.equal(await slider.count(),0);
  // Input changes cancel the old sweep, then automatically prepare the new one.
  await page.getByRole('button',{name:'Resume animation',exact:true}).click();
  await page.getByRole('button',{name:'Cancel animation',exact:true}).waitFor();
  await page.locator('#model-parameters input[type=number]').first().fill('80');
  await paused.waitFor(); delay=0;
  fail=true;await range.fill('11');await page.getByText(/Could not generate variations: Fixture service unavailable/).waitFor();
  assert.equal(await slider.count(),0);fail=false;await page.getByRole('button',{name:'Retry animation',exact:true}).click();await paused.waitFor();
  await range.fill('0');await page.getByText('Choose a range from 1% to 20%.').waitFor();
  await page.emulateMedia({reducedMotion:'reduce'});await range.fill('5');await slider.waitFor();
  assert.equal(await paused.count(),0);
  const frame=await slider.inputValue();await page.waitForTimeout(900);assert.equal(await slider.inputValue(),frame);
  await slider.fill('1');
  for(const width of [390,320]){await page.setViewportSize({width,height:1000});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  console.log('PASS: automatic fast playback, no flicker/generate button, bounded cached queries, pause/cancel/retry, input refresh, reduced motion and mobile');
} finally { await browser.close(); }
