// 누리집에만 올라오는 공개 자료의 **게시판 자리**를 찾는다 — 243곳.
//
//   node scripts/find_boards.js                  243곳 전부 (탭 넷)
//   node scripts/find_boards.js 4513000 1132000  그 곳만(시험용, 파일에 안 적는다)
//   node scripts/find_boards.js --다시            적힌 것을 버리고 처음부터
//   node scripts/find_boards.js --의회            의회 누리집 판(boards.json 을 먼저 만들어야 한다) → boards_council.json
// ⭐ 끊겨도 된다 — 한 곳마다 적고, 다시 부르면 남은 곳만 한다.
//
// 왜 — 고향사랑기부 접수·사용 내역, 업무추진비 집행 내역 같은 것은 API 에 없고
//      자치단체 누리집 게시판에만 있다(2026-10-08). 긁기 전에 「어디 있나」부터 안다.
//
// 찾는 법 — count_clicks.js 와 같다. 첫 화면을 크롬으로 열고, 사이트맵·정보공개·재정 같은 링크를
//   넓이 우선으로 두 번까지 따라가며 **만나는 링크마다** 아래 과녁 여섯과 견준다.
//   과녁마다 후보를 몇 개씩 남긴다(어느 것이 진짜 게시판인지는 2단계에서 가린다).
// ⚠️ 못 찾은 곳은 「못 찾음」이다. 「공개 안 함」으로 읽지 말 것.
// ⚠️ 크롬 포트를 recheck_disclosure.js·count_clicks.js 와 같이 쓴다 — 한꺼번에 돌리지 말 것.
//
// 결과: data/boards.json

const fs = require('fs');
const path = require('path');
const os = require('os');
const { 크롬자리, 크롬띄우기, 붙을때까지, 탭열기, PORT } = require('./recheck_disclosure.js');
const { 첫화면, 뿌리, 열기 } = require('./count_clicks.js');

const ROOT = path.dirname(__dirname);
// --의회 : 자치단체 누리집에서 찾은 의회 누리집으로 가서 의원 업무추진비·국외출장을 찾는다
const 의회판 = process.argv.includes('--의회');
const OUT = path.join(ROOT, 'data', 의회판 ? 'boards_council.json' : 'boards.json');
const 한번에 = 4;
const 깊이끝 = 2;
const 층마다 = 10;
const 후보수 = 5;

const 과녁 = 의회판 ? {
  업무추진비: /업무\s*추진\s*비/,
  국외출장: /국외\s*(출장|연수|활동|여비)|공무\s*국외|해외\s*(연수|출장)/,
} : {
  고향사랑: /고향\s*사랑/,
  업무추진비: /업무\s*추진\s*비/,
  수의계약: /수의\s*계약/,
  감사결과: /감사\s*결과|자체\s*감사/,
  투자심사: /투자\s*심사/,
  공약: /공약/,
  // 투명성 평가안의 빈칸 셋(공청회·일일 집행·공론장) — 2026-10-08 「쓸 수도 있으니까」
  고시공고: /고시\s*[·ㆍ.\/]?\s*공고|공고\s*[·ㆍ.\/]?\s*고시/,
  공청회: /공청회|주민\s*설명회/,
  일일집행: /일일\s*(재정|예산|집행)|재정\s*집행\s*(현황|상황|공개)|예산\s*집행\s*(현황|상황|공개)|실시간\s*재정/,
  공론장: /공론|숙의|원탁\s*회의|시민\s*토론/,
  // 의회 누리집으로 가는 링크 — --의회 판의 출발점. 다른 누리집(주소)인 것만 담는다
  의회: /의회/,
};
// 과녁 안에서도 「공개·현황·내역」이 붙은 링크를 앞에 세운다 — 기부 안내 화면보다 공개 게시판이 먼저다
const 알맹이 = /공개|현황|내역|결과|운용|집행|공시|이행|실적|보고/;
const 따라갈 = 의회판
  ? /사이트\s*맵|전체\s*메뉴|정보\s*공개|의정|의원|공개|자료|열린/
  : /사이트\s*맵|전체\s*메뉴|정보\s*공개|사전\s*공표|재정|예산|계약|감사|고향\s*사랑|공약|열린|행정\s*정보|분야별|고시|공고|참여|소통/;
const 차례 = t => /사이트\s*맵|전체\s*메뉴/.test(t) ? 0 : /정보\s*공개|사전\s*공표/.test(t) ? 1 : /재정|예산|의정/.test(t) ? 2 : 3;

async function 한곳(탭, 곳) {
  // 의회 누리집은 주소를 그대로 쓴다 — 첫화면() 은 council.○○.go.kr 을 www.○○.go.kr 로 바꿔 버린다
  const 첫 = 의회판 ? new URL(곳.주소).origin + '/' : 첫화면(곳.주소);
  const 집 = 뿌리(new URL(첫).hostname);
  const 첫호스트 = new URL(첫).hostname;
  const 본것 = new Set([첫]);
  const 찾음 = Object.fromEntries(Object.keys(과녁).map(k => [k, []]));
  const 담기 = (t, h, 길) => {
    for (const [k, re] of Object.entries(과녁)) {
      if (!re.test(t) || 찾음[k].some(x => x.주소 === h)) continue;
      if (k === '의회') { try { if (new URL(h).hostname === 첫호스트) continue; } catch (_) { continue; } }
      찾음[k].push({ 글자: t, 주소: h.slice(0, 300), 길: [...길, t] });
    }
  };
  let 층 = [{ url: 첫, 길: [] }];
  let 연곳 = 0;
  for (let 깊이 = 0; 깊이 <= 깊이끝 && 층.length; 깊이++) {
    const 다음 = [];
    for (const { url, 길 } of 층) {
      const 링크 = await 열기(탭, url);
      if (링크.length) 연곳++;
      if (깊이 === 0 && !링크.length) return { 첫화면: 첫, 까닭: '첫 화면이 안 열린다' };
      const 관문 = 깊이 === 0 && 링크.length < 30;
      for (const [t, h] of 링크) {
        if (!/^https?:/.test(h)) continue;
        담기(t, h, 길);
        if (본것.has(h) || !(관문 || 따라갈.test(t))) continue;
        try { if (뿌리(new URL(h).hostname) !== 집) continue; } catch (_) { continue; }
        본것.add(h);
        다음.push({ url: h, 길: [...길, t] });
      }
    }
    if (깊이 === 깊이끝) break;
    층 = 다음.sort((a, b) => 차례(a.길[a.길.length - 1]) - 차례(b.길[b.길.length - 1])).slice(0, 층마다);
  }
  for (const k of Object.keys(찾음)) {
    찾음[k] = 찾음[k].sort((a, b) => 알맹이.test(b.글자) - 알맹이.test(a.글자) || a.길.length - b.길.length).slice(0, 후보수);
  }
  return { 첫화면: 첫, 연화면: 연곳, ...찾음 };
}

async function main() {
  if (!크롬자리) throw new Error('크롬을 못 찾겠다');
  const dis = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'disclosure.json'), 'utf-8'))['곳'];
  const p = path.join(ROOT, 'data', 'disclosure_found.json');
  const 손 = fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf-8'))['곳'] : {};
  let 곳들 = dis.filter(r => r.주소).map(r => ({ ...r, 주소: (손[r.laf_cd] || {}).주소 || r.주소 }));
  if (의회판) {
    // 출발점 = 자치단체 판(boards.json)이 찾은 의회 링크. council 이 주소에 든 것을 먼저 고른다
    const 판 = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'boards.json'), 'utf-8'))['곳'];
    곳들 = 곳들.map(r => {
      const 후보 = ((판[r.laf_cd] || {}).의회 || []).filter(x => /^https?:/.test(x.주소));
      const 고른 = 후보.find(x => /council|assembly|의회/i.test(x.주소)) || 후보[0];
      return 고른 ? { ...r, 주소: 고른.주소 } : null;
    }).filter(Boolean);
  }
  const 한곳만 = process.argv.slice(2).filter(a => /^\d{7}$/.test(a));
  if (한곳만.length) 곳들 = 곳들.filter(r => 한곳만.includes(r.laf_cd));
  // 이어 하기 — 한 곳 끝날 때마다 적고, 다시 돌리면 적힌 곳은 건너뛴다. 처음부터는 --다시
  const 다시 = process.argv.includes('--다시');
  const 결과 = !한곳만.length && !다시 && fs.existsSync(OUT) ? JSON.parse(fs.readFileSync(OUT, 'utf-8'))['곳'] : {};
  const 적기 = () => fs.writeFileSync(OUT, JSON.stringify({ 만든날: new Date().toISOString().slice(0, 10), 곳: 결과 }, null, 1));
  곳들 = 곳들.filter(r => !결과[r.laf_cd] || 결과[r.laf_cd].까닭);
  console.log(`남은 곳 ${곳들.length}`);

  const 프로필 = fs.mkdtempSync(path.join(os.tmpdir(), 'lf-boards-'));
  const 크롬 = 크롬띄우기(프로필);
  await 붙을때까지();
  let 다음 = 0, 끝난 = 0;
  const 일꾼 = async () => {
    const 탭 = await 탭열기();
    while (다음 < 곳들.length) {
      const 곳 = 곳들[다음++];
      try { 결과[곳.laf_cd] = { 이름: 곳.이름, ...(await 한곳(탭, 곳)) }; }
      catch (e) { 결과[곳.laf_cd] = { 이름: 곳.이름, 까닭: '찾다가 멈췄다 — ' + String(e).slice(0, 60) }; }
      if (!한곳만.length) 적기();
      if (++끝난 % 10 === 0) console.log(`   ${끝난}/${곳들.length}`);
    }
    탭.ws.close();
    await fetch(`http://127.0.0.1:${PORT}/json/close/${탭.tab.id}`).catch(() => {});
  };
  await Promise.all(Array.from({ length: Math.min(한번에, 곳들.length) }, 일꾼));
  크롬.kill();

  const 셈 = Object.fromEntries(Object.keys(과녁).map(k => [k, Object.values(결과).filter(v => (v[k] || []).length).length]));
  console.log(`찾은 곳 수 ${JSON.stringify(셈)} / ${곳들.length}`);
  if (한곳만.length) console.log(JSON.stringify(결과, null, 1));
  else { 적기(); console.log('적음: data/boards.json'); }
  await new Promise(r => setTimeout(r, 1500));
  try { fs.rmSync(프로필, { recursive: true, force: true }); } catch (_) { /* 임시 폴더다 */ }
}

main().catch(e => { console.error('FAIL', e); process.exit(1); });
