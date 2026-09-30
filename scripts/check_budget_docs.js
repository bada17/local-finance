// 예산서·결산서 게시판을 **브라우저로** 본다 — 「공개 평가」(score.html) 의 근거를 모은다.
//
//   node scripts/check_budget_docs.js               243곳 전부 (한 시간 안팎)
//   node scripts/check_budget_docs.js --only 12     앞 12곳만 (시험)
//   node scripts/check_budget_docs.js --곳 1100000,4613000   몇 곳만 다시 — 결과를 합친다
//
// 어디를 보나 — 지방재정365 가 자치단체마다 준 「예산서」·「결산서」 주소(BUDLK·SETLK, site/data/loc/<코드>.json 의 원문).
//   대부분 게시판 목록이다. 목록의 **글 제목**(「2026년 성인지 예산서」 따위)을 적어 두고,
//   올해 본예산 글·가장 새 결산 글에 **한 겹만** 들어가 붙은 파일 이름과 형식을 적는다.
//
// ⭐ 여기서는 **모으기만** 한다. 무엇이 「있다/없다」인지는 build_score.py 가 이 파일을 읽어 가른다
//    (잣대를 바꿔도 다시 긁지 않아도 되게).
// ⚠️ 「못 찾았다」는 「없다」가 아니다 — 자동이 못 들어간 곳이 섞인다. build_score.py 는 그런 칸을 「미확인」으로 둔다.
// ⚠️ 두 겹 이상 들어가지 않는다 — 어디를 본 것인지 알 수 없게 된다(recheck_disclosure.js 와 같은 규칙).
//
// 결과: data/budget_docs.json

const fs = require('fs');
const path = require('path');
const os = require('os');
const { 크롬자리, 크롬띄우기, 붙을때까지, 탭열기, PORT, 긁개, 뜻있나, 기다림 } = require('./recheck_disclosure.js');

const ROOT = path.dirname(__dirname);
const OUT = path.join(ROOT, 'data', 'budget_docs.json');
const 한번에 = 4;
const 잠깐 = ms => new Promise(r => setTimeout(r, ms));

// 목록에서 글 제목을 모은다 — 예산·결산 문서 이름이 든 링크만. 누르는 글(href="#")은 몇 번째인지 적는다
const 글모으개 = String.raw`(() => {
  const 뜻 = /예산|결산|명세서|설명서|성인지|기후|온실가스|탄소|의견서|중기|재정계획/;
  const out = [], 본 = new Set();
  [...document.querySelectorAll('a')].forEach((a, 번째) => {
    const t = (a.textContent || '').replace(/\s+/g, ' ').trim();
    if (t.length < 4 || t.length > 110 || !뜻.test(t) || 본.has(t)) return;
    const raw = (a.getAttribute('href') || '').trim(), h = a.href || '';
    const 누름 = ((!raw || raw.startsWith('#')) && !!a.getAttribute('onclick')) || /^javascript:\s*\w+\(/i.test(raw);
    if (!누름 && !/^https?:/.test(h)) return;
    if (!누름 && h.split('#')[0] === location.href.split('#')[0]) return;
    let 남 = false; try { 남 = !누름 && new URL(h).hostname !== location.hostname; } catch (e) {}
    본.add(t);
    out.push({ 글: t, 주소: 누름 ? '' : h.slice(0, 220), 번째: 누름 ? 번째 : -1, 남 });
  });
  return JSON.stringify(out.slice(0, 60));
})()`;

async function 열기(탭, url) {
  const { 보내기, 상태 } = 탭;
  상태.코드 = null; 상태.실패 = '';
  await 보내기('Page.navigate', { url });
  return 기다리기(탭);
}
// ⚠️ loadEventFired 는 앞 화면 신호에 속는다 — 눌러 보며 기다린다(recheck_disclosure.js 와 같은 까닭)
async function 기다리기(탭) {
  const 끝 = Date.now() + 기다림;
  const 처음 = Date.now();
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

// 들어갈 글 고르기 — 예산은 올해(없으면 작년) **본예산** 글, 결산은 가장 새 해 결산 글. 남의 누리집 글은 빼고.
function 고르기(글들, 종류, 해들) {
  const 해of = t => { const m = t.match(/(20\d\d)/) || t.match(/(?:^|\D)(\d\d)\s*년/); return m ? (m[1].length === 2 ? '20' + m[1] : m[1]) : ''; };
  const 점수 = g => {
    const t = g.글, 해 = 해of(t);
    if (g.남) return -99;
    let s = 0;
    const k = 해들.indexOf(해);
    if (k < 0) return -99;
    s += (해들.length - k) * 10;
    if (종류 === '예산') {
      if (!/예산/.test(t)) return -99;
      if (/추경|추가경정|제\s*\d\s*회|변경|수정/.test(t)) s -= 8;
      if (/본예산|당초|예산서|명세서|설명서|성인지|기후|의견서/.test(t)) s += 4;
    } else {
      if (!/결산/.test(t)) return -99;
      if (/결산서|세입세출결산|결산\s*검사|성인지/.test(t)) s += 4;
    }
    return s;
  };
  return 글들.map(g => ({ ...g, 점수: 점수(g) })).filter(g => g.점수 > 0).sort((a, b) => b.점수 - a.점수);
}

async function 한판(탭, url, 종류, 해들) {
  const 판 = { 주소: url, 코드: null, 실패: '', 제목: '', 목록글: [], 파일: [], 들어간글: [] };
  if (!url) { 판.실패 = '주소 없음'; return 판; }
  const 준비 = await 열기(탭, url);
  판.코드 = 탭.상태.코드; 판.실패 = 탭.상태.실패 || (준비 ? '' : '안 열림');
  const 첫 = await 긁기(탭, 긁개);
  if (첫) { 판.제목 = 첫.제목; 판.파일 = 첫.파일; 판.끝주소 = 첫.주소; }
  판.목록글 = (await 긁기(탭, 글모으개)) || [];
  // 목록 화면에 이미 뜻 있는 파일이 셋 넘게 걸리면(글 화면이거나 목록에 파일을 늘어놓은 곳) 들어가지 않는다
  if (판.파일.filter(f => 뜻있나(f.이름)).length >= 3) return 판;
  const 갈글 = 고르기(판.목록글, 종류, 해들).slice(0, 종류 === '예산' ? 3 : 2);
  for (const [k, g] of 갈글.entries()) {
    if (g.번째 >= 0) {
      if (k) await 열기(탭, url);
      await 탭.보내기('Runtime.evaluate', { expression: `document.querySelectorAll('a')[${g.번째}].click()` });
      await 잠깐(2500);
      await 기다리기(탭);
    } else {
      await 열기(탭, g.주소);
    }
    const v = await 긁기(탭, 긁개);
    판.들어간글.push({ 글: g.글, 주소: (v && v.주소) || g.주소, 파일: v ? v.파일 : [], 날짜: v ? v.날짜 : '' });
  }
  return 판;
}

async function main() {
  if (!크롬자리) throw new Error('크롬을 못 찾겠다');
  const 목록 = JSON.parse(fs.readFileSync(path.join(ROOT, 'site', 'data', 'loc', 'index.json'), 'utf-8'));
  let 곳들 = 목록.곳.filter(x => !x.진행만).map(x => {
    const d = JSON.parse(fs.readFileSync(path.join(ROOT, 'site', 'data', 'loc', `${x.cd}.json`), 'utf-8'));
    return { laf_cd: x.cd, 이름: d.이름, 예산서: d.원문.예산서, 결산서: d.원문.결산서, 예산연도: +d.예산연도, 결산연도: +d.결산연도 };
  });
  const i = process.argv.indexOf('--only');
  if (i > 0) 곳들 = 곳들.slice(0, parseInt(process.argv[i + 1], 10));
  const j = process.argv.indexOf('--곳');
  const 몇곳 = j > 0 ? new Set(process.argv[j + 1].split(',')) : null;
  if (몇곳) 곳들 = 곳들.filter(x => 몇곳.has(x.laf_cd));

  const 프로필 = fs.mkdtempSync(path.join(os.tmpdir(), 'lf-budget-'));
  const 크롬 = 크롬띄우기(프로필);
  await 붙을때까지();

  const 결과 = [];
  let 다음 = 0, 끝난 = 0;
  const 일꾼 = async () => {
    const 탭 = await 탭열기();
    while (true) {
      const k = 다음++;
      if (k >= 곳들.length) break;
      const 곳 = 곳들[k];
      const 줄 = { laf_cd: 곳.laf_cd, 이름: 곳.이름 };
      for (const [종류, url, 해들] of [
        ['예산', 곳.예산서, [곳.예산연도, 곳.예산연도 - 1].map(String)],
        ['결산', 곳.결산서, [곳.결산연도 + 1, 곳.결산연도, 곳.결산연도 - 1].map(String)],
      ]) {
        try { 줄[종류] = await 한판(탭, url, 종류, 해들); }
        catch (e) { 줄[종류] = { 주소: url, 실패: String(e).slice(0, 80), 파일: [], 목록글: [], 들어간글: [] }; }
      }
      결과.push(줄);
      끝난++;
      if (끝난 % 10 === 0) process.stdout.write(`   ${끝난}/${곳들.length}\n`);
    }
    탭.ws.close();
    await fetch(`http://127.0.0.1:${PORT}/json/close/${탭.tab.id}`).catch(() => {});
  };
  await Promise.all(Array.from({ length: 한번에 }, 일꾼));

  // 몇 곳만 다시 본 것이면 앞의 결과에 합친다
  let 전부 = 결과;
  if (몇곳 && fs.existsSync(OUT)) {
    const 새 = new Map(결과.map(r => [r.laf_cd, r]));
    전부 = JSON.parse(fs.readFileSync(OUT, 'utf-8')).곳.map(r => 새.get(r.laf_cd) || r);
    for (const r of 결과) if (!전부.some(x => x.laf_cd === r.laf_cd)) 전부.push(r);
  }
  전부.sort((a, b) => a.laf_cd.localeCompare(b.laf_cd));
  fs.writeFileSync(OUT, JSON.stringify({ 만든날: new Date().toISOString().slice(0, 10), 곳: 전부 }));

  const 셈 = k => 결과.filter(r => r[k] && ((r[k].파일 || []).length || (r[k].들어간글 || []).some(g => g.파일.length))).length;
  console.log(`\n본 곳 ${결과.length} · 예산 파일 잡힘 ${셈('예산')} · 결산 파일 잡힘 ${셈('결산')}`);
  console.log('적음: data/budget_docs.json');
  크롬.kill();
  await 잠깐(1500);
  try { fs.rmSync(프로필, { recursive: true, force: true }); } catch (_) {}
}

main().catch(e => { console.error('FAIL', e); process.exit(1); });
