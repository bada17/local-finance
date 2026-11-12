// 결산기준(또는 예산기준) 공시 묶음을 **못 받은 곳**에서 그 묶음이 누리집 어디에 있는지 링크를 찾는다.
//   (2026-11-12 사용자 「투 트랙으로 — 공시된 링크를 확인하는 거 먼저, 열어보는 것도」) — 이건 첫 트랙(링크).
//
//   node scripts/find_settle_page.js 일감.json [결과.json]
//     일감 = [{곳, 이름, 기준:'결산'|'예산', 출발:[주소…]}]   ← tag_disclosure.py --묶음일감 이 만든다
//   결과(기본 data/disclosure_settle.json, **앞 결과와 합친다** — 새로 못 찾은 곳은 앞에 찾은 것을 둔다)
//     곳|기준 마다 {기준, 후보:[{글, 주소, 본곳, 점}], 고른주소, 화면:{제목, 끝주소, 파일:[…]}, 까닭}
//
// 찾는 법 — 출발 화면(받은 공시 주소 → 들어간 주소 → 누리집 첫 화면)마다 링크를 모은다.
//   후보: 글자에 「결산」(예산이면 「예산」·결산 없음)이 있고 ⓐ「공시·재정·운용」도 있거나 ⓑ「결산」「결산기준」처럼 짧은 탭 글자.
//   점수: 공시 +3 · 재정 +1 · 기준 +1 · 해 2026/2025 +2, 2024 +1 · 짧은 탭 +2 · 추가·수시·특수·정정·수정·성과·서식·안내 −4.
//   위에서 넷까지 열어 본다 — 주소가 있으면 그 주소로, 자바스크립트·#·같은 화면이면 **그 자리에서 눌러** 바뀐 화면을 긁는다
//   (포항 「재정공시(결산)」 탭 — 주소로 다시 열면 예산 탭이 떠서 예산 파일을 잡았다, 11-12).
//   고르기: 파일 이름에 그 기준 말(결산)이 든 수 + 후보 점수가 가장 큰 화면.
// ⚠️ 고른 화면이 진짜 결산 공시인지는 **파일을 열어 봐야** 안다(둘째 트랙, read_disclosure_files.py). 여기는 링크까지만.
const fs = require('fs');
const path = require('path');
const os = require('os');
const R = require('./recheck_disclosure.js');

const ROOT = path.dirname(__dirname);
const 쉼 = ms => new Promise(r => setTimeout(r, ms));

const 링크모으기 = 기준 => `(() => {
  const 결 = ${기준 === '결산'};
  const 맞 = 결 ? (s => /결산/.test(s)) : (s => /예산/.test(s) && !/결산/.test(s));
  const 탭 = 결 ? /^\\(?\\s*(20\\d\\d\\s*(년|회계연도)?\\s*)?결산\\s*(기준|공시|기준\\s*공시)?\\s*\\)?$/ : /^\\(?\\s*(20\\d\\d\\s*(년|회계연도)?\\s*)?예산\\s*(기준|공시|기준\\s*공시)?\\s*\\)?$/;
  return JSON.stringify([...document.querySelectorAll('a,button,[role=tab],li[onclick]')].map((a, i) => {
    const 글 = (a.innerText || a.title || '').replace(/\\s+/g, ' ').trim();
    if (!글 || 글.length > 60 || !맞(글)) return null;
    const 짧은탭 = 탭.test(글);
    if (!짧은탭 && !/공시|재정|운용|운영/.test(글)) return null;
    if (/결산서|예산서|첨부|다운|바로보기|미리보기|바로듣기/.test(글) && !/공시/.test(글)) return null;
    if (/\\.(pdf|hwpx?|xlsx?|zip)\\b|\\[[\\d.,]+\\s*[KM]B/i.test(글) || /download|filedown|atchfile/i.test(a.href || '')) return null;   // 파일 링크는 화면이 아니다(경기 「…추가공시.pdf」)
    const 점 = (/공시/.test(글) ? 3 : 0) + (/재정/.test(글) ? 1 : 0) + (/기준/.test(글) ? 1 : 0) + (짧은탭 ? 2 : 0)
      + (/202[56]/.test(글) ? 2 : /2024/.test(글) ? 1 : 0) - (/추가|수시|특수|정정|수정|성과|서식|안내/.test(글) ? 4 : 0);
    const 주소 = a.href || '';
    return { 글, 주소, 번째: i, 점, 누름: !/^https?:/.test(주소) || 주소.split('#')[0] === location.href.split('#')[0] };
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

async function 긁기(탭) {
  const r = await 탭.보내기('Runtime.evaluate', { expression: R.긁개, returnByValue: true, timeout: 8000 });
  return r.result && r.result.value ? JSON.parse(r.result.value) : null;
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
    if (후보.some(c => c.점 >= 6)) break;   // 「20xx … 결산기준 공시」까지 맞으면 더 안 돌아다닌다
  }
  후보.sort((a, b) => b.점 - a.점);
  const 기준말 = new RegExp(일.기준);
  let 고른 = null;
  for (const c of 후보.filter(c => c.점 > 0).slice(0, 4)) {
    let 화면 = null, 주소 = c.주소;
    try {
      if (c.누름) {   // 그 자리에서 누르고 바뀐 화면을 긁는다(탭·자바스크립트 링크)
        await 열기(탭, c.본곳);
        await 탭.보내기('Runtime.evaluate', { expression: `document.querySelectorAll('a,button,[role=tab],li[onclick]')[${c.번째}].click()` });
        await 쉼(3500);
        화면 = await 긁기(탭);
        주소 = (화면 && 화면.주소) || c.본곳;
        if (화면) 화면 = { 제목: 화면.제목, 끝주소: 주소, 파일: 화면.파일 || [], 누른글: c.글 };
      } else {
        화면 = await R.한곳(탭, { laf_cd: 일.곳, 이름: 일.이름, 주소 });
      }
    } catch (e) { continue; }
    const 이름들 = ((화면 && 화면.파일) || []).filter(f => R.뜻있나(f.이름));
    if (!이름들.length) continue;
    const 점 = 이름들.filter(f => 기준말.test(f.이름)).length * 2 + c.점;
    if (!고른 || 점 > 고른.점) 고른 = { 점, 주소, 화면 };
  }
  if (고른) return { 기준: 일.기준, 후보: 후보.slice(0, 8), 고른주소: 고른.주소, 화면: 고른.화면, 까닭: '' };
  return { 기준: 일.기준, 후보: 후보.slice(0, 8), 고른주소: '', 화면: null,
           까닭: 후보.length ? '후보 링크는 있는데 파일 이름이 든 화면이 없음' : `「${일.기준}」이 든 공시 링크·탭 없음` };
}

(async () => {
  const 일감 = JSON.parse(fs.readFileSync(process.argv[2], 'utf-8'));
  const 쓸곳 = process.argv[3] || path.join(ROOT, 'data', 'disclosure_settle.json');
  const 크롬 = R.크롬띄우기(fs.mkdtempSync(path.join(os.tmpdir(), 'lf-settle-')));
  await R.붙을때까지();
  const 나온 = fs.existsSync(쓸곳) ? JSON.parse(fs.readFileSync(쓸곳, 'utf-8')).곳 : {};
  let 다음 = 0, 끝난 = 0, 찾음 = 0;
  const 일꾼 = async () => {   // 탭 넷 — 한 곳은 한 탭에서만(같은 누리집을 동시에 두드리지 않게)
    const 탭 = await R.탭열기();
    탭.듣기('Page.javascriptDialogOpening', () => 탭.보내기('Page.handleJavaScriptDialog', { accept: true }));
    while (다음 < 일감.length) {
      const 일 = 일감[다음++], 열쇠 = 일.곳 + '|' + 일.기준;
      let v;
      try { v = { 이름: 일.이름, ...await 한곳(탭, 일) }; }
      catch (e) { v = { 이름: 일.이름, 기준: 일.기준, 까닭: '틀림 ' + String(e).slice(0, 60) }; }
      if (v.화면 || !(나온[열쇠] && 나온[열쇠].화면)) 나온[열쇠] = v;   // 새로 못 찾았으면 앞에 찾은 것을 둔다
      if (v.화면) 찾음++;
      if (++끝난 % 20 === 0) console.log(`   ${끝난}/${일감.length}`);
    }
  };
  await Promise.all([일꾼(), 일꾼(), 일꾼(), 일꾼()]);
  fs.writeFileSync(쓸곳, JSON.stringify({ 만든날: new Date().toISOString().slice(0, 10), 곳: 나온 }, null, 0));
  console.log(`결산·예산 공시 화면 찾기 ${일감.length}건 → 찾음 ${찾음} · 적음 ${쓸곳}`);
  크롬.kill();
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
