// 누리집 검색에 걸린 글(D 꼬리표)로 들어가 그 글의 첨부 파일 목록을 긁는다 — 둘째 트랙(열어 보기)의 앞 단계.
//   (2026-11-12 사용자 「공시된 링크를 확인하는 거 먼저하고 열어보는 것도」) — 받아 여는 것은 read_disclosure_files.py 가 한다.
//
//   node scripts/open_search_posts.js           data/disclosure_search.json 의 「링크」 중 2024년 뒤 날짜·메뉴로 걸린 낱말만
//   결과: data/disclosure_posts.json — {곳: {낱말: [{글, 주소, 화면:{제목, 끝주소, 파일}}]}}  (앞 결과와 합침)
// 고르기: 낱말마다 링크 글자에 2024~2026 이 든 것 먼저, 셋까지. 같은 주소는 한 번만.
const fs = require('fs');
const path = require('path');
const os = require('os');
const R = require('./recheck_disclosure.js');

const ROOT = path.dirname(__dirname);
const OUT = path.join(ROOT, 'data', 'disclosure_posts.json');

(async () => {
  const 검색 = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'disclosure_search.json'), 'utf-8')).곳;
  const 나온 = fs.existsSync(OUT) ? JSON.parse(fs.readFileSync(OUT, 'utf-8')).곳 : {};
  const 일감 = [];
  for (const [cd, v] of Object.entries(검색))
    for (const [w, x] of Object.entries(v.낱말 || {})) {
      if (!(x.링크 || []).length || (나온[cd] && 나온[cd][w])) continue;   // 이미 연 것은 다시 안 연다
      const 링크 = [...x.링크].sort((a, b) => /202[4-6]/.test(b.글) - /202[4-6]/.test(a.글))
        .filter((l, i, a) => a.findIndex(m => m.주소 === l.주소) === i && !/download|filedown|atchfile/i.test(l.주소)).slice(0, 3);
      if (링크.length) 일감.push({ cd, 이름: v.이름, w, 링크 });
    }
  console.log(`글 열기 ${일감.length}건(곳·낱말)`);
  const 크롬 = R.크롬띄우기(fs.mkdtempSync(path.join(os.tmpdir(), 'lf-posts-')));
  await R.붙을때까지();
  // 탭 넷 — 한 곳은 한 탭에서만(곳별로 묶어 나눈다)
  const 묶 = [[], [], [], []];
  for (const 일 of 일감.sort((a, b) => a.cd.localeCompare(b.cd)))
    (묶.find(b => b.length && b[b.length - 1].cd === 일.cd) || 묶.reduce((a, b) => (a.length <= b.length ? a : b))).push(일);
  let 끝난 = 0, 파일있음 = 0;
  await Promise.all(묶.map(async b => {
    const 탭 = await R.탭열기();
    탭.듣기('Page.javascriptDialogOpening', () => 탭.보내기('Page.handleJavaScriptDialog', { accept: true }));
    for (const 일 of b) {
      const 본 = [];
      for (const l of 일.링크) {
        try {
          const 화면 = await R.한곳(탭, { laf_cd: 일.cd, 이름: 일.이름, 주소: l.주소 });
          본.push({ ...l, 화면: { 제목: 화면.제목, 끝주소: 화면.들어간주소 || 화면.끝주소, 파일: 화면.파일 || [] } });
          if ((화면.파일 || []).some(f => R.뜻있나(f.이름))) 파일있음++;
        } catch (e) { 본.push({ ...l, 까닭: '틀림 ' + String(e).slice(0, 60) }); }
      }
      (나온[일.cd] = 나온[일.cd] || {})[일.w] = 본;
      if (++끝난 % 50 === 0) console.log(`   ${끝난}/${일감.length}`);
    }
  }));
  fs.writeFileSync(OUT, JSON.stringify({ 만든날: new Date().toISOString().slice(0, 10), 곳: 나온 }, null, 0));
  console.log(`글 열기 ${일감.length}건 → 파일 있는 글 ${파일있음} · 적음 ${OUT}`);
  크롬.kill();
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
