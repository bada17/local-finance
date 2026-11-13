// 투명성 지표(score.html)의 「사람이 볼 칸」을 봇이 할 수 있는 만큼 본다(2026-11-13 사용자
//   「일일 예산집행 공개가 게시판에 있는지 없는지 확인하면 되잖아」 「주민 공청회는 페이지가 있는지」 「의회 부분은 … 할 수 있는 걸」).
//
//   CDP_PORT=9451 node scripts/find_score_pages.js 일감.json     일감 = build_score.py --쪽일감 이 만든다
//   결과: data/score_pages.json — {곳: {일일, 공청회, 공론장, 별도, 예산안, 본곳}}
//
// 곳마다 —
//   ① 첫 화면 + 사이트맵(전체메뉴)의 링크 글자에서 메뉴를 찾는다: 일일 집행 · 공청회 · 공론장 · 따로 둔 재정 누리집
//      (메뉴 꼴만 — 30자 넘는 글은 공지 제목이라 안 친다)
//   ② 누리집 통합검색 「공청회」 — 메뉴가 없어도 공고 글이 걸리는지(몇 건·보기 둘)
//   ③ 예산서 게시판 1~2쪽에서 「예산안」 글(의회에 낸 안) → 둘까지 들어가 붙은 파일 이름, 목록 줄의 날짜
//   --의회: ③ 을 의회 누리집에서 — 첫 화면·사이트맵의 예산·결산·의안 메뉴(셋까지) → 예산안 글, 없으면 통합검색 「예산안」
//           결과는 곳마다 「의회」 칸에 덧붙인다(11-13 사용자 「그렇게 하자」)
// ⚠️ 못 찾으면 「못 찾음」이다. 「없음」으로 읽지 말 것.
const fs = require('fs');
const path = require('path');
const os = require('os');
const R = require('./recheck_disclosure.js');
const S = require('./search_disclosure_items.js');

const ROOT = path.dirname(__dirname);
const OUT = path.join(ROOT, 'data', 'score_pages.json');
const 쉼 = ms => new Promise(r => setTimeout(r, ms));

const 과녁 = {
  일일: /일일\s*(재정|예산|집행)|(예산|재정|세출)\s*집행\s*(현황|상황|공개|내역)|실시간\s*재정|예산\s*운영\s*상황/,
  공청회: /공청회|주민\s*설명회/,
  공론장: /공론|숙의|원탁\s*회의|시민\s*토론/,
  별도: /재정\s*(공시|정보|공개|운영)|예산\s*(공개|정보)|열린\s*재정|살림\s*(살이|공개)|재정\s*포털/,
};

// 링크 글자·주소 전부 + 사이트맵 주소. 목록 줄(tr·li)의 날짜도 같이 — 예산안 글 올린 날
const 링크들 = `(() => {
  const 날 = /(20\\d{2})\\s*[-.\\/년]\\s*(\\d{1,2})\\s*[-.\\/월]\\s*(\\d{1,2})/;
  return JSON.stringify({
    주소: location.href,
    a: [...document.querySelectorAll('a')].map(a => {
      const 줄 = a.closest('tr, li');
      const m = 줄 ? (줄.innerText || '').match(날) : null;
      return { 글: (a.innerText || a.textContent || a.title || '').replace(/\\s+/g, ' ').trim().slice(0, 140), 주소: a.href || '',
               날: m ? m[1] + '-' + m[2].padStart(2, '0') + '-' + m[3].padStart(2, '0') : '' };
    }).filter(x => x.글.length >= 2),
    쪽: [...document.querySelectorAll('[class*=pag] a, [class*=Pag] a, [id*=pag] a, .page a, .paging a')]
         .map(a => ({ 글: (a.innerText || a.textContent || '').trim(), 주소: a.href || '' })).filter(x => x.글 === '2'),
    사이트맵: ([...document.querySelectorAll('a')].find(a => /사이트\\s*맵|sitemap|전체\\s*메뉴/i.test((a.innerText || a.textContent || a.title || '') + ' ' + a.href) && /^https?:/.test(a.href)) || {}).href || ''
  });
})()`;

async function 열기(탭, 주소) {
  await 탭.보내기('Page.navigate', { url: 주소 });
  await S.다될때(탭, 1200);
  await 쉼(600);
}
async function 보기(탭) {
  const r = await 탭.보내기('Runtime.evaluate', { expression: 링크들, returnByValue: true, timeout: 8000 });
  return r.result && r.result.value ? JSON.parse(r.result.value) : { a: [], 쪽: [], 사이트맵: '' };
}
const 메뉴꼴 = l => l.글.length <= 30 && /^https?:|^javascript/.test(l.주소) && !/search|query=|srch|keyword=/i.test(l.주소) && !/검색어/.test(l.글);
// 짧은 메뉴 이름만 — 예결특위 회의 일정·「예산안 심의 절차」·「예결산 분석 지원」은 문서 자리가 아니다. 의안 목록에 예산안이 올라오는 곳이 많다
const 예결메뉴 = l => l.글.length <= 12 && /예산|결산|의안/.test(l.글) && !/위원회|위원|분석|절차|지원|제\s*\d+\s*회|특위|교육|과정|처리\s*결과/.test(l.글);
const 예산안글 = l => /예산안|예산\s?\(안\)/.test(l.글.replace(/\s+/g, ' ')) && !/승인|변경|정정|설명회|공청회|안내|일정|토론회|절차|분석|간담회|세미나|교육|심의\s*및/.test(l.글) && l.글.length <= 90;
const 새것 = l => (/202[56]/.test(l.글 + l.날) ? 2 : 0) + (/추가경정|추경/.test(l.글) ? 0 : 1);   // 올해·내년 본예산부터 본다
// 예산안 글 둘까지 들어가 붙은 파일 이름 — javascript: 글은 못 들어간다(파일 빈 채로 남김)
async function 안글보기(탭, 후보) {
  const 글 = [];
  for (const l of [...new Map(후보.map(l => [l.주소 || l.글, l])).values()].sort((a, b) => 새것(b) - 새것(a)).slice(0, 2)) {
    let 파일 = [];
    if (/^https?:/.test(l.주소)) {
      const 화면 = await R.한곳(탭, { laf_cd: '', 이름: '', 주소: l.주소 }).catch(() => ({ 파일: [] }));
      파일 = (화면.파일 || []).filter(f => R.뜻있나(f.이름)).map(f => f.이름.slice(0, 120)).slice(0, 15);
    }
    글.push({ 글: l.글, 날: l.날, 주소: (l.주소 || '').slice(0, 300), 파일, 명세서: 파일.some(f => /명세서/.test(f)) || /명세서/.test(l.글) });
  }
  return 글;
}
const 호스트 = u => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch (e) { return ''; } };

async function 한곳(탭, 일) {
  const 결과 = { 본곳: [] };
  const 홈호 = 호스트(일.홈);
  // ① 메뉴
  const 링크 = [];
  try {
    await 열기(탭, 일.홈);
    const v = await 보기(탭);
    링크.push(...v.a.map(l => ({ ...l, 어디: '첫 화면', 클릭: 1 })));
    결과.본곳.push('첫 화면');
    if (v.사이트맵) {
      await 열기(탭, v.사이트맵);
      const m = await 보기(탭);
      링크.push(...m.a.map(l => ({ ...l, 어디: '사이트맵', 클릭: 2 })));
      결과.본곳.push('사이트맵');
    } else 결과.본곳.push('사이트맵 없음');
  } catch (e) { 결과.본곳.push('첫 화면 못 엶 ' + String(e).slice(0, 40)); }
  for (const [k, re] of Object.entries(과녁)) {
    let 걸 = 링크.filter(l => 메뉴꼴(l) && re.test(l.글));
    if (k === '별도') 걸 = 걸.filter(l => /^https?:/.test(l.주소) && 호스트(l.주소) && 호스트(l.주소) !== 홈호 && !/lofin365|lofin\.mois/.test(l.주소));
    const 모 = [...new Map(걸.map(l => [l.글 + '|' + l.주소, l])).values()].slice(0, 5);
    결과[k] = { 찾음: 모.length > 0, 메뉴: 모.map(l => ({ 글: l.글, 주소: l.주소.slice(0, 300), 어디: l.어디, 클릭: l.클릭,
      지방재정365: /lofin365|lofin\.mois/.test(l.주소) })) };
  }
  const 따로 = (결과.별도.메뉴 || []).find(m => /^https?:/.test(m.주소));
  if (!결과.일일.찾음 && 따로) {
    try {
      await 열기(탭, 따로.주소);
      const v = await 보기(탭);
      결과.본곳.push('따로 둔 재정 누리집');
      const 걸 = v.a.filter(l => 메뉴꼴(l) && 과녁.일일.test(l.글)).slice(0, 3);
      if (걸.length) 결과.일일 = { 찾음: true, 메뉴: 걸.map(l => ({ 글: l.글, 주소: l.주소.slice(0, 300), 어디: '따로 둔 재정 누리집 「' + 따로.글 + '」', 클릭: 따로.클릭 + 1, 지방재정365: /lofin365|lofin\.mois/.test(l.주소) })) };
    } catch (e) { 결과.본곳.push('따로 둔 재정 누리집 못 엶'); }
  }
  // ② 통합검색 「공청회」
  try {
    await 열기(탭, 일.홈);
    const r = await 탭.보내기('Runtime.evaluate', { expression: S.검색하기('공청회'), returnByValue: true });
    const 방법 = (r.result && r.result.value) || '못 보냄';
    if (방법 === '검색칸 못 찾음' || 방법 === '못 보냄') { 결과.공청회.검색 = { 됨: false, 까닭: 방법 }; 결과.본곳.push('검색 ' + 방법); }
    else {
      await S.다될때(탭, 3500);
      const v = await 보기(탭);
      const 글 = v.a.filter(l => l.글.includes('공청회') && l.글.length <= 120 && !/검색어|검색결과/.test(l.글) && /^https?:|^javascript/.test(l.주소));
      const 모 = [...new Map(글.map(l => [l.글, l])).values()];
      결과.공청회.검색 = { 됨: true, 주소: v.주소.slice(0, 200), 링크수: v.a.length, 건: 모.length, 보기: 모.slice(0, 3).map(l => ({ 글: l.글, 날: l.날 })) };
      결과.본곳.push('검색 「공청회」');
    }
  } catch (e) { 결과.공청회.검색 = { 됨: false, 까닭: '틀림 ' + String(e).slice(0, 40) }; }
  // ③ 예산서 게시판의 예산안 글
  결과.예산안 = { 찾음: false, 글: [] };
  if (일.예산주소) {
    try {
      await 열기(탭, 일.예산주소);
      let 후보 = [];
      for (let 쪽 = 1; 쪽 <= 2; 쪽++) {
        const v = await 보기(탭);
        결과.본곳.push(`예산서 게시판 ${쪽}쪽`);
        후보 = 후보.concat(v.a.filter(예산안글));
        const 다음 = v.쪽[0];
        if (!다음 || !/^https?:/.test(다음.주소)) break;
        await 열기(탭, 다음.주소);
      }
      결과.예산안.글 = await 안글보기(탭, 후보);
      결과.예산안.찾음 = 결과.예산안.글.length > 0;
    } catch (e) { 결과.본곳.push('예산서 게시판 못 엶 ' + String(e).slice(0, 40)); }
  }
  return 결과;
}

async function 의회곳(탭, 일) {
  const 결과 = { 홈: 일.의회, 본곳: [], 메뉴: [], 글: [], 찾음: false };
  const 링크 = [];
  try {
    await 열기(탭, 일.의회);
    const v = await 보기(탭);
    링크.push(...v.a); 결과.본곳.push('첫 화면');
    if (v.사이트맵) { await 열기(탭, v.사이트맵); 링크.push(...(await 보기(탭)).a); 결과.본곳.push('사이트맵'); }
    else 결과.본곳.push('사이트맵 없음');
  } catch (e) { 결과.본곳.push('첫 화면 못 엶 ' + String(e).slice(0, 40)); return 결과; }
  const 메뉴 = [...new Map(링크.filter(l => 메뉴꼴(l) && /^https?:/.test(l.주소) && 예결메뉴(l)).map(l => [l.주소, l])).values()]
    .sort((a, b) => /의안/.test(a.글) - /의안/.test(b.글)).slice(0, 3);
  결과.메뉴 = 메뉴.map(l => ({ 글: l.글, 주소: l.주소.slice(0, 300) }));
  let 후보 = [];
  for (const m of 메뉴) {
    try { await 열기(탭, m.주소); 후보 = 후보.concat((await 보기(탭)).a.filter(예산안글)); 결과.본곳.push('메뉴 「' + m.글 + '」'); }
    catch (e) { 결과.본곳.push('메뉴 못 엶'); }
  }
  if (!후보.length) {
    try {
      await 열기(탭, 일.의회);
      const r = await 탭.보내기('Runtime.evaluate', { expression: S.검색하기('예산안'), returnByValue: true });
      const 방법 = (r.result && r.result.value) || '못 보냄';
      if (방법 === '검색칸 못 찾음' || 방법 === '못 보냄') 결과.본곳.push('검색 ' + 방법);
      else { await S.다될때(탭, 3500); 후보 = (await 보기(탭)).a.filter(예산안글); 결과.본곳.push('검색 「예산안」'); }
    } catch (e) { 결과.본곳.push('검색 틀림'); }
  }
  결과.글 = await 안글보기(탭, 후보);
  결과.찾음 = 결과.글.length > 0;
  return 결과;
}

(async () => {
  const 일감 = JSON.parse(fs.readFileSync(process.argv[2], 'utf-8'));
  const 나온 = fs.existsSync(OUT) && !process.argv.includes('--다시') ? JSON.parse(fs.readFileSync(OUT, 'utf-8')).곳 : {};
  const 의회모드 = process.argv.includes('--의회');
  const 할 = 일감.filter(x => 의회모드 ? x.의회 && !(나온[x.cd] || {}).의회 : !나온[x.cd]);   // 끊겨도 된다 — 다시 부르면 남은 곳만
  const 크롬 = R.크롬띄우기(fs.mkdtempSync(path.join(os.tmpdir(), 'lf-scorepages-')));
  await R.붙을때까지();
  let 다음 = 0, 끝난 = 0;
  const 적기 = () => fs.writeFileSync(OUT, JSON.stringify({ 만든날: new Date().toISOString().slice(0, 10), 곳: 나온 }, null, 0));
  await Promise.all([0, 1, 2, 3].map(async () => {
    const 탭 = await R.탭열기();
    탭.듣기('Page.javascriptDialogOpening', () => 탭.보내기('Page.handleJavaScriptDialog', { accept: true }));
    while (다음 < 할.length) {
      const 일 = 할[다음++];
      if (의회모드) { try { 나온[일.cd] = { ...나온[일.cd], 의회: await 의회곳(탭, 일) }; } catch (e) { 나온[일.cd] = { ...나온[일.cd], 의회: { 본곳: ['틀림 ' + String(e).slice(0, 60)] } }; } }
      else try { 나온[일.cd] = await 한곳(탭, 일); } catch (e) { 나온[일.cd] = { 본곳: ['틀림 ' + String(e).slice(0, 60)] }; }
      if (++끝난 % 20 === 0) { console.log(`   ${끝난}/${할.length}`); 적기(); }
    }
  }));
  적기();
  const 셈 = k => Object.values(나온).filter(x => x[k] && x[k].찾음).length;
  if (의회모드) { const 의 = Object.values(나온).filter(x => x.의회); console.log(`끝 — 의회 ${의.length}곳 · 예산안 글 ${의.filter(x => x.의회.찾음).length} · 명세서 ${의.filter(x => (x.의회.글 || []).some(g => g.명세서)).length}`); }
  else console.log(`끝 — ${Object.keys(나온).length}곳 · 일일 ${셈('일일')} · 공청회 메뉴 ${셈('공청회')} · 공론장 ${셈('공론장')} · 별도 ${셈('별도')} · 예산안 글 ${셈('예산안')}`);
  크롬.kill();
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
