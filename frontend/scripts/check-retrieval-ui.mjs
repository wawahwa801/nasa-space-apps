// Optional browser regression check: install Playwright separately and run with
// NODE_PATH=/path/to/node_modules TEST_BASE_URL=http://127.0.0.1:3001 node scripts/check-retrieval-ui.mjs
import { createRequire } from 'node:module';
import assert from 'node:assert/strict';
import fs from 'node:fs';
// Resolve the optional QA dependency from NODE_PATH without adding it to the app.
const { chromium } = createRequire(import.meta.url)('playwright');
const base = process.env.TEST_BASE_URL || 'http://127.0.0.1:3001';
const data = JSON.parse(fs.readFileSync(new URL('../public/flames/flex2/index.json',import.meta.url)));

(async () => {
  const browser = await chromium.launch({ headless:true });
  try {
    const page = await browser.newPage({ viewport:{width:1440,height:1000} });
    const errors=[],failedAssets=[];let modelCalls=0;
    page.on('pageerror',e=>errors.push(e.message));
    page.on('response',r=>{if(r.url().includes('/flames/')&&r.status()>=400)failedAssets.push(r.url());});
    await page.route(/https?:\/\/(localhost|127\.0\.0\.1):(5000|5050|5051)\//,route=>{modelCalls++;return route.abort();});
    await page.goto(base);await page.waitForFunction(()=>Boolean(window.FireDashboard));
    assert.equal(await page.getByRole('heading',{level:1}).count(),1);
    if (!await page.locator('#parameters').isVisible()) await page.locator('.topbar .panel-toggle').click();
    await page.getByRole('spinbutton',{name:'Oxygen concentration value',exact:true}).fill('24');
    await page.getByRole('button',{name:'Apply parameters',exact:false}).click();
    if (!await page.locator('#chat-panel').isVisible()) await page.getByRole('button',{name:'Scenario chat',exact:true}).click();
    await page.locator('#scenario-prompt').fill('Retrieval integration check');
    await page.getByRole('button',{name:'Save scenario note',exact:true}).click();
    await page.getByText('Retrieval integration check',{exact:true}).waitFor();

    const retrievalTab=page.getByRole('tab',{name:'Feature retrieval',exact:true});
    const flameTab=page.getByRole('tab',{name:'Flame simulation',exact:true});
    await retrievalTab.click();
    const result=page.locator('[aria-label="Retrieved flame result"]');
    await result.waitFor();
    assert.equal(await page.getByRole('button',{name:'Parameters',exact:true}).count(),0);
    assert.equal(await page.locator('#flame-panel').isVisible(),false);
    const image=()=>result.getByRole('img');
    await image().scrollIntoViewIfNeeded();await page.waitForFunction(()=>document.querySelector('[aria-label="Retrieved flame result"] img')?.naturalWidth===256);
    const initialRun=await result.getAttribute('data-run-id');
    const pressure=page.getByRole('spinbutton',{name:'Chamber pressure value',exact:true});
    await pressure.fill('0');assert.equal(await pressure.getAttribute('aria-invalid'),'true');
    assert.equal(await result.getAttribute('data-run-id'),initialRun);
    await page.getByRole('button',{name:'Reset retrieval conditions'}).click();
    assert.equal(await pressure.getAttribute('aria-invalid'),'false');
    const temp=page.getByRole('spinbutton',{name:'Chamber temperature value',exact:true});
    await temp.fill('');assert.equal(await temp.getAttribute('aria-invalid'),'true');
    await page.getByRole('button',{name:'Reset retrieval conditions'}).click();
    assert.equal(await temp.getAttribute('aria-invalid'),'false');

    const seen=await page.evaluate(async()=>{
      const input=document.getElementById('retrieval-pressure_kpa'),ids=new Set();
      const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
      for(let i=0;i<32;i++){
        setter.call(input,Number(input.min)+(Number(input.max)-Number(input.min))*i/31);
        input.dispatchEvent(new Event('input',{bubbles:true}));
        await new Promise(resolve=>setTimeout(resolve,20));
        ids.add(document.querySelector('[aria-label="Retrieved flame result"]').dataset.runId);
      }return ids.size;
    });
    assert.ok(seen>1,'Continuous dragging must retrieve different experiments');
    for (const record of data.records) {
      await page.locator('#retrieval-run').selectOption(record.id);
      await page.waitForFunction(id=>document.querySelector('[aria-label="Retrieved flame result"]').dataset.runId===id,record.id);
      assert.equal(await page.locator('#retrieval-fuel').inputValue(),record.fuel);
      await image().scrollIntoViewIfNeeded();await page.waitForFunction(()=>document.querySelector('[aria-label="Retrieved flame result"] img')?.naturalWidth===256);
      assert.ok((await result.textContent()).includes('Exact recorded conditions'));
    }
    await page.locator('#retrieval-fuel').selectOption('Decane');
    await page.getByRole('spinbutton',{name:'Chamber temperature value',exact:true}).fill('26');
    const saved=await page.locator('#retrieval-temperature_c').inputValue();
    await flameTab.click();
    assert.equal(await page.getByRole('spinbutton',{name:'Oxygen concentration value',exact:true}).inputValue(),'24');
    assert.equal(await page.getByText('Retrieval integration check',{exact:true}).count(),1);
    await page.locator('.parameter-panel .unit-toggle').click();
    await page.waitForFunction(()=>document.querySelector('input[aria-label="Temperature value"]').value==='295.15');
    assert.equal(await page.getByRole('spinbutton',{name:'Temperature value',exact:true}).inputValue(),'295.15');
    await page.getByRole('spinbutton',{name:'Temperature value',exact:true}).fill('310.15');
    await page.locator('.parameter-panel .unit-toggle').click();
    await page.waitForFunction(()=>document.querySelector('input[aria-label="Temperature value"]').value==='37');
    assert.equal(await page.getByRole('spinbutton',{name:'Temperature value',exact:true}).inputValue(),'37');
    await retrievalTab.click();assert.equal(await page.locator('#retrieval-temperature_c').inputValue(),saved);
    await retrievalTab.focus();await page.keyboard.press('ArrowLeft');
    assert.equal(await flameTab.getAttribute('aria-selected'),'true');
    await page.keyboard.press('End');assert.equal(await retrievalTab.getAttribute('aria-selected'),'true');
    await page.getByRole('link',{name:'NASA data',exact:true}).click();
    assert.equal(await flameTab.getAttribute('aria-selected'),'true');
    await page.locator('#nasa-comparison').waitFor({state:'visible'});
    const downloadEvent=page.waitForEvent('download');
    await page.getByRole('button',{name:'Export results',exact:true}).click();
    const download=await downloadEvent;
    const exported=JSON.parse(fs.readFileSync(await download.path(),'utf8'));
    assert.equal(exported.inputs.o2_pct,24);
    assert.equal(exported.inputs.internal_temp_c,37);
    await page.getByRole('button',{name:'Load example',exact:true}).click();
    await page.waitForFunction(()=>Number(document.getElementById('oxygen').value)===Number(window.EXAMPLE_INPUT.o2_pct));
    await retrievalTab.click();await page.getByRole('button',{name:'New scenario',exact:true}).click();
    await page.waitForFunction(()=>document.getElementById('retrieval-fuel')?.value==='Decane');
    assert.equal(await temp.inputValue(),data.fuels[0].defaults.temperature_c.toFixed(2));
    await result.scrollIntoViewIfNeeded();
    await page.screenshot({path:'/tmp/dashboard-retrieval-desktop.png',fullPage:true});
    await result.locator('summary').click();
    assert.equal(await page.getByRole('link',{name:'Open NASA FLEX-2 dataset',exact:false}).getAttribute('href'),data.source_url);
    assert.ok((await page.getByRole('link',{name:'Open this prepared image',exact:false}).getAttribute('href')).startsWith('/flames/flex2/'));
    for (const width of [1024,768,600,390,320]) {
      await page.setViewportSize({width,height:900});
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Retrieval overflow at ${width}`);
      await flameTab.click();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Simulation overflow at ${width}`);
      await retrievalTab.click();
    }
    await page.screenshot({path:'/tmp/dashboard-retrieval-mobile.png',fullPage:true});
    assert.equal(modelCalls,0);assert.deepEqual(failedAssets,[]);assert.deepEqual(errors,[]);

    // Failed library/image requests have explicit recoverable UI states.
    const failure=await browser.newPage({viewport:{width:1000,height:900}});
    let failLibrary=true,failImage=true;
    await failure.route('**/flames/flex2/index.json',route=>failLibrary?route.fulfill({status:503,body:'Unavailable'}):route.continue());
    await failure.route('**/flames/flex2/A109D04.png*',route=>failImage?route.abort():route.continue());
    await failure.goto(base);await failure.getByRole('tab',{name:'Feature retrieval'}).click();
    await failure.getByRole('heading',{name:'Flame library unavailable'}).waitFor();
    failLibrary=false;await failure.getByRole('button',{name:'Retry loading library'}).click();
    await failure.getByText('This recorded image could not load.',{exact:true}).waitFor();
    failImage=false;await failure.getByRole('button',{name:'Retry image',exact:true}).click();
    await failure.waitForFunction(()=>document.querySelector('[aria-label="Retrieved flame result"] img')?.naturalWidth===256);
    await failure.close();
    console.log(JSON.stringify({verifiedRuns:data.records.length,liveRetrievedRuns:seen,modelServiceRequests:modelCalls,browserErrors:errors,checks:'tabs, state, reset, validation, source links, 24 images, live input, keyboard, mobile, retry states'}));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
