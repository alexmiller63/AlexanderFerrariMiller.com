/* Run: node --test tests/test_nativitas_profiles.cjs */
const {test,before,after}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
let browser;
before(async()=>{browser=await chromium.launch({headless:true,args:['--no-sandbox'],executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});});
after(async()=>{await browser?.close();});
function render(file) {
  return fs.readFileSync(path.join(root,file),'utf8')
    .replace(/\{% include ephemera-style.html %\}/g,fs.readFileSync(path.join(root,'_includes/ephemera-style.html'),'utf8'))
    .replace(/\{% include ephemera-panel.html %\}/g,fs.readFileSync(path.join(root,'_includes/ephemera-panel.html'),'utf8'))
    .replace(/\{% if page.calculator == 'natal' %\}([\s\S]*?)\{% endif %\}/g,(_,body)=>body.split('{% else %}')[0])
    .replace(/\{% unless page.calculator == 'natal' %\}[\s\S]*?\{% endunless %\}/g,'')
    .replace(/\{\{ '([^']+)' \| relative_url \}\}/g,'$1')
    .replace(/\{\{ page.calculator \}\}/g,'natal')
    .replace(/\{%.*?%\}/g,'').replace(/^---[\s\S]*?---/,'');
}
async function context() {
  const ctx=await browser.newContext();
  await ctx.route('http://localhost:8765/**',route=>{
    const file=new URL(route.request().url()).pathname.slice(1);
    if(file.endsWith('.html')) return route.fulfill({contentType:'text/html',body:render(file)});
    const full=path.join(root,file);
    if(!fs.existsSync(full)) return route.fulfill({status:404,body:''});
    return route.fulfill({path:full,contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'application/json'});
  });
  await ctx.addInitScript(()=>{
    window.requests=[];
    window.Worker=class {postMessage(data){window.requests.push(data);} terminate(){}};
  });
  return ctx;
}
async function open(ctx,kind='natal-chart') {const page=await ctx.newPage();await page.goto(`http://localhost:8765/nativitas/${kind}.html`);await page.waitForSelector('.birth-profiles');return page;}
const input=(page,name)=>page.locator(`#ephemera-form [name="${name}"]`);
async function birth(page,{date='1963-10-09',time='08:00',zone='America/New_York',unknown=false}={}) {
  await input(page,'local_date').fill(date);
  await input(page,'timezone').fill(zone);
  await input(page,'unknown_time').setChecked(unknown);
  if(!unknown)await input(page,'local_time').fill(time);
  await page.locator('#ephemera-city').fill('New York');
  await input(page,'latitude').fill('40.7');await input(page,'longitude').fill('-74');
  await input(page,'elevation_m').fill('12');
}
async function save(page,name='Alexander') {await page.locator('.profile-name').fill(name);await page.locator('.profile-new').click();assert.match(await page.locator('.profile-status').textContent(),/saved on this device/);return page.locator('.profile-select').inputValue();}
test('save, reopen, use natal and both Synastry forms with the same profile',async()=>{
 const ctx=await context();try {
  const page=await open(ctx);await birth(page);const id=await save(page);
  await page.close();const reopened=await open(ctx);await reopened.locator('.profile-select').selectOption(id);
  assert.equal(await input(reopened,'local_date').inputValue(),'1963-10-09');
  await reopened.locator('#ephemera-calculate').click();
  assert.equal(await reopened.evaluate(()=>requests[0].instant_utc),'1963-10-09T12:00:00.000Z');
  assert.equal(await reopened.locator('.profile-new').isDisabled(),true);
  await reopened.locator('#ephemera-cancel').click();
  const syn=await open(ctx,'synastry');
  for(const i of [0,1]){const f=syn.locator(`[data-person="${i}"]`);await f.locator('.profile-select').selectOption(id);assert.equal(await f.locator('[name=label]').inputValue(),'Alexander');}
  await syn.locator('#synastry-calculate').click();
  assert.equal(await syn.evaluate(()=>requests[0].instant_utc),'1963-10-09T12:00:00.000Z');
  assert.equal(await syn.evaluate(()=>requests[0].elevation_m),12);
 }finally{await ctx.close();}
});
test('unknown time survives loading into Synastry, resaving, and natal noon request',async()=>{
 const ctx=await context();try{
  const page=await open(ctx);await birth(page,{unknown:true});const id=await save(page,'Unknown');
  const syn=await open(ctx,'synastry'),f=syn.locator('[data-person="0"]');await f.locator('.profile-select').selectOption(id);
  assert.equal(await f.locator('[name=time]').isDisabled(),true);
  await f.locator('.profile-update').click();assert.match(await f.locator('.profile-status').textContent(),/updated/);
  await page.reload();await page.locator('.profile-select').selectOption(id);await page.locator('#ephemera-calculate').click();
  assert.equal(await page.evaluate(()=>requests[0].unknown_time),true);assert.equal(await page.evaluate(()=>requests[0].instant_utc),'1963-10-09T16:00:00.000Z');
 }finally{await ctx.close();}
});
test('update and delete synchronize selectors; duplicate names remain distinct; names render as text',async()=>{
 const ctx=await context();try{
  const page=await open(ctx);await birth(page);const id=await save(page,'<img src=x onerror=alert(1)>');
  const syn=await open(ctx,'synastry');const second=await save(page,'<img src=x onerror=alert(1)>');assert.notEqual(id,second);
  assert.equal(await syn.locator('[data-person="0"] .profile-select option').count(),3);
  assert.equal(await page.locator('.birth-profiles img').count(),0);
  await page.locator('.profile-name').fill('Revised');await input(page,'local_date').fill('1970-01-01');await page.locator('.profile-update').click();
  await syn.locator('[data-person="0"] .profile-select').selectOption(second);
  assert.equal(await syn.locator('[data-person="0"] [name=date]').inputValue(),'1970-01-01');
  page.on('dialog',d=>d.accept());await page.locator('.profile-delete').click();
  assert.equal(await syn.locator('[data-person="0"] .profile-select option').count(),2);
  assert.equal(await syn.locator('[data-person="0"] .profile-update').isDisabled(),true);
  assert.equal(await input(page,'local_date').inputValue(),'1970-01-01');
 }finally{await ctx.close();}
});
test('repeated DST occurrence round trips; nonexistent time cannot be saved',async()=>{
 const ctx=await context();try{
  const page=await open(ctx);await birth(page,{date:'2024-11-03',time:'01:30'});
  await page.locator('.profile-name').fill('DST');await page.locator('.profile-new').click();assert.match(await page.locator('.profile-status').textContent(),/occurs twice/);
  await input(page,'time_occurrence').selectOption(String(Date.parse('2024-11-03T06:30:00Z')));const id=await save(page,'DST');
  const syn=await open(ctx,'synastry');for(const i of [0,1])await syn.locator(`[data-person="${i}"] .profile-select`).selectOption(id);
  await syn.locator('#synastry-calculate').click();assert.equal(await syn.evaluate(()=>requests[0].instant_utc),'2024-11-03T06:30:00.000Z');
  await page.reload();await page.locator('.profile-select').selectOption(id);await page.locator('#ephemera-calculate').click();assert.equal(await page.evaluate(()=>requests[0].instant_utc),'2024-11-03T06:30:00.000Z');await page.locator('#ephemera-cancel').click();
  await birth(page,{date:'2024-03-10',time:'02:30'});await page.locator('.profile-new').click();assert.match(await page.locator('.profile-status').textContent(),/does not exist/);
 }finally{await ctx.close();}
});
test('corrupt and unavailable storage report errors without overwriting data or blocking charts',async()=>{
 const ctx=await context();try{
  const page=await open(ctx);await page.evaluate(()=>localStorage.setItem('nativitas.birthProfiles.v1','broken'));await page.reload();
  assert.match(await page.locator('.profile-status').textContent(),/left unchanged/);
  await birth(page);await page.locator('.profile-name').fill('Test');await page.locator('.profile-new').click();
  assert.equal(await page.evaluate(()=>localStorage.getItem('nativitas.birthProfiles.v1')),'broken');
  await page.evaluate(()=>{localStorage.clear();Storage.prototype.setItem=()=>{throw Error('quota');};});
  await page.locator('.profile-new').click();assert.match(await page.locator('.profile-status').textContent(),/could not be saved/);
  await page.locator('#ephemera-calculate').click();assert.equal(await page.evaluate(()=>requests.length),1);
 }finally{await ctx.close();}
});

test('denied storage leaves the birth calculator usable',async()=>{
 const ctx=await context();try{
  await ctx.addInitScript(()=>{Storage.prototype.getItem=()=>{throw new DOMException('Denied','SecurityError');};});
  const page=await open(ctx);assert.match(await page.locator('.profile-status').textContent(),/storage is unavailable/);
  await birth(page);await page.locator('#ephemera-calculate').click();assert.equal(await page.evaluate(()=>requests.length),1);
 }finally{await ctx.close();}
});
