// Run with: playwright-cli -s=meeting-draft run-code --filename=scripts/check_meeting_draft.js
async page => {
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('http://127.0.0.1:8765/drafts/meeting.html?cd=1113000');
  await page.locator('#summaryText').waitFor({timeout:5000});
  await page.evaluate(() => localStorage.removeItem('local-finance-meeting-v1'));
  await page.reload();
  if (!/선정된 활동이 없습니다/.test(await page.locator('#summaryText').innerText())) throw Error('undecided activities were represented as selected');
  if (await page.locator('[data-candidate]').count() !== 5) throw Error('candidate comparison missing');
  await page.locator('#decision-open').selectOption('한다');
  await page.locator('#decision-grant').selectOption('보류');
  await page.locator('#note-open').fill('<img src=x onerror=alert(1)> 공개 시점 원문 확인');
  await page.locator('#primaryGoal').selectOption('토대마련');
  await page.reload();
  if (await page.locator('#decision-open').inputValue() !== '한다') throw Error('meeting decision did not survive reload');
  if (!/공개 시점/.test(await page.locator('#note-open').inputValue())) throw Error('meeting note did not survive reload');
  const proposal = await page.locator('#summaryText').innerText();
  if (!/예산안/.test(proposal) || /선정된 활동이 없습니다/.test(proposal)) throw Error('selected activity is absent from proposal');
  if (!/사업 미정|보류/.test(await page.locator('#decisionSummary').innerText())) throw Error('pending work lacks decision status');
  if (await page.locator('#summaryText img').count()) throw Error('notes rendered as markup');
  await page.locator('#exportNotes').click();
  if (!/내려받/.test(await page.locator('#saveStatus').innerText())) throw Error('export not acknowledged');
  for (const width of [1440,360]) {
    await page.setViewportSize({width,height:1000});
    if (!await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)) throw Error(`meeting overflow at ${width}`);
  }
  await page.goto('http://127.0.0.1:8765/drafts/town.html?cd=1113000');
  await page.locator('[data-meeting]').waitFor();
  if (!/cd=1113000/.test(await page.locator('[data-meeting]').getAttribute('href'))) throw Error('meeting link lost region');
  await page.goto('http://127.0.0.1:8765/drafts/index.html?cd=4177000');
  await page.locator('#meetingLink').waitFor();
  if (!/cd=4177000/.test(await page.locator('#meetingLink').getAttribute('href'))) throw Error('door page meeting link lost region');
  await page.evaluate(() => localStorage.removeItem('local-finance-meeting-v1'));
  if (errors.length) throw Error(errors.join('\n'));
  return 'PASS: undecided state, candidate comparison, persisted decisions, safe notes, selected proposal, export, mobile and region link';
}
