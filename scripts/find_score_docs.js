// 투명성 지표(score.html) 문서 항목을 **별도 문서로 올렸나** 끝까지 찾는다 — 예산세부명세서·예산설명서·결산서·성인지 예결산서·
//   중기지방재정계획·주민참여예산 의견서·기후예산서.
//   (2026-11-12 사용자 「문서 파일 끝까지 찾는 봇」 「파일 열어봐서 있는 게 아니라 별도로 정리해서 올리는지 확인하고 싶은 것」)
//   → 판정은 **글 제목·파일 이름**에 그 문서 이름(build_score.py 의 잣대)이 있나. 파일 안 글자는 안 본다.
//
//   node scripts/find_score_docs.js 일감.json      일감 = build_score.py --문서일감 이 만든다(아직 ? 인 곳·항목만)
//   결과: data/score_docs.json (앞 결과와 합침) — {곳: {항목: {찾음, 글, 주소, 어디, 본곳:[…]}}}
//
// 차례(찾으면 그 항목은 멈춘다) —
//   ① 예산서·결산서 게시판 1~3쪽의 글 제목, 그 화면의 파일 이름
//   ② 그 게시판에서 남은 항목 이름이 든 글(또는 올해·지난해 예산서·결산서 글) 다섯까지 들어가 붙은 파일 이름
//   ③ 누리집 통합검색(항목마다 한 말) → 걸린 링크 글자, 둘까지 들어가 붙은 파일 이름
//   ④ 사이트맵·전체메뉴에서 그 이름이 든 메뉴 → 들어가 파일 이름
//   못 찾으면 「본곳」에 어디까지 봤는지 남긴다 — 「못 찾음」과 「안 올림」을 가르려고.
const fs = require('fs');
const path = require('path');
const os = require('os');
const R = require('./recheck_disclosure.js');
const S = require('./search_disclosure_items.js');

const ROOT = path.dirname(__dirname);
const OUT = path.join(ROOT, 'data', 'score_docs.json');
const 쉼 = ms => new Promise(r => setTimeout(r, ms));

// 화면의 링크 글자 전부(숨은 메뉴 포함) + 쪽 넘김 링크
const 링크들 = `(() => JSON.stringify({
  주소: location.href,
  a: [...document.querySelectorAll('a')].map((a, i) => ({ 글: (a.innerText || a.textContent || a.title || '').replace(/\\s+/g, ' ').trim().slice(0, 140), 주소: a.href || '', 번째: i }))
       .filter(x => x.글.length >= 2),
  쪽: [...document.querySelectorAll('[class*=pag] a, [class*=Pag] a, [id*=pag] a, .page a, .paging a')]
       .map((a, i) => ({ 글: (a.innerText || a.textContent || '').trim(), 주소: a.href || '' })).filter(x => /^[23]$/.test(x.글)),
  사이트맵: ([...document.querySelectorAll('a')].find(a => /사이트\\s*맵|sitemap|전체\\s*메뉴/i.test((a.innerText || a.textContent || a.title || '') + ' ' + a.href) && /^https?:/.test(a.href)) || {}).href || ''
}))()`;

async function 열기(탭, 주소) {
  await 탭.보내기('Page.navigate', { url: 주소 });
  await S.다될때(탭, 1200);
  await 쉼(600);
}
async function 보기(탭) {
  const r = await 탭.보내기('Runtime.evaluate', { expression: 링크들, returnByValue: true, timeout: 8000 });
  return r.result && r.result.value ? JSON.parse(r.result.value) : { a: [], 쪽: [], 사이트맵: '' };
}
async function 파일이름(탭, 주소) {   // 글 하나에 붙은 파일 이름 — recheck_disclosure.js 의 긁개
  const 화면 = await R.한곳(탭, { laf_cd: '', 이름: '', 주소 });
  return (화면.파일 || []).filter(f => R.뜻있나(f.이름)).map(f => ({ 글: f.이름, 주소: f.주소 && /^https?:/.test(f.주소) ? f.주소 : 화면.끝주소 }));
}

async function 한곳(탭, 일) {
  const 남 = new Map(일.항목.map(h => [h.키, { ...h, 잣 : new RegExp(h.잣대, 'i') }]));
  const 결과 = {}, 본곳 = [];
  // 꼬리표(11-12 사용자 「보기 쉽고 어렵고, 몇 번 클릭해야 볼 수 있고 나중에 측정」) —
  //   방법(목록·글 안·검색·사이트맵), 클릭(홈에서 그 이름이 보일 때까지 누른 수, 게시판까지 깊이를 모르면 null), 쪽, 형식(파일 확장자)
  // 비슷한 이름 — 못 찾은 칸의 규칙을 넓히려고, 본 글·파일 이름 가운데 그 항목의 느슨한 말이 든 것을 모은다(11-12)
  const 느슨 = { 명세서: /명세/, 설명서: /설명/, 결산서: /결산/, 성인지: /성인지|양성|성별/, 중기: /중기|재정\s*계획/, 의견서: /의견/, 기후: /기후|탄소|온실|녹색/ };
  const 비슷 = new Map();
  const 대보기 = (줄들, 어디, 방법, 클릭, 쪽 = null) => {
    for (const l of 줄들) for (const k of 남.keys())
      if (느슨[k] && l.글.length <= 90 && 느슨[k].test(l.글)) {
        const m = 비슷.get(k) || new Map();
        if (m.size < 15 && !m.has(l.글)) m.set(l.글, 어디);
        비슷.set(k, m);
      }
    // 해: 글자에 든 가장 큰 20xx(또는 ’xx). 양식·서식·견본은 문서가 아니다. 2024 앞 해만 적힌 것은 옛 문서라 안 친다.
    // 검색으로만 걸린 것은 해가 적혀 있어야 친다(검색은 아무 글이나 걸린다 — 「기후예산」 한 줄 따위)
    const 해 = s => Math.max(0, ...[...s.matchAll(/20(1\d|2\d)|[’'‘](1\d|2\d)\s*(년|회계)/g)].map(m => 2000 + +(m[1] || m[2])));
    for (const [k, h] of 남) {
      const x = 줄들.find(l => h.잣.test(l.글) && !/양식|서식|견본|작성\s*예시|신청서/.test(l.글)
        && (해(l.글) === 0 ? 방법 !== '검색으로만' : 해(l.글) >= 2024)
        // 검색 결과는 문서 제목 꼴만(수원 「양성평등기금 지원사업 … 성료」 뉴스가 「성인지」로 걸렸다)
        && (방법 !== '검색으로만' || (l.글.length <= 90 && /예산서|결산서|예산안|공시|계획|명세서|설명서|의견서|보고서/.test(l.글))));
      if (!x) continue;
      const 형식 = ((x.글 + ' ' + (x.주소 || '')).match(/\.(pdf|hwpx?|xlsx?|csv|zip|docx?)\b/i) || [])[1] || '';
      결과[k] = { 찾음: true, 글: x.글.slice(0, 120), 주소: (x.주소 || '').slice(0, 300), 어디, 방법, 클릭, 쪽, 형식: 형식.toLowerCase(), 해: 해(x.글) || null };
      남.delete(k);
    }
  };
  // 홈에서 게시판까지 몇 번 — 홈 화면에 그 게시판 링크가 있으면 1(메뉴), 사이트맵에 있으면 2, 못 찾으면 null
  const 깊이 = {};
  if (일.홈) {
    try {
      await 열기(탭, 일.홈);
      const v = await 보기(탭);
      const 같음 = (a, b) => a && b && a.split('#')[0].replace(/\/$/, '') === b.split('#')[0].replace(/\/$/, '');
      for (const u of [일.예산주소, 일.결산주소]) if (u && v.a.some(l => 같음(l.주소, u))) 깊이[u] = 1;
      if (v.사이트맵 && [일.예산주소, 일.결산주소].some(u => u && !깊이[u])) {
        await 열기(탭, v.사이트맵);
        const m = await 보기(탭);
        for (const u of [일.예산주소, 일.결산주소]) if (u && !깊이[u] && m.a.some(l => 같음(l.주소, u))) 깊이[u] = 2;
      }
    } catch (e) { /* 깊이 모름 */ }
  }
  const 더 = (a, b) => (a == null ? null : a + b);
  // ① ② 예산서·결산서 게시판
  for (const [판, 주소] of [['예산서 게시판', 일.예산주소], ['결산서 게시판', 일.결산주소]]) {
    if (!주소 || !남.size) continue;
    let 글후보 = [];
    try {
      await 열기(탭, 주소);
      for (let 쪽 = 1; 쪽 <= 3 && 남.size; 쪽++) {
        const v = await 보기(탭);
        본곳.push(`${판} ${쪽}쪽`);
        const 판깊이 = 깊이[주소] ?? null;
        대보기(v.a, `${판} ${쪽}쪽 글 제목`, '게시판 목록', 더(판깊이, 쪽 - 1), 쪽);
        const 파 = await 파일이름(탭, v.주소).catch(() => []);
        대보기(파, `${판} ${쪽}쪽에 붙은 파일`, '게시판 목록', 더(판깊이, 쪽 - 1), 쪽);
        글후보 = 글후보.concat(v.a.filter(l => /^https?:/.test(l.주소) && l.주소.split('#')[0] !== v.주소.split('#')[0]
          && ([...남.values()].some(h => h.잣.test(l.글)) || /(202[4-6]).*(예산|결산)|(예산|결산).*(202[4-6])/.test(l.글))).map(l => ({ ...l, 쪽 })));
        const 다음 = v.쪽.find(p => p.글 === String(쪽 + 1));
        if (!다음 || !/^https?:/.test(다음.주소)) break;
        await 열기(탭, 다음.주소);
      }
      for (const l of 글후보.filter((l, i, a) => a.findIndex(m => m.주소 === l.주소) === i).slice(0, 5)) {
        if (!남.size) break;
        const 파 = await 파일이름(탭, l.주소).catch(() => []);
        본곳.push(`${판} 글 「${l.글.slice(0, 30)}」`);
        대보기(파, `${판} 글 「${l.글.slice(0, 40)}」에 붙은 파일`, '게시판 글 안', 더(깊이[주소] ?? null, (l.쪽 || 1)), l.쪽 || 1);
      }
    } catch (e) { 본곳.push(`${판} 못 엶 ${String(e).slice(0, 40)}`); }
  }
  // ③ 누리집 통합검색
  for (const [k, h] of [...남]) {
    if (!남.has(k) || !일.홈) continue;
    try {
      await 열기(탭, 일.홈);
      const r = await 탭.보내기('Runtime.evaluate', { expression: S.검색하기(h.검색말), returnByValue: true });
      const 방법 = (r.result && r.result.value) || '못 보냄';
      if (방법 === '검색칸 못 찾음' || 방법 === '못 보냄') { 본곳.push(`검색 「${h.검색말}」 ${방법}`); continue; }
      await S.다될때(탭, 3500);
      const v = await 보기(탭);
      본곳.push(`검색 「${h.검색말}」`);
      대보기(v.a.filter(l => !/검색어|검색결과/.test(l.글)), `누리집 검색 「${h.검색말}」 결과 글`, '검색으로만', 2);
      const 걸린 = v.a.filter(l => /^https?:/.test(l.주소) && l.글.includes(h.검색말)).slice(0, 2);
      for (const l of 걸린) {
        if (!남.size) break;
        const 파 = await 파일이름(탭, l.주소).catch(() => []);
        대보기(파, `검색 글 「${l.글.slice(0, 40)}」에 붙은 파일`, '검색으로만', 3);
      }
    } catch (e) { 본곳.push(`검색 「${h.검색말}」 틀림`); }
  }
  // ④ 사이트맵
  if (남.size && 일.홈) {
    try {
      await 열기(탭, 일.홈);
      const 맵 = (await 보기(탭)).사이트맵;
      if (맵) {
        await 열기(탭, 맵);
        const v = await 보기(탭);
        본곳.push('사이트맵');
        for (const [k, h] of [...남]) {
          // 검색 주소·「검색어」 줄은 메뉴가 아니다(포천·나주 — 첫 화면의 「최근 검색어」에 봇이 넣은 말이 남아 메뉴처럼 걸렸다)
          const 메뉴 = v.a.find(l => h.잣.test(l.글) && /^https?:/.test(l.주소) && !/search|query=|srch|keyword=|#$/i.test(l.주소) && !/검색어/.test(l.글));
          if (!메뉴) continue;
          결과[k] = { 찾음: true, 글: 메뉴.글, 주소: 메뉴.주소, 어디: '사이트맵 메뉴 이름', 방법: '사이트맵 메뉴', 클릭: 2, 쪽: null, 형식: '' };
          남.delete(k);
        }
      } else 본곳.push('사이트맵 없음');
    } catch (e) { 본곳.push('사이트맵 틀림'); }
  }
  for (const k of 남.keys()) 결과[k] = { 찾음: false, 비슷: [...(비슷.get(k) || new Map())].map(([글, 어디]) => ({ 글, 어디 })) };
  for (const k of Object.keys(결과)) 결과[k].본곳 = 본곳;
  return 결과;
}

(async () => {
  const 일감 = JSON.parse(fs.readFileSync(process.argv[2], 'utf-8'));
  const 나온 = fs.existsSync(OUT) ? JSON.parse(fs.readFileSync(OUT, 'utf-8')).곳 : {};
  const 크롬 = R.크롬띄우기(fs.mkdtempSync(path.join(os.tmpdir(), 'lf-scoredocs-')));
  await R.붙을때까지();
  let 다음 = 0, 끝난 = 0, 찾음 = 0;
  await Promise.all([0, 1, 2, 3].map(async () => {   // 탭 넷 — 한 곳은 한 탭에서만
    const 탭 = await R.탭열기();
    탭.듣기('Page.javascriptDialogOpening', () => 탭.보내기('Page.handleJavaScriptDialog', { accept: true }));
    while (다음 < 일감.length) {
      const 일 = 일감[다음++];
      let v;
      try { v = await 한곳(탭, 일); } catch (e) { v = Object.fromEntries(일.항목.map(h => [h.키, { 찾음: false, 본곳: ['틀림 ' + String(e).slice(0, 60)] }])); }
      나온[일.cd] = { ...(나온[일.cd] || {}), ...v };
      찾음 += Object.values(v).filter(x => x.찾음).length;
      if (++끝난 % 20 === 0) {   // 도는 중에도 볼 수 있게 20곳마다 적는다
        console.log(`   ${끝난}/${일감.length} · 찾음 ${찾음}`);
        fs.writeFileSync(OUT, JSON.stringify({ 만든날: new Date().toISOString().slice(0, 10), 곳: 나온 }, null, 0));
      }
    }
  }));
  fs.writeFileSync(OUT, JSON.stringify({ 만든날: new Date().toISOString().slice(0, 10), 곳: 나온 }, null, 0));
  console.log(`문서 찾기 ${일감.length}곳 · ${일감.reduce((s, x) => s + x.항목.length, 0)}칸 → 찾음 ${찾음} · 적음 ${OUT}`);
  크롬.kill();
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
