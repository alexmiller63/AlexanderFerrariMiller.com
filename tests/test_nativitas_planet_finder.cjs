/* Run: node --test tests/test_nativitas_planet_finder.cjs
 * Uses Playwright for the real DOM; the astronomy worker is controlled here so
 * UI regressions do not require the large runtime or a lengthy layout search.
 */
const {test, before, after} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
let browser;
before(async () => { browser = await chromium.launch({headless:true, executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE, args:['--no-sandbox']}); });
after(async () => { await browser?.close(); });
async function pageFixture() {
  const page = await browser.newPage();
  page.on('pageerror', error => console.error('PAGE ERROR:', error.message));
  let html = fs.readFileSync(path.join(root,'nativitas/planet-finder.html'),'utf8');
  html = html.replace(/\{% include almanack-notation-toggle.html %\}/, fs.readFileSync(path.join(root,'_includes/almanack-notation-toggle.html'),'utf8'))
    .replace(/<script[\s\S]*?<\/script>/g,'').replace(/<link[^>]*>/g,'').replace(/\{%.*?%\}/g,'');
  await page.route('http://finder.test/**', route => route.fulfill({contentType:'text/html',body:html}));
  await page.goto('http://finder.test/nativitas/planet-finder.html');
  await page.evaluate(() => {
    window.requests = [];
    window.Worker = class {
      constructor() { window.runner = this; }
      postMessage(data) { window.requests.push(data); }
      terminate() {}
    };
  });
  await page.addScriptTag({path:path.join(root,'nativitas/planet-finder-progress.js')});
  await page.addScriptTag({path:path.join(root,'nativitas/planet-finder-form.js')});
  return page;
}
async function choose(page,date,time,zone='America/New_York',city='New York City, NY') {
  await page.locator('#finder-date').fill(date);
  await page.locator('#finder-time').fill(time);
  await page.locator('#finder-zone').fill(zone);
  await page.locator('#finder-city').fill(city);
  await page.locator('#finder-city').press('Tab');
  await page.locator('#finder-generate').click();
}
async function deliver(page, modes=['greek','latin','mixed']) {
  await page.evaluate(modes => {
    const charts=Object.fromEntries(modes.map(mode=>[mode,`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1400 1400"><text y="110">UTC subtitle</text><text y="200">${mode}</text></svg>`]));
    window.runner.onmessage({data:{type:'result',data:{charts,local_title:'October 9, 1963 · 8:00 AM EDT · New York City, NY'}}});
  }, modes);
}
test('historical local conversion, Greek default, local SVG and completed progress', async () => {
  const page=await pageFixture();
  try {
    assert.equal(await page.locator('#finder-mode').inputValue(),'greek');
    await choose(page,'1963-10-09','08:00');
    assert.equal(await page.evaluate(()=>requests[0].instant_utc),'1963-10-09T12:00:00.000Z');
    await deliver(page,['greek']);
    assert.equal(await page.locator('#finder-toggles').isVisible(),false);
    assert.match(await page.locator('#finder-result text[y="110"]').textContent(),/October 9, 1963 · 8:00 AM EDT/);
    assert.equal(await page.locator('#finder-progress-heading').textContent(),'Chart ready');
    assert.equal(await page.locator('#finder-progress-bar').getAttribute('value'),'1');
    const exported = await page.evaluate(async()=>await (await fetch(document.getElementById('finder-download').href)).text());
    assert.match(exported,/October 9, 1963 · 8:00 AM EDT/);
    assert.match(exported,/UTC instant: 1963-10-09T12:00:00.000Z/);
    assert.doesNotMatch(exported,/UTC subtitle/);
  } finally {await page.close();}
});
test('All switches one cached chart at a time, keeps submitted context, and never recalculates',async()=>{
  const page=await pageFixture();
  try {
    await page.locator('#finder-mode').selectOption('all');
    await choose(page,'1963-10-09','08:00');
    await page.locator('#finder-date').fill('2000-01-01');
    await deliver(page);
    assert.equal(await page.locator('#finder-toggles').isVisible(),true);
    assert.equal(await page.locator('[data-bayer-mode="1"]').getAttribute('aria-pressed'),'true');
    for(const [id,key] of [['1','greek'],['2','latin'],['3','mixed'],['1','greek']]){
      await page.locator(`[data-bayer-mode="${id}"]`).focus();
      await page.locator(`[data-bayer-mode="${id}"]`).press('Enter');
      assert.equal(await page.locator('#finder-result svg:visible').count(),1);
      assert.equal(await page.locator('#finder-result svg:visible text[y="200"]').textContent(),key);
      assert.equal(await page.locator(`[data-bayer-mode="${id}"]`).getAttribute('aria-pressed'),'true');
      assert.match(await page.locator('#finder-result svg:visible text[y="110"]').textContent(),/1963/);
      assert.equal(await page.locator('#finder-download').getAttribute('download'),`planet-finder-${key}.svg`);
    }
    assert.equal(await page.evaluate(()=>requests.length),1);
    assert.equal(await page.evaluate(()=>requests[0].mode),'all');
    assert.equal(await page.evaluate(()=>requests[0].city),'New York City, NY');
    await page.locator('#finder-mode').selectOption('latin');
    await choose(page,'1963-10-09','08:00');
    assert.equal(await page.locator('#finder-cancel').isEnabled(),true);
    assert.equal(await page.locator('#finder-progress-heading').textContent(),'Calculating your chart');
    await deliver(page,['latin']);
    assert.equal(await page.locator('#finder-toggles').isVisible(),false);
    assert.equal(await page.locator('#finder-result svg').count(),1);
  }finally{await page.close();}
});
test('DST gap and fold rejected; summer, winter and fractional offsets converted',async()=>{
  const page=await pageFixture();
  try {
    for(const [date,time,pattern] of [['2026-03-08','02:30',/does not exist/],['2026-11-01','01:30',/occurs twice/]]){
      await choose(page,date,time);
      assert.match(await page.locator('#finder-availability').textContent(),pattern);
    }
    assert.equal(await page.evaluate(()=>requests.length),0);
    for(const [date,time,zone,expected] of [
      ['1963-01-09','08:00','America/New_York','1963-01-09T13:00:00.000Z'],
      ['1990-01-16','14:28','America/Los_Angeles','1990-01-16T22:28:00.000Z'],
      ['2026-07-01','08:00','Asia/Kolkata','2026-07-01T02:30:00.000Z'],
      ['2026-07-01','00:15','Pacific/Auckland','2026-06-30T12:15:00.000Z']]) {
      await choose(page,date,time,zone,'');
      assert.equal(await page.evaluate(()=>requests.at(-1).instant_utc),expected);
      await page.locator('#finder-cancel').click();
    }
  }finally{await page.close();}
});
test('incomplete All result never displays partial charts or success; error and cancellation stop progress',async()=>{
  const page=await pageFixture();
  try {
    await page.locator('#finder-mode').selectOption('all');
    await choose(page,'1963-10-09','08:00');
    await deliver(page,['greek']);
    assert.equal(await page.locator('#finder-result').isVisible(),false);
    assert.match(await page.locator('#finder-availability').textContent(),/mode is missing/);
    assert.equal(await page.locator('#finder-progress-heading').textContent(),'Calculation stopped');
    await choose(page,'1963-10-09','08:00');
    await page.locator('#finder-cancel').click();
    assert.equal(await page.locator('#finder-progress-heading').textContent(),'Calculation stopped');
  }finally{await page.close();}
});
test('real worker message contract returns every mode and local title atomically',async()=>{
  const messages=[];let pythonCode='';
  const python={globals:{set(){}},async runPythonAsync(code){pythonCode=code;return JSON.stringify({charts:{greek:'g',latin:'e',mixed:'m'},local_title:'local'});}};
  const context={self:{location:{href:'http://localhost/star-almanack/js/ephemera-worker.js'},postMessage:x=>messages.push(x)},URL,console};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(root,'star-almanack/js/ephemera-worker.js'),'utf8'),context);
  context.python=python;
  vm.runInContext('ready = Promise.resolve(python)',context);
  await context.self.onmessage({data:{calculator:'planet-finder',mode:'all',instant_utc:'1963-10-09T12:00:00Z',timezone:'America/New_York'}});
  assert.deepEqual(Object.keys(messages.at(-1).data.charts),['greek','latin','mixed']);
  assert.equal(messages.at(-1).data.local_title,'local');
  assert.match(pythonCode, /ZoneInfo/);
});
