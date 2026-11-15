// Optional real-browser check. Requires playwright and a running local lab.
// NODE_PATH=/path/to/playwright/node_modules node ml/check_flex2_ui.cjs
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const base = process.env.TEST_BASE_URL || 'http://127.0.0.1:5051';
(async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:1000}});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    let predictions=0;
    page.on('request',request=>{if(request.url().includes('/flex2/api/predict'))predictions++;});
    // Slower responses exercise the latest-pending-input queue while dragging.
    await page.route('**/flex2/api/predict?*',async route=>{
      const response=await route.fetch();await new Promise(resolve=>setTimeout(resolve,120));
      await route.fulfill({response});
    });
    await page.goto(base+'/');await page.waitForURL('**/flex2/');
    await page.locator('#flame').waitFor({state:'visible'});
    assert.equal(await page.locator('#retrieval').getAttribute('aria-pressed'),'true');
    await page.screenshot({path:'/tmp/flex2-default.png',fullPage:true});
    await page.locator('#cnn').click();
    await page.waitForFunction(()=>shownVersion===renderVersion&&!inFlight&&!desired);
    assert.equal(await page.locator('#flame').evaluate(el=>el.naturalWidth),256);
    const initial=await page.locator('#flame').getAttribute('src');
    const during=await page.evaluate(async()=>{
      const input=document.getElementById('pressure_kpa');const start=Number(document.getElementById('flame').dataset.renderCount);
      let midway=0;
      for(let i=0;i<40;i++){
        input.value=Number(input.min)+(Number(input.max)-Number(input.min))*i/39;
        input.dispatchEvent(new Event('input',{bubbles:true}));
        await new Promise(resolve=>setTimeout(resolve,30));
        if(i===30)midway=Number(document.getElementById('flame').dataset.renderCount)-start;
      }return midway;
    });
    assert.ok(during>=2,'CNN must render intermediate predictions before input stops');
    await page.waitForFunction(()=>shownVersion===renderVersion&&!inFlight&&!desired);
    assert.notEqual(await page.locator('#flame').getAttribute('src'),initial);
    const expected=await page.locator('#pressure_kpa').evaluate(el=>Number(el.max).toFixed(2));
    assert.ok((await page.locator('#caption').textContent()).includes(expected+' kPa'));
    await page.screenshot({path:'/tmp/flex2-desktop.png',fullPage:true});
    await page.locator('#retrieval').click();
    assert.equal(await page.locator('#retrieval').getAttribute('aria-pressed'),'true');
    const before=predictions;
    const unique=await page.evaluate(()=>{
      const input=document.getElementById('pressure_kpa'),seen=new Set();
      for(let i=0;i<40;i++){
        input.value=Number(input.min)+(Number(input.max)-Number(input.min))*i/39;
        input.dispatchEvent(new Event('input',{bubbles:true}));seen.add(document.getElementById('flame').src);
      }return seen.size;
    });
    assert.ok(unique>1,'Retrieval must select different recorded images across the range');
    assert.equal(predictions,before,'Local retrieval must not queue CNN requests');
    await page.getByText('Recorded examples',{exact:true}).click();await page.locator('#trainOnly').check();
    assert.ok((await page.locator('#caption').textContent()).includes('· train ·'));
    await page.locator('#fuel').selectOption('Heptane');
    assert.ok((await page.locator('#caption').textContent()).startsWith('Recorded'));
    await page.locator('#cnn').click();
    await page.waitForFunction(()=>shownVersion===renderVersion&&!inFlight&&!desired);
    assert.ok((await page.locator('#caption').textContent()).includes('Heptane'));
    for(const width of [390,320]){
      await page.setViewportSize({width,height:900});
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile overflow at '+width);
    }
    await page.screenshot({path:'/tmp/flex2-mobile.png',fullPage:true});
    await page.getByRole('link',{name:'SPICE',exact:true}).click();await page.waitForURL('**/spice/');
    await page.locator('#prediction').waitFor({state:'visible'});
    assert.deepEqual(errors,[]);console.log(JSON.stringify({liveCnnRendersDuringDrag:during,retrievedImagesAcrossSweep:unique,predictionRequests:predictions,browserErrors:errors}));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
