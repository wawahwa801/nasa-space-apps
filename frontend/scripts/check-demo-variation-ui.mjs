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
  const calls=[]; let delay=0;
  await page.route('**/hybrid/runs',r=>r.fulfill({json:info}));
  await page.route('**/hybrid/environment',r=>r.fulfill({json:{source:0,
    rooms:[{id:'room-a',name:'Demo room',x:0,y:0,fuel:true}],edges:[]}}));
  await page.route('**/hybrid/compare?*',async route=>{
    assert.equal(route.request().headers()['x-model-id'],'42','All prediction frames pin the registry model selected by /runs');
    const q=Object.fromEntries(new URL(route.request().url()).searchParams); calls.push(q);
    if(delay) await new Promise(resolve=>setTimeout(resolve,delay));
    try { await route.fulfill({json:{hybrid:pixel,cnn:pixel,retrieval:pixel,conditions:`Pressure ${q.n0}; temperature ${q.n1}`,model_note:'Fixture prediction'}}); } catch { /* An expected cancellation can close this request. */ }
  });
  await page.goto(base);
  const paused=page.getByRole('button',{name:'Pause flame animation',exact:true});
  const resumed=page.getByRole('button',{name:'Resume flame animation',exact:true});
  const image=page.locator('.demo-flame-image');
  const caption=page.locator('.demo-frame-conditions');
  await paused.waitFor();
  assert.equal(await page.locator('.demo-variation-controls').count(),0);
  assert.equal(await page.getByText('Selected prediction',{exact:true}).count(),0);
  assert.equal(await image.evaluate(e=>getComputedStyle(e).animationName),'none');
  const visited=await caption.evaluate(e=>new Promise(resolve=>{const values=new Set();const timer=setInterval(()=>values.add(e.textContent),30);setTimeout(()=>{clearInterval(timer);resolve([...values]);},450);}));
  assert.ok(visited.length>=3,'Frames still play quickly after removing the controls');
  const before=calls.length;await paused.click();const held=await caption.textContent();
  await page.waitForTimeout(600);assert.equal(await caption.textContent(),held);assert.equal(calls.length,before);
  await resumed.press('Enter');await paused.waitFor();await paused.press('Space');await resumed.waitFor();
  // Edits cancel the paused sweep and automatically refresh to the new inputs.
  delay=100;await page.locator('#model-parameters input[type=number]').first().fill('80');await paused.waitFor();
  const recent=calls.slice(-8);assert.equal(recent.length,8);
  for(const q of recent){assert.equal(q.run,'run-a');assert.ok(+q.n0>=info.numeric[0].min&&+q.n0<=info.numeric[0].max);assert.ok(+q.n1>=20&&+q.n1<=30);}
  // Rapid edits abort old requests; only the last controls get an animation.
  await page.locator('#model-parameters input[type=number]').first().fill('90');
  await page.waitForTimeout(350);await page.locator('#model-parameters input[type=number]').first().fill('100');await paused.waitFor();
  assert.ok(calls.slice(-8).every(q=>Math.abs(+q.n0-100)<=10.01));
  delay=0;await page.emulateMedia({reducedMotion:'reduce'});
  const next=page.getByRole('button',{name:'Next flame variation',exact:true});await next.waitFor();
  const frame=await caption.textContent();await page.waitForTimeout(500);assert.equal(await caption.textContent(),frame);
  await next.click();assert.notEqual(await caption.textContent(),frame);
  for(const width of [390,320]){await page.setViewportSize({width,height:1000});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  console.log('PASS: controls block removed, cached automatic frames, image click/keyboard pause, input refresh/cancellation, reduced-motion advance and mobile');
} finally { await browser.close(); }
