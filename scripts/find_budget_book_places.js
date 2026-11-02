// 예산서 자리 찾기 — 곳마다 「사업예산서가 실제로 올라오는 화면」 주소를 하나씩 적는다(2026-11-02 사용자 「예산서를 늘 확인할 수 있어야 해」).
//
//   node scripts/find_budget_book_places.js                     243곳 전부(30분 안팎)
//   node scripts/find_budget_book_places.js --곳 4125000,1111000  몇 곳만 — 결과를 합친다
//   CDP_PORT=9471 node scripts/find_budget_book_places.js        다른 대화가 크롬(9333)을 쓰고 있으면
//
// 왜 — 지방재정365 가 준 예산서 주소(BUDLK)가 엉뚱한 게시판인 곳이 있다. 시흥은 재정게시판을 주는데
//   예산서는 같은 누리집의 「예산서」 메뉴에 해마다 따로 있다. 그래서 BUDLK 화면과 그 화면 메뉴 가운데
//   「예산서」 같은 이름의 링크를 몇 개 열어 보고, 올해·작년 예산서 이름이 가장 많이 보이는 화면을 고른다.
// ⭐ 사람이 적은 줄(어떻게: '사람')은 건드리지 않는다 — 봇이 못 찾은 곳은 사람이 주소를 적어 넣는다.
// ⚠️ 국내 PC 에서 돌린다(지자체 누리집은 해외를 막는 곳이 많다).
//
// 결과: data/budget_book_places.json — { 곳: { <코드>: { 이름, 주소, 어떻게, 점수, 근거, BUDLK } } }
//   어떻게 = BUDLK(받은 주소가 맞다) · 메뉴(메뉴를 따라가 찾았다) · 못 찾음 · 사람

const fs = require('fs');
const path = require('path');
const os = require('os');
const { 크롬자리, 크롬띄우기, 붙을때까지, 탭열기, PORT, 긁개, 뜻있나, 기다림 } = require('./recheck_disclosure.js');

const ROOT = path.dirname(__dirname);
const OUT = path.join(ROOT, 'data', 'budget_book_places.json');
const 한번에 = 4;
const 잠깐 = ms => new Promise(r => setTimeout(r, ms));

// 「예산서」 메뉴 후보 — 글자가 짧아도(「예산서」 3자) 줍는다. 같은 누리집만
const 메뉴모으개 = String.raw`(() => {
  const 뜻 = /예산서|세입\s*[·ㆍ\/]?\s*세출\s*예산|본\s*예산|예산\s*공개|예\s*[·ㆍ]?\s*결산서|사업\s*예산/;
  const 아님 = /성인지|기금|주민참여|아동|기후|온실|낭비|절감|공시|중기|설명회|결산서?$|규모|총괄|집행|의견|센터|재단|공단|운[용영]\s*(현황|상황)/;
  const out = [], 본 = new Set();
  for (const a of document.querySelectorAll('a')) {
    const t = (a.textContent || '').replace(/\s+/g, ' ').trim();
    // 해가 적힌 링크는 메뉴가 아니라 글 하나다(은평·서초) — 자리는 그 글이 걸린 목록이다
    if (t.length < 2 || t.length > 40 || !뜻.test(t) || 아님.test(t) || /20\d\d/.test(t)) continue;
    let u; try { u = new URL(a.href); } catch (e) { continue; }
    if (!/^https?:$/.test(u.protocol) || u.hostname !== location.hostname) continue;
    const h = u.href.split('#')[0];
    if (h === location.href.split('#')[0] || 본.has(h)) continue;
    본.add(h);
    out.push({ 글: t, 주소: h.slice(0, 220) });
  }
  return JSON.stringify(out.slice(0, 8));
})()`;

// 화면에 보이는 글 제목(예산이 든 링크 글자) — 게시판 목록이면 「2026년 본예산서」 같은 글이 걸린다
const 글모으개 = String.raw`(() => {
  const out = new Set();
  for (const a of document.querySelectorAll('a,button,option,li,td')) {
    const t = (a.textContent || '').replace(/\s+/g, ' ').trim();
    if (t.length >= 4 && t.length <= 90 && /예산/.test(t)) out.add(t);
    if (out.size >= 150) break;
  }
  return JSON.stringify([...out]);
})()`;

// 「2026년도 본예산」만 적힌 글(구례·부산 강서)도 예산서 글이다. 「기금」은 빼지 않는다 — 충주는 「… 예산서 / 기금운용계획」
const 좋은이름 = /사업\s*예산서|세입\s*[·ㆍ]?\s*세출\s*예산서|예산서|세출\s*예산|사업\s*명세|세부\s*사업|예산\s*\(?\s*전체|본\s*예산/;
const 나쁜이름 = /성인지|결산|기후|온실|아동|주민참여|재정\s*공시|설명회|중기|낭비|절감|공기업|운[용영]\s*(현황|상황)|센터|재단|공단|어린이집|규모/;

// 화면 하나의 점수 — 올해·작년 예산서 이름이 몇 개 보이나, 제목이 「예산서」인가
function 매기기(화면, 해들) {
  const 이름들 = [...(Array.isArray(화면.파일) ? 화면.파일 : []).map(f => f.이름).filter(뜻있나), ...(Array.isArray(화면.글) ? 화면.글 : [])];
  const 좋은 = [...new Set(이름들.filter(n => 좋은이름.test(n) && !나쁜이름.test(n)))];
  const 해맞음 = 좋은.filter(n => 해들.some(y => n.includes(y) || n.includes(y.slice(2) + '년')));
  let 점수 = Math.min(해맞음.length, 5) * 3 + Math.min(좋은.length, 5);
  if (/예산서/.test(화면.제목 || '')) 점수 += 3;
  if (해들.some(y => (화면.제목 || '').includes(y))) 점수 += 3;   // 연도 칸으로 나뉜 화면은 파일 이름에 해가 없다(태백)
  // 「재정공시」 제목이라고 깎지 않는다 — 강서구는 재정공시방에 사업예산서 글이 섞여 올라온다
  return { 점수, 근거: (해맞음.length ? 해맞음 : 좋은).slice(0, 4) };
}

async function 열기(탭, url) {
  탭.상태.코드 = null; 탭.상태.실패 = '';
  await 탭.보내기('Page.navigate', { url });
  // ⚠️ loadEventFired 는 앞 화면 신호에 속는다 — 글자 수를 재며 기다린다(check_budget_docs.js 와 같은 까닭)
  const 끝 = Date.now() + 기다림, 처음 = Date.now();
  while (Date.now() < 끝) {
    const r = await 탭.보내기('Runtime.evaluate', {
      expression: 'location.href.slice(0,8) + "|" + document.readyState + "|" + (document.body ? document.body.innerText.length : 0)',
      returnByValue: true,
    });
    const [주소, 상태글, 길이] = String((r.result && r.result.value) || '').split('|');
    if (주소.startsWith('http') && Number(길이) > 120 && (상태글 === 'complete' || Date.now() - 처음 > 6000)) {
      await 잠깐(1200);
      return true;
    }
    await 잠깐(400);
  }
  return false;
}
async function 긁기(탭, 식) {
  const r = await 탭.보내기('Runtime.evaluate', { expression: 식, returnByValue: true, timeout: 8000 });
  try { return r.result && r.result.value ? JSON.parse(r.result.value) : null; } catch (e) { return null; }
}
async function 보기(탭, url) {
  await 열기(탭, url);
  const v = (await 긁기(탭, 긁개)) || {};
  return { 주소: v.주소 || url, 제목: v.제목 || '', 파일: v.파일 || [], 글: (await 긁기(탭, 글모으개)) || [], 메뉴: (await 긁기(탭, 메뉴모으개)) || [] };
}

async function 한곳(탭, 곳) {
  const 해들 = [곳.예산연도, 곳.예산연도 - 1].map(String);
  const 본 = [];
  if (곳.BUDLK) {
    const 첫 = await 보기(탭, 곳.BUDLK);
    본.push({ ...첫, 어떻게: 'BUDLK', ...매기기(첫, 해들) });
    // 첫 화면 메뉴에 없으면 누리집 첫 화면 메뉴도 본다
    let 메뉴 = 첫.메뉴;
    if (!메뉴.length) {
      try { 메뉴 = (await 보기(탭, new URL(곳.BUDLK).origin + '/')).메뉴; } catch (e) { 메뉴 = []; }
    }
    for (const m of 메뉴.slice(0, 4)) {
      const v = await 보기(탭, m.주소);
      본.push({ ...v, 어떻게: '메뉴', 메뉴글: m.글, ...매기기(v, 해들) });
    }
  }
  본.sort((a, b) => b.점수 - a.점수);
  const 최고 = 본[0];
  // ponytail: 점수 4(올해·작년 예산서 이름 하나, 또는 예산서 이름 하나 + 제목 「예산서」)를 문턱으로 — 틀리게 고른 곳은 사람이 '사람' 줄로 덮는다
  if (!최고 || 최고.점수 < 4) {
    return { 이름: 곳.이름, 주소: '', 어떻게: '못 찾음', 점수: 최고 ? 최고.점수 : 0, 근거: 최고 ? 최고.근거 : [], BUDLK: 곳.BUDLK, 본: 본.map(v => v.주소) };
  }
  return { 이름: 곳.이름, 주소: 최고.주소, 어떻게: 최고.어떻게, 점수: 최고.점수, 근거: 최고.근거, BUDLK: 곳.BUDLK, ...(최고.메뉴글 ? { 메뉴글: 최고.메뉴글 } : {}) };
}

async function main() {
  if (!크롬자리) throw new Error('크롬을 못 찾겠다');
  const 옛 = fs.existsSync(OUT) ? JSON.parse(fs.readFileSync(OUT, 'utf-8')).곳 : {};
  const 목록 = JSON.parse(fs.readFileSync(path.join(ROOT, 'site', 'data', 'loc', 'index.json'), 'utf-8'));
  let 곳들 = 목록.곳.filter(x => !x.진행만).map(x => {
    const d = JSON.parse(fs.readFileSync(path.join(ROOT, 'site', 'data', 'loc', `${x.cd}.json`), 'utf-8'));
    return { laf_cd: x.cd, 이름: d.이름, BUDLK: d.원문.예산서, 예산연도: +d.예산연도 };
  }).filter(x => !(옛[x.laf_cd] && 옛[x.laf_cd].어떻게 === '사람'));
  const j = process.argv.indexOf('--곳');
  if (j > 0) { const 몇 = new Set(process.argv[j + 1].split(',')); 곳들 = 곳들.filter(x => 몇.has(x.laf_cd)); }

  const 프로필 = fs.mkdtempSync(path.join(os.tmpdir(), 'lf-places-'));
  const 크롬 = 크롬띄우기(프로필);
  await 붙을때까지();

  const 새 = {};
  let 다음 = 0, 끝난 = 0;
  const 일꾼 = async () => {
    const 탭 = await 탭열기();
    while (true) {
      const k = 다음++;
      if (k >= 곳들.length) break;
      const 곳 = 곳들[k];
      try { 새[곳.laf_cd] = await 한곳(탭, 곳); }
      catch (e) { 새[곳.laf_cd] = { 이름: 곳.이름, 주소: '', 어떻게: '못 찾음', 점수: 0, 근거: [], BUDLK: 곳.BUDLK, 실패: String(e).slice(0, 80) }; }
      if (++끝난 % 10 === 0) process.stdout.write(`   ${끝난}/${곳들.length}\n`);
    }
    탭.ws.close();
    await fetch(`http://127.0.0.1:${PORT}/json/close/${탭.tab.id}`).catch(() => {});
  };
  await Promise.all(Array.from({ length: 한번에 }, 일꾼));

  const 전부 = { ...옛, ...새 };
  const 차례 = Object.fromEntries(Object.keys(전부).sort().map(k => [k, 전부[k]]));
  fs.writeFileSync(OUT, JSON.stringify({ 만든날: new Date().toISOString().slice(0, 10), 곳: 차례 }, null, 1));

  const 셈 = {};
  for (const v of Object.values(차례)) 셈[v.어떻게] = (셈[v.어떻게] || 0) + 1;
  console.log('\n이번에 본 곳', 곳들.length, '· 전체', 셈);
  console.log('적음:', OUT);
  크롬.kill();
  await 잠깐(1500);
  try { fs.rmSync(프로필, { recursive: true, force: true }); } catch (_) {}
}

main().catch(e => { console.error('FAIL', e); process.exit(1); });
