// Run with: playwright-cli -s=town-draft run-code --filename=scripts/check_town_draft.js
async page => {
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('http://127.0.0.1:8765/drafts/town.html?cd=1113000');
  await page.locator('#story-grant').waitFor();
  if (!/용산/.test(await page.locator('#story-grant').innerText())) throw Error('local grant story must identify Yongsan');
  await page.locator('#story-grant [data-sub]').click();
  if (!await page.locator('#wants input[value="감액"]').isChecked()) throw Error('story interest was not carried into the subscription preview');
  if (await page.locator('#subDlg button[type="submit"]').isEnabled()) throw Error('prototype must not collect contacts');
  await page.locator('#subDlg [data-close]').click();
  await page.locator('#townBtn').click();
  await page.locator('#q').fill('가평');
  await page.locator('#pickList button').click();
  if (!/전국 사례/.test(await page.locator('#story-grant').innerText())) throw Error('Yongsan story must not be presented as a Gapyeong finding');
  if (!/가평/.test(await page.locator('h1').innerText())) throw Error('place change lost the selected region');
  await page.locator('#reviewCase').selectOption('1');
  await page.locator('#story-invest [data-sub]').click();
  if (!/검단/.test(await page.locator('#subContext').innerText())) throw Error('selected project was not carried into the subscription preview');
  await page.locator('#subDlg [data-close]').click();
  for (const width of [1440,390]) {
    await page.setViewportSize({width,height:920});
    if (!await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)) throw Error(`horizontal overflow at ${width}`);
  }
  await page.locator('#townBtn').click();
  await page.locator('#q').fill('<img src=x onerror=alert(1)>');
  if (await page.locator('#pickList img').count()) throw Error('search input rendered as markup');
  await page.locator('#pickDlg [data-close]').click();
  await page.goto('http://127.0.0.1:8765/drafts/index.html?cd=4177000');
  await page.locator('[data-town="story-grant"]').waitFor();
  if (!/cd=4177000#story-grant$/.test(await page.locator('[data-town="story-grant"]').getAttribute('href'))) throw Error('review page link lost selected region');
  if (errors.length) throw Error(errors.join('\n'));
  return 'PASS: local/national scope, retained story interest, disabled collection, region change, mobile width and safe search';
}
