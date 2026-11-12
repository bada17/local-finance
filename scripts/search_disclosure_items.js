// 공시 목록에 없는 항목을 **그 누리집의 통합검색**으로 찾는다 — 공지·고시공고 같은 다른 게시판에 올린 것(「목록 밖」)을 잡으려고.
//   (2026-11-11 사용자 「중기지방재정계획은 별도 목록이 아니라 공지에 올라가 있어서 못 찾은 경우도 있잖아」)
//
//   node scripts/search_disclosure_items.js 일감.json      일감 = [{곳, 이름, 주소(누리집 아무 화면), 낱말:[…]}]
//   결과: data/disclosure_search.json — 곳마다 낱말마다 {검색주소, 결과줄:[…], 까닭}
//
// 찾는 법 — 첫 화면에서 검색칸(input 이름·id·placeholder·title 에 query·keyword·search·검색)을 찾아 낱말을 넣고 그 form 을 보낸다.
//   결과 화면에서 낱말이 든 줄만 적는다(사람이 볼 근거). **나온 줄이 공시인지는 판정하지 않는다** — 줄 그대로 남긴다.
//   검색칸을 못 찾으면 「검색칸 못 찾음」, 결과에 낱말이 없으면 「검색 결과 없음」.
// ⚠️ 크롬 넷(CDP_PORT … +3)을 따로 띄운다. 한 곳은 한 탭에서 차례로(같은 누리집을 동시에 두드리지 않게).
const fs = require('fs');
const path = require('path');
const os = require('os');
const R = require('./recheck_disclosure.js');

const ROOT = path.dirname(__dirname);
const OUT = path.join(ROOT, 'data', 'disclosure_search.json');
const 쉼 = ms => new Promise(r => setTimeout(r, ms));

async function 다될때(탭, 먼저 = 1500) {
  await 쉼(먼저);
  const 끝 = Date.now() + 15000;
  while (Date.now() < 끝) {
    const r = await 탭.보내기('Runtime.evaluate', { expression: 'document.readyState + "|" + (document.body ? document.body.innerText.length : 0)', returnByValue: true });
    const [s, n] = String((r.result && r.result.value) || '').split('|');
    if (s === 'complete' && +n > 200) return;
    await 쉼(400);
  }
}

const 검색하기 = 낱말 => `(() => {
  const 맞 = e => /query|keyword|kwd|search|srch|searchword|q$|검색/i.test([e.name, e.id, e.placeholder, e.title, e.getAttribute('aria-label')].join(' '));
  const 칸들 = [...document.querySelectorAll('input[type=text],input[type=search],input:not([type])')].filter(맞);
  const 칸 = 칸들.find(e => e.form) || 칸들[0];
  if (!칸) return '검색칸 못 찾음';
  칸.focus(); 칸.value = ${JSON.stringify(낱말)};
  칸.dispatchEvent(new Event('input', { bubbles: true }));
  const f = 칸.form;
  if (f) { const b = f.querySelector('button[type=submit],input[type=submit],button:not([type]),input[type=image]'); if (b) b.click(); else f.submit(); return 'form'; }
  칸.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, which: 13, bubbles: true }));
  const b = 칸.parentElement && 칸.parentElement.querySelector('button,a,input[type=image]');
  if (b) b.click();
  return 'enter';
})()`;

const 줄뽑기 = 낱말 => `(() => {
  const 열쇠 = s => s.replace(/\\s+/g, '');
  const w = 열쇠(${JSON.stringify(낱말)});
  const 줄 = (document.body ? document.body.innerText : '').split('\\n').map(s => s.replace(/\\s+/g, ' ').trim())
    .filter(s => s.length >= 4 && s.length <= 200 && 열쇠(s).includes(w));
  // 낱말이 든 글 링크(글로 들어가 첨부를 열어 보려고 — open_search_posts.js, 11-12)
  const 링크 = [...document.querySelectorAll('a')].map(a => ({ 글: (a.innerText || a.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 120), 주소: a.href }))
    .filter(x => /^https?:/.test(x.주소) && x.글.length >= 4 && 열쇠(x.글).includes(w)).slice(0, 8);
  return JSON.stringify({ 주소: location.href.slice(0, 300), 줄: [...new Set(줄)].slice(0, 15), 수: 줄.length, 링크 });
})()`;

async function 한곳(탭, 일) {
  const 결과 = {};
  for (const 낱말 of 일.낱말) {
    try {
      await 탭.보내기('Page.navigate', { url: 일.주소 });
      await 다될때(탭);
      const r = await 탭.보내기('Runtime.evaluate', { expression: 검색하기(낱말), returnByValue: true });
      const 방법 = (r.result && r.result.value) || '못 보냄';
      if (방법 === '검색칸 못 찾음' || 방법 === '못 보냄') { 결과[낱말] = { 까닭: 방법 }; continue; }
      await 다될때(탭, 3500);
      const q = await 탭.보내기('Runtime.evaluate', { expression: 줄뽑기(낱말), returnByValue: true });
      const v = JSON.parse((q.result && q.result.value) || '{"줄":[]}');
      // 검색칸에 남은 낱말·「검색어: …」 줄만 있으면 결과가 아니다
      const 진짜 = v.줄.filter(s => !/검색어|검색결과\\s*\\d|search/i.test(s) || s.length > 40);
      // 검색 화면으로 안 넘어가면 줄은 **받은 화면(메뉴·목록)의 글자**다 — 그렇다고 적는다
      const 넘어감 = v.주소.split('#')[0] !== 일.주소.split('#')[0];
      결과[낱말] = { 검색주소: v.주소, 넘어감, 결과줄: 진짜, 링크: v.링크 || [], 까닭: 진짜.length ? '' : (넘어감 ? '검색 결과 없음' : '검색 화면으로 안 넘어감') };
    } catch (e) {
      결과[낱말] = { 까닭: '틀림 ' + String(e).slice(0, 60) };
    }
  }
  return 결과;
}

module.exports = { 다될때, 검색하기, 줄뽑기 };
if (require.main === module) (async () => {
  const 일감 = JSON.parse(fs.readFileSync(process.argv[2], 'utf-8'));
  const 프로필 = fs.mkdtempSync(path.join(os.tmpdir(), 'lf-search-'));
  const 크롬 = R.크롬띄우기(프로필);
  await R.붙을때까지();
  const 나온 = {};
  let k = 0, 다음 = 0;
  // 탭 넷이 곳을 하나씩 가져간다 — 한 곳의 낱말들은 한 탭에서 차례로(같은 누리집을 동시에 두드리지 않게)
  await Promise.all([0, 1, 2, 3].map(async () => {
    const 탭 = await R.탭열기();
    탭.듣기('Page.javascriptDialogOpening', () => 탭.보내기('Page.handleJavaScriptDialog', { accept: true }));
    while (다음 < 일감.length) {
      const 일 = 일감[다음++];
      나온[일.곳] = { 이름: 일.이름, 바탕: 일.주소, 낱말: await 한곳(탭, 일) };
      if (++k % 20 === 0) console.log(`   ${k}/${일감.length}`);
    }
  }));
  const 쓸곳 = process.argv[3] || OUT;
  // 앞 결과와 합친다 — 일감은 아직 안 찾아본 말뿐이라 덮어쓰면 앞 회차가 날아간다(11-12)
  const 앞 = fs.existsSync(쓸곳) ? JSON.parse(fs.readFileSync(쓸곳, 'utf-8')).곳 : {};
  for (const [cd, v] of Object.entries(나온)) 앞[cd] = { ...(앞[cd] || v), 낱말: { ...((앞[cd] || {}).낱말 || {}), ...v.낱말 } };
  fs.writeFileSync(쓸곳, JSON.stringify({ 만든날: new Date().toISOString().slice(0, 10), 곳: 앞 }, null, 0));
  console.log('적음', 쓸곳);
  크롬.kill();
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
