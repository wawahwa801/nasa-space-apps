// Optional QA: NODE_PATH=/path/to/node_modules TEST_BASE_URL=http://127.0.0.1:3012 node scripts/check-demo-variation-ui.mjs
// Controlled responses exercise cancellation/failure races without a model service.
import { createRequire } from 'node:module';
import assert from 'node:assert/strict';
const { chromium } = createRequire(import.meta.url)('playwright');
const base = process.env.TEST_BASE_URL || 'http://127.0.0.1:3012';
const pixel = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=';
const info = {model:{id:42},runs:[{id:'run-a', label:'Demo fuel', values:{n0:1.123456789, n1:25}}],
  numeric:[{key:'n0',label:'Pressure',unit:'kPa',min:1.123456789,max:200.987654321,step:'any'},
           {key:'n1',label:'Temperature',unit:'°C',min:20,max:30,step:'any'}],categories:[]};
const browser = await chromium.launch({headless:true});
try {
  const page = await browser.newPage({viewport:{width:1200,height:1000}});
  const calls=[];
  await page.route('**/hybrid/runs',r=>r.fulfill({json:info}));
  await page.route('**/hybrid/environment',r=>r.fulfill({json:{source:0,
    rooms:[{id:'room-a',name:'Demo room',x:0,y:0,fuel:true}],edges:[]}}));
  await page.route('**/hybrid/compare?*',async route=>{
    assert.equal(route.request().headers()['x-model-id'],'42','Selected prediction pins the registry model selected by /runs');
    const q=Object.fromEntries(new URL(route.request().url()).searchParams); calls.push(q);
    try { await route.fulfill({json:{hybrid:pixel,cnn:pixel,retrieval:pixel,conditions:`Pressure ${q.n0}; temperature ${q.n1}`,model_note:'Fixture prediction'}}); } catch { /* An expected cancellation can close this request. */ }
  });
  await page.goto(base);
  const image=page.locator('.demo-flame-image');
  const caption=page.locator('.demo-frame-conditions');
  await image.waitFor();
  await page.waitForTimeout(750);
  assert.equal(await page.getByRole('button',{name:/flame animation|flame variation/i}).count(),0);
  assert.equal(await image.evaluate(e=>getComputedStyle(e).animationName),'none');
  const before=calls.length, held=await caption.textContent();
  await page.waitForTimeout(1000);
  assert.equal(calls.length,before,'Idle preview makes no variation requests');
  assert.equal(await caption.textContent(),held,'Selected prediction stays still');
  await page.locator('#model-parameters input[type=number]').first().fill('80');
  await page.waitForFunction(()=>document.querySelector('.demo-frame-conditions')?.textContent.includes('Pressure 80;'));
  assert.equal(calls.length,before+1,'One selected prediction is requested after an edit');
  assert.equal(+calls.at(-1).n0,80);
  assert.equal(+calls.at(-1).n1,25);
  await page.emulateMedia({reducedMotion:'reduce'});
  const stable=await caption.textContent();
  await page.waitForTimeout(500);assert.equal(await caption.textContent(),stable);
  for(const width of [390,320]){await page.setViewportSize({width,height:1000});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  console.log('PASS: static selected flame, no variation requests/playback, input refresh, model pinning, reduced motion and mobile');
} finally { await browser.close(); }
