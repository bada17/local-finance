// find_boards.js 가 찾은 게시판에 들어가 **글 목록**(제목·날짜·주소)과 붙은 파일을 적는다.
//
//   node scripts/fetch_boards.js                     243곳 × 과녁 여섯
//   node scripts/fetch_boards.js 고향사랑            그 과녁만
//   node scripts/fetch_boards.js 고향사랑 1111000    그 과녁·그 곳만(시험용, 파일에 안 적는다)
//   node scripts/fetch_boards.js --의회              의회 누리집 판 → board_posts_council.json
//
// 판정 — 후보 링크를 차례로 열어, 날짜가 붙은 줄이 셋 이상이면 「게시판」으로 보고 첫 쪽 글을 적는다.
//   게시판이 아니면(안내 화면) 그 화면에 붙은 파일만 적는다. 후보 셋까지 보고 게시판을 찾으면 멈춘다.
// ⭐ 쪽을 넘겨 2022-01-01 글까지 받는다(사용자 2026-10-08). 고시·공고는 「공청회」로 검색한 결과만.
// ⚠️ 글 안의 파일·표는 아직 안 연다(3단계). 여기서는 「어디에 무엇이 있나」까지만.
//
// ⭐ 끊겨도 된다 — 하나마다 적고, 다시 부르면 남은 것만 한다. 처음부터는 --다시
// 결과: data/board_posts.json  (과녁별로 합쳐 적는다 — 한 과녁만 돌려도 다른 과녁은 남는다)

const fs = require('fs');
const path = require('path');
const os = require('os');
const { 크롬자리, 크롬띄우기, 붙을때까지, 탭열기, PORT, 긁개, 기다림 } = require('./recheck_disclosure.js');

const ROOT = path.dirname(__dirname);
// --의회 : find_boards.js --의회 가 찾은 의회 누리집 게시판
const 의회판 = process.argv.includes('--의회');
const IN = path.join(ROOT, 'data', 의회판 ? 'boards_council.json' : 'boards.json');
const OUT = path.join(ROOT, 'data', 의회판 ? 'board_posts_council.json' : 'board_posts.json');
const 과녁차례 = 의회판 ? ['업무추진비', '국외출장']
  : ['고향사랑', '업무추진비', '수의계약', '감사결과', '투자심사', '공약', '고시공고', '공청회', '일일집행', '공론장'];
const 한번에 = 12;
const 후보끝 = 3;

const 목록긁개 = String.raw`(() => {
  const 날 = /(20\d{2})\s*[-.\/년]\s*(\d{1,2})\s*[-.\/월]\s*(\d{1,2})/;
  const 링크들 = [...document.querySelectorAll('a')];
  const 줄들 = [...document.querySelectorAll('tr, li')].filter(r => {
    const t = r.innerText || '';
    return t.length < 400 && 날.test(t) && r.querySelector('a') && !r.querySelector('tr, li');
  });
  const 글 = [], 본 = new Set();
  for (const r of 줄들) {
    const a = [...r.querySelectorAll('a')].sort((x, y) => (y.textContent || '').trim().length - (x.textContent || '').trim().length)[0];
    const 제목 = (a.textContent || a.title || '').replace(/\s+/g, ' ').trim();
    if (제목.length < 4) continue;
    const m = (r.innerText || '').match(날);
    const 날짜 = m ? m[1] + '-' + m[2].padStart(2, '0') + '-' + m[3].padStart(2, '0') : '';
    if (본.has(제목 + 날짜)) continue;
    본.add(제목 + 날짜);
    const raw = (a.getAttribute('href') || '').trim();
    const 누름 = !raw || raw.startsWith('#') || /^javascript:/i.test(raw);
    글.push({ 제목: 제목.slice(0, 120), 날짜, 주소: 누름 ? '' : a.href.slice(0, 300), 번째: 누름 ? 링크들.indexOf(a) : -1 });
  }
  return JSON.stringify({ 화면: (document.title || '').replace(/\s+/g, ' ').trim().slice(0, 80), 주소: location.href.slice(0, 300), 글 });
})()`;

// 화면이 다 실릴 때까지 기다린다(이동한 뒤·누른 뒤 같이 쓴다)
async function 기다리기(보내기, 먼저 = 0) {
  if (먼저) await new Promise(x => setTimeout(x, 먼저));
  const 끝날때 = Date.now() + 기다림;
  while (Date.now() < 끝날때) {
    const r = await 보내기('Runtime.evaluate', {
      expression: 'location.href.slice(0,8) + "|" + document.readyState + "|" + (document.body ? document.body.innerText.length : 0)',
      returnByValue: true,
    });
    const [주소, 상태글, 길이] = String((r.result && r.result.value) || '').split('|');
    if (주소.startsWith('http') && Number(길이) > 120 && (상태글 === 'complete' || Date.now() > 끝날때 - 기다림 + 6000)) break;
    await new Promise(x => setTimeout(x, 400));
  }
  await new Promise(x => setTimeout(x, 1200));
}
async function 긁기(보내기, 식) {
  const r = await 보내기('Runtime.evaluate', { expression: 식, returnByValue: true, timeout: 8000 });
  return r.result && r.result.value ? JSON.parse(r.result.value) : null;
}
async function 열고긁기(탭, url, 식) {
  await 탭.보내기('Page.navigate', { url });
  await 기다리기(탭.보내기);
  return 긁기(탭.보내기, 식);
}

// ⭐ 2022년 글까지만 받는다(사용자 2026-10-08 — CLIK 범위와 같게). 그보다 옛 글이 나오면 쪽 넘기기를 멈춘다.
const 시작날 = '2022-01-01';
const 쪽끝 = 150;
// 다음 쪽 링크 — 쪽 번호(n)를 쪽 묶음 안에서 먼저 찾고, 없으면 「다음」 단추
const 다음쪽식 = n => String.raw`(() => {
  const as = [...document.querySelectorAll('a')];
  const 글 = a => (a.textContent || '').replace(/\s+/g, '').trim();
  const 쪽칸 = a => !!a.closest('[class*=pag],[id*=pag],[class*=Pag],[class*=page],nav');
  let i = as.findIndex(a => 글(a) === '${n}' && 쪽칸(a));
  if (i < 0) i = as.findIndex(a => 쪽칸(a) && /^(다음|다음페이지|next|›|>)$/i.test(글(a) || (a.title || '').replace(/\s+/g, '')));
  return String(i);
})()`;
// 고시·공고는 글이 하루 수십 개라 다 넘길 수 없다 — 게시판 안 검색칸에 「공청회」를 넣고 그 결과만 넘긴다
const 검색식 = 낱말 => String.raw`(() => {
  const 칸 = [...document.querySelectorAll('input[type=text],input[type=search],input:not([type])')]
    .find(x => /search|keyword|srch|sch|query|word|kwd|stx/i.test((x.name || '') + (x.id || '') + (x.className || '')));
  if (!칸) return 'false';
  칸.value = '${낱말}';
  const f = 칸.form;
  if (f) { if (f.requestSubmit) f.requestSubmit(); else f.submit(); return 'true'; }
  const b = 칸.parentElement && 칸.parentElement.querySelector('button,input[type=submit],a');
  if (b) { b.click(); return 'true'; }
  return 'false';
})()`;

async function 지난쪽까지(탭, 첫목록) {
  const { 보내기 } = 탭;
  const 글 = 첫목록.글.map(x => ({ ...x, 쪽: 1 }));
  const 본 = new Set(글.map(x => x.제목 + x.날짜));
  let 쪽 = 1, 멈춘까닭 = '';
  while (쪽 < 쪽끝) {
    const 가장옛 = 글.map(x => x.날짜).filter(Boolean).sort()[0];
    if (가장옛 && 가장옛 < 시작날) { 멈춘까닭 = `${시작날} 앞 글에 닿음`; break; }
    const i = Number(JSON.parse(JSON.stringify((await 보내기('Runtime.evaluate', { expression: 다음쪽식(쪽 + 1), returnByValue: true })).result?.value ?? '-1')));
    if (!(i >= 0)) { 멈춘까닭 = '다음 쪽이 없다'; break; }
    await 보내기('Runtime.evaluate', { expression: `document.querySelectorAll('a')[${i}].click()` });
    await 기다리기(보내기, 2000);
    const 새 = await 긁기(보내기, 목록긁개);
    const 새글 = ((새 && 새.글) || []).filter(x => !본.has(x.제목 + x.날짜));
    if (!새글.length) { 멈춘까닭 = '넘겨도 새 글이 없다'; break; }
    쪽++;
    for (const x of 새글) { 본.add(x.제목 + x.날짜); 글.push({ ...x, 쪽, 번째: 쪽 === 1 ? x.번째 : -1 }); }
  }
  if (!멈춘까닭) 멈춘까닭 = `${쪽끝}쪽 한도`;
  return { 글: 글.filter(x => !x.날짜 || x.날짜 >= 시작날), 본쪽: 쪽, 멈춘까닭 };
}

async function 한과녁(탭, 후보들, 과녁) {
  let 안내 = null;
  for (const 후보 of 후보들.slice(0, 후보끝)) {
    if (!/^https?:/.test(후보.주소) || /#$/.test(후보.주소)) continue;
    let 목록 = await 열고긁기(탭, 후보.주소, 목록긁개);
    if (목록 && 목록.글.length >= 3) {
      let 검색어 = '';
      if (과녁 === '고시공고') {
        const 됨 = (await 탭.보내기('Runtime.evaluate', { expression: 검색식('공청회'), returnByValue: true })).result?.value === 'true';
        if (!됨) return { 종류: '게시판', 링크글자: 후보.글자, 화면: 목록.화면, 주소: 목록.주소, 글: [], 까닭: '검색칸을 못 찾아 공청회 글을 못 골랐다' };
        await 기다리기(탭.보내기, 2000);
        목록 = (await 긁기(탭.보내기, 목록긁개)) || { 글: [] };
        검색어 = '공청회';
      }
      const 넘김 = await 지난쪽까지(탭, 목록);
      return { 종류: '게시판', 링크글자: 후보.글자, 화면: 목록.화면, 주소: 목록.주소, 검색어, ...넘김 };
    }
    if (!안내) {
      const 화면 = await 열고긁기(탭, 후보.주소, 긁개);
      if (화면) 안내 = { 종류: '안내 화면', 링크글자: 후보.글자, 화면: 화면.제목, 주소: 화면.주소, 파일: 화면.파일, 날짜: 화면.날짜 };
    }
  }
  return 안내 || { 종류: '못 열었다' };
}

async function main() {
  if (!크롬자리) throw new Error('크롬을 못 찾겠다');
  const 곳들 = JSON.parse(fs.readFileSync(IN, 'utf-8'))['곳'];
  const 인자 = process.argv.slice(2);
  const 과녁들 = 인자.filter(a => !/^\d{7}$/.test(a) && !a.startsWith('--'));
  const 한곳만 = 인자.filter(a => /^\d{7}$/.test(a));
  const 할일 = [];
  for (const [laf, v] of Object.entries(곳들)) {
    if (한곳만.length && !한곳만.includes(laf)) continue;
    for (const k of 과녁차례) {
      if (과녁들.length && !과녁들.includes(k)) continue;
      if ((v[k] || []).length) 할일.push({ laf, 이름: v.이름, 과녁: k, 후보: v[k] });
    }
  }
  // 이어 하기 — 하나 끝날 때마다 적고, 다시 돌리면 적힌 것은 건너뛴다. 처음부터는 --다시
  const 시험 = 한곳만.length > 0;
  const 결과 = !시험 && !process.argv.includes('--다시') && fs.existsSync(OUT) ? JSON.parse(fs.readFileSync(OUT, 'utf-8'))['곳'] : {};
  const 적기 = () => fs.writeFileSync(OUT, JSON.stringify({ 만든날: new Date().toISOString().slice(0, 10), 곳: 결과 }, null, 1));
  const 남은 = 할일.filter(일 => { const x = (결과[일.laf] || {})[일.과녁]; return !x || x.종류 === '멈췄다'; });
  console.log(`할 일 ${할일.length}, 남은 것 ${남은.length}`);
  할일.splice(0, 할일.length, ...남은);

  const 프로필 = fs.mkdtempSync(path.join(os.tmpdir(), 'lf-posts-'));
  const 크롬 = 크롬띄우기(프로필);
  await 붙을때까지();
  let 다음 = 0, 끝난 = 0;
  const 일꾼 = async () => {
    const 탭 = await 탭열기();
    while (다음 < 할일.length) {
      const 일 = 할일[다음++];
      let 값;
      try { 값 = await 한과녁(탭, 일.후보, 일.과녁); } catch (e) { 값 = { 종류: '멈췄다', 까닭: String(e).slice(0, 60) }; }
      (결과[일.laf] = 결과[일.laf] || { 이름: 일.이름 })[일.과녁] = 값;
      if (!시험) 적기();
      if (++끝난 % 20 === 0) console.log(`   ${끝난}/${할일.length}`);
    }
    탭.ws.close();
    await fetch(`http://127.0.0.1:${PORT}/json/close/${탭.tab.id}`).catch(() => {});
  };
  await Promise.all(Array.from({ length: Math.min(한번에, 할일.length) }, 일꾼));
  크롬.kill();

  const 셈 = {};
  for (const v of Object.values(결과)) for (const [k, x] of Object.entries(v)) {
    if (k === '이름') continue;
    셈[k] = 셈[k] || {};
    셈[k][x.종류] = (셈[k][x.종류] || 0) + 1;
  }
  console.log(JSON.stringify(셈));
  if (시험) console.log(JSON.stringify(결과, null, 1));
  else { 적기(); console.log('적음: data/board_posts.json'); }
  await new Promise(r => setTimeout(r, 1500));
  try { fs.rmSync(프로필, { recursive: true, force: true }); } catch (_) { /* 임시 폴더다 */ }
}

main().catch(e => { console.error('FAIL', e); process.exit(1); });
