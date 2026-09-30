// Serve site/ on localhost:8765 first. Set NODE_PATH if Playwright is bundled elsewhere.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const base=process.env.SITE_URL||'http://127.0.0.1:8765/';
(async()=>{
 const browser=await chromium.launch({channel:process.env.BROWSER_CHANNEL||'msedge',headless:true});
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto(base+'#4612000,계약');await page.waitForSelector('#cyear button');
  await page.locator('#cyear button').first().click();
  assert.equal(await page.locator('#clik-panel').count(),0,'council list lives only in its own tab');
  for(const width of [1440,360]){
   await page.setViewportSize({width,height:950});
   for(const [file,ready] of [['#4612000,의회','#clik-count'],['board.html','#list tbody tr'],['transparency.html','#list tbody tr'],['catalog.html','#list tbody tr'],['edu.html','#tree .nd'],['datamap.html','#all tbody tr']]){
    await page.goto(base+file);await page.waitForSelector(ready);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${file} overflow at ${width}`);
   }
  }
  await page.goto(base+'#4612000,의회');await page.waitForSelector('#clik-count');
  assert.equal(await page.locator('#clik-panel .clik-note li').count(),4);
  assert.equal(await page.locator('#clik-results li').count(),25);
  const first=await page.locator('#clik-results a').first().getAttribute('href');
  await page.locator('#clik-next').click();
  assert.notEqual(await page.locator('#clik-results a').first().getAttribute('href'),first);
  await page.locator('#clik-prev').click();
  assert.equal(await page.locator('#clik-results a').first().getAttribute('href'),first);
  await page.locator('[data-clik-kind="의안"]').click();await page.locator('#clik-query').fill('섬박람회');
  assert.ok(await page.locator('#clik-results li').count()>0);
  await page.locator('#clik-query').fill('<img src=x onerror=alert(1)>');
  assert.equal(await page.locator('#clik-panel img').count(),0);
  assert.equal(await page.locator('#clik-results li').count(),0);
  await page.locator('#pick').selectOption('3014000');await page.waitForSelector('#clik-count');
  await page.locator('[data-clik-kind="의안"]').click();await page.locator('#clik-year').selectOption('unknown');
  assert.match(await page.locator('#clik-results').innerText(),/20225110/);
  // Request failure is visibly different from a successful empty list; retry recovers.
  await page.evaluate(()=>clikCache.delete('4612000'));
  await page.route('**/data/clik/4612000.json',r=>r.abort());await page.goto(base+'#4612000,의회');
  await page.waitForSelector('#clik-retry');await page.unroute('**/data/clik/4612000.json');
  await page.locator('#clik-retry').click();await page.waitForSelector('#clik-count');
  // A slow old place must not overwrite a newly selected place or remove its council panel.
  await page.route('**/data/clik/4612000.json',async r=>{await new Promise(resolve=>setTimeout(resolve,500));await r.continue();});
  await page.evaluate(()=>clikCache.delete('4612000'));await page.goto(base+'#4612000,의회');await page.locator('#pick').selectOption('2812500');
  await page.waitForSelector('#clik-count');await page.waitForTimeout(650);
  assert.match(await page.locator('#app h1').innerText(),/제물포/);
  assert.equal(await page.locator('#clik-panel').count(),1);
  await page.unroute('**/data/clik/4612000.json');
  await page.goto(base+'board.html');await page.waitForSelector('#list tbody tr');
  assert.ok(await page.locator('.amount-under').count()>0,'percentages need amounts');
  assert.match(await page.locator('.amount-under').first().innerText(),/원/);
  await page.setViewportSize({width:1440,height:950});await page.goto(base+'transparency.html');await page.waitForSelector('#list tbody tr');
  const wrap=page.locator('#list .scroll').first();
  if(!await wrap.evaluate(e=>e.classList.contains('needs-scroll')))assert.equal(await wrap.evaluate(e=>getComputedStyle(e).overflowX),'visible');
  assert.deepEqual(errors,[]);
  console.log('PASS: six pages at 1440/360px; CLIK paging/search/invalid-date/error/retry; contract-year retention; slow-place race; amounts; sticky container; no JS errors.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
