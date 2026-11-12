// 결산기준(또는 예산기준) 공시 묶음을 **못 받은 곳**에서 그 묶음이 누리집 어디에 있는지 링크를 찾는다.
//   (2026-11-12 사용자 「투 트랙으로 — 공시된 링크를 확인하는 거 먼저, 열어보는 것도」) — 이건 첫 트랙(링크).
//
//   node scripts/find_settle_page.js 일감.json [결과.json]
//     일감 = [{곳, 이름, 기준:'결산'|'예산', 출발:[주소…]}]   ← tag_disclosure.py --묶음일감 이 만든다
//   결과(기본 data/disclosure_settle.json) — 곳마다 {기준, 후보:[{글, 주소, 본곳}], 고른주소, 화면:{제목, 끝주소, 파일:[…]}, 까닭}
//
// 찾는 법 — 출발 화면(받은 공시 주소 → 들어간 주소 → 누리집 첫 화면)마다 링크 글자에 「결산」(예산이면 「예산」·결산 없음)과
//   「공시·재정」이 함께 든 것을 모은다. 점수 높은 것부터 셋까지 열어(링크가 자바스크립트면 눌러서 간 주소를 적는다)
//   recheck_disclosure.js 의 한곳()으로 그 화면의 파일을 긁는다. 파일 이름이 든 첫 화면을 고른다.
// ⚠️ 고른 화면이 진짜 결산 공시인지는 **파일을 열어 봐야** 안다(둘째 트랙, read_disclosure_files.py). 여기는 링크까지만.
const fs = require('fs');
const path = require('path');
const os = require('os');
const R = require('./recheck_disclosure.js');

const ROOT = path.dirname(__dirname);
const 쉼 = ms => new Promise(r => setTimeout(r, ms));

const 링크모으기 = 기준 => `(() => {
  const 맞 = ${기준 === '결산'} ? (s => /결산/.test(s)) : (s => /예산/.test(s) && !/결산/.test(s));
  return JSON.stringify([...document.querySelectorAll('a')].map((a, i) => {
    const 글 = (a.innerText || a.title || '').replace(/\\s+/g, ' ').trim();
    if (!글 || 글.length > 60 || !맞(글) || !/공시|재정|운용|운영/.test(글)) return null;
    if (/결산서|예산서|첨부|다운|바로보기|미리보기/.test(글) && !/공시/.test(글)) return null;
    const 점 = (/공시/.test(글) ? 3 : 0) + (/재정/.test(글) ? 1 : 0) + (/202[456]/.test(글) ? 1 : 0) + (/기준/.test(글) ? 1 : 0);
    return { 글, 주소: a.href, 번째: i, 점 };
  }).filter(Boolean));
})()`;

async function 열기(탭, 주소) {
  await 탭.보내기('Page.navigate', { url: 주소 });
  await 쉼(1500);
  const 끝 = Date.now() + 15000;
  while (Date.now() < 끝) {
    const r = await 탭.보내기('Runtime.evaluate', { expression: 'document.readyState + "|" + (document.body ? document.body.innerText.length : 0)', returnByValue: true });
    const [s, n] = String((r.result && r.result.value) || '').split('|');
    if (s === 'complete' && +n > 120) break;
    await 쉼(400);
  }
  await 쉼(800);
}

async function 한곳(탭, 일) {
  const 후보 = [];
  for (const 출발 of 일.출발) {
    try {
      await 열기(탭, 출발);
      const r = await 탭.보내기('Runtime.evaluate', { expression: 링크모으기(일.기준), returnByValue: true });
      for (const c of JSON.parse((r.result && r.result.value) || '[]'))
        if (!후보.some(x => x.글 === c.글 && x.주소 === c.주소)) 후보.push({ ...c, 본곳: 출발 });
    } catch (e) { /* 출발 화면이 안 열리면 다음 출발로 */ }
    if (후보.some(c => c.점 >= 4)) break;   // 「…결산…공시」 + 해/기준까지 맞으면 더 안 돌아다닌다
  }
  후보.sort((a, b) => b.점 - a.점);
  for (const c of 후보.slice(0, 3)) {
    let 주소 = c.주소;
    if (!/^https?:/.test(주소)) {   // 자바스크립트 링크 — 그 화면에서 눌러 보고 간 주소를 적는다
      await 열기(탭, c.본곳);
      await 탭.보내기('Runtime.evaluate', { expression: `document.querySelectorAll('a')[${c.번째}].click()` });
      await 쉼(4000);
      const q = await 탭.보내기('Runtime.evaluate', { expression: 'location.href', returnByValue: true });
      주소 = (q.result && q.result.value) || '';
      c.눌러간주소 = 주소;
      if (!주소 || 주소 === c.본곳) continue;
    }
    const 화면 = await R.한곳(탭, { laf_cd: 일.곳, 이름: 일.이름, 주소 });
    if ((화면.파일 || []).some(f => R.뜻있나(f.이름)))
      return { 기준: 일.기준, 후보: 후보.slice(0, 8), 고른주소: 주소, 화면, 까닭: '' };
  }
  return { 기준: 일.기준, 후보: 후보.slice(0, 8), 고른주소: '', 화면: null,
           까닭: 후보.length ? '후보 링크는 있는데 파일 이름이 든 화면이 없음' : `「${일.기준}」·「공시/재정」이 함께 든 링크 없음` };
}

(async () => {
  const 일감 = JSON.parse(fs.readFileSync(process.argv[2], 'utf-8'));
  const 쓸곳 = process.argv[3] || path.join(ROOT, 'data', 'disclosure_settle.json');
  const 크롬 = R.크롬띄우기(fs.mkdtempSync(path.join(os.tmpdir(), 'lf-settle-')));
  await R.붙을때까지();
  const 나온 = {};
  let 다음 = 0, 끝난 = 0;
  const 일꾼 = async () => {   // 탭 넷 — 한 곳은 한 탭에서만(같은 누리집을 동시에 두드리지 않게)
    const 탭 = await R.탭열기();
    탭.듣기('Page.javascriptDialogOpening', () => 탭.보내기('Page.handleJavaScriptDialog', { accept: true }));
    while (다음 < 일감.length) {
      const 일 = 일감[다음++];
      try { 나온[일.곳 + '|' + 일.기준] = { 이름: 일.이름, ...await 한곳(탭, 일) }; }
      catch (e) { 나온[일.곳 + '|' + 일.기준] = { 이름: 일.이름, 기준: 일.기준, 까닭: '틀림 ' + String(e).slice(0, 60) }; }
      if (++끝난 % 10 === 0) console.log(`   ${끝난}/${일감.length}`);
    }
  };
  await Promise.all([일꾼(), 일꾼(), 일꾼(), 일꾼()]);
  fs.writeFileSync(쓸곳, JSON.stringify({ 만든날: new Date().toISOString().slice(0, 10), 곳: 나온 }, null, 0));
  console.log('적음', 쓸곳);
  크롬.kill();
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
