// 「몇 번 눌러야 닿나」를 잰다 — 자치단체 첫 화면에서 재정공시까지.
//
//   node scripts/count_clicks.js                  243곳 전부 (탭 넷, 20분쯤)
//   node scripts/count_clicks.js 4513000 1132000  그 곳만(시험용, 파일에 안 적는다)
//
// 왜 — 공시 점검은 지방재정365가 준 **직통 주소**로 잰다. 시민은 그 주소를 모른다.
//      첫 화면에서 메뉴를 따라가야 한다. 몇 번 눌러야 닿는지가 투명성 지표 ② 켜의 남은 칸이다.
//
// 재는 법 — 누리집 첫 화면(주소의 앞머리, 하위 도메인이면 www.)을 **크롬으로** 열고,
//   「재정공시」라고 적힌 링크가 보이면 거기까지 누른 수가 답이다. 없으면 재정·예산·정보공개 같은
//   글자가 붙은 **같은 누리집** 링크를 따라 넓이 우선으로 세 번까지 들어간다.
// ⚠️ 첫 화면의 큰 메뉴(메가메뉴)에 숨어 있어도 1번으로 센다 — 마우스를 올리면 보이기 때문이다.
// ⚠️ 세 번 안에 못 찾은 곳은 「못 찾음」이다. 「멀다」로 읽지 말 것 — 우리 따라가기 규칙이 못 닿은 것일 수 있다.
// ⚠️ 크롬 띄우기는 recheck_disclosure.js 것을 빌려 쓴다(같은 포트다 — 둘을 한꺼번에 돌리지 말 것).
//
// 결과: data/disclosure_clicks.json

const fs = require('fs');
const path = require('path');
const os = require('os');
const { 크롬자리, 크롬띄우기, 붙을때까지, 탭열기, PORT } = require('./recheck_disclosure.js');

const ROOT = path.dirname(__dirname);
const OUT = path.join(ROOT, 'data', 'disclosure_clicks.json');
const 한번에 = 4;
const 깊이끝 = 3;
const 층마다 = 12;        // 한 층에서 따라갈 링크 수
const 기다림 = 14000;

const 과녁 = /재정\s*(운용|운영)?\s*(상황)?\s*공시/;
const 따라갈 = /재정|예산|정보\s*공개|행정\s*정보|분야별|열린|시정|구정|군정|도정|사이트\s*맵|전체\s*메뉴|누리집|홈페이지/;
// 따라갈 차례 — 한 층에 링크가 수천 개인 곳(대구 2,034개)은 「정보공개」 류에 한도가 먼저 차서
// 「재정」 메뉴까지 못 갔다(2026-09-29). 재정 → 예산 → 나머지 차례로 고른다.
const 차례 = t => /재정/.test(t) ? 0 : /예산/.test(t) ? 1 : /사이트\s*맵|전체\s*메뉴/.test(t) ? 2 : 3;

// 페이지 안에서 링크를 다 줍는다 — 숨은 메뉴까지
const 줍개 = String.raw`JSON.stringify([...document.querySelectorAll('a')].map(a =>
  [(a.textContent || a.title || '').replace(/\s+/g, ' ').trim().slice(0, 40), a.href || '']).filter(x => x[0]))`;

// www.xxx.go.kr 의 「xxx.go.kr」 — 같은 누리집인지 볼 때 쓴다
const 뿌리 = host => host.split('.').slice(-3).join('.');

function 첫화면(주소) {
  const u = new URL(주소);
  const 뿌리이름 = 뿌리(u.hostname);
  return `${u.protocol}//${u.hostname === 뿌리이름 || u.hostname.startsWith('www.') ? u.hostname : 'www.' + 뿌리이름}/`;
}

async function 열기(탭, url) {
  const { 보내기 } = 탭;
  await 보내기('Page.navigate', { url });
  const 끝날때 = Date.now() + 기다림;
  while (Date.now() < 끝날때) {
    const r = await 보내기('Runtime.evaluate', {
      expression: 'location.href.slice(0,8) + "|" + document.readyState + "|" + (document.body ? document.body.innerText.length : 0)',
      returnByValue: true,
    });
    const [주소, 상태글, 길이] = String((r.result && r.result.value) || '').split('|');
    if (주소.startsWith('http') && Number(길이) > 50 && (상태글 === 'complete' || Date.now() > 끝날때 - 기다림 + 6000)) break;
    await new Promise(x => setTimeout(x, 400));
  }
  await new Promise(x => setTimeout(x, 1200));     // 메뉴를 JS 로 그리는 곳을 더 기다린다
  const r = await 보내기('Runtime.evaluate', { expression: 줍개, returnByValue: true, timeout: 8000 });
  return r.result && r.result.value ? JSON.parse(r.result.value) : [];
}

async function 한곳(탭, 곳) {
  const 첫 = 첫화면(곳.주소);
  const 집 = 뿌리(new URL(첫).hostname);
  const 본것 = new Set([첫]);
  let 층 = [{ url: 첫, 길: [] }];
  for (let 깊이 = 0; 깊이 < 깊이끝 && 층.length; 깊이++) {
    const 다음 = [];
    for (const { url, 길 } of 층) {
      const 링크 = await 열기(탭, url);
      if (깊이 === 0 && !링크.length) return { 첫화면: 첫, 번: null, 까닭: '첫 화면이 안 열린다' };
      const 맞음 = 링크.find(([t]) => 과녁.test(t));
      if (맞음) return { 첫화면: 첫, 번: 깊이 + 1, 길: [...길, 맞음[0]], 닿은곳: 맞음[1].slice(0, 200) };
      // 첫 화면이 관문(링크 몇 개짜리 소개 화면)이면 글자를 안 가리고 같은 누리집 링크를 다 따라간다 — 안동시
      const 관문 = 깊이 === 0 && 링크.length < 30;
      for (const [t, h] of 링크) {
        if (!/^https?:/.test(h) || 본것.has(h) || !(관문 || 따라갈.test(t))) continue;
        try { if (뿌리(new URL(h).hostname) !== 집) continue; } catch (_) { continue; }
        본것.add(h);
        다음.push({ url: h, 길: [...길, t] });
      }
    }
    층 = 다음.sort((a, b) => 차례(a.길[a.길.length - 1]) - 차례(b.길[b.길.length - 1])).slice(0, 층마다);
  }
  return { 첫화면: 첫, 번: null, 까닭: `${깊이끝}번 안에 「재정공시」 링크를 못 찾았다` };
}

async function main() {
  if (!크롬자리) throw new Error('크롬을 못 찾겠다');
  const dis = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'disclosure.json'), 'utf-8'))['곳'];
  const p = path.join(ROOT, 'data', 'disclosure_found.json');
  const 찾은 = fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf-8'))['곳'] : {};
  // 구역이 바뀌어 누리집이 옮겨 간 곳(인천 동구 → 제물포구)은 손으로 찾은 주소의 누리집에서 잰다
  let 곳들 = dis.filter(r => r.주소).map(r => ({ ...r, 주소: (찾은[r.laf_cd] || {}).주소 || r.주소 }));
  const 한곳만 = process.argv.slice(2).filter(a => /^\d{7}$/.test(a));
  if (한곳만.length) 곳들 = 곳들.filter(r => 한곳만.includes(r.laf_cd));

  const 프로필 = fs.mkdtempSync(path.join(os.tmpdir(), 'lf-clicks-'));
  const 크롬 = 크롬띄우기(프로필);
  await 붙을때까지();
  const 결과 = {};
  let 다음 = 0, 끝난 = 0;
  const 일꾼 = async () => {
    const 탭 = await 탭열기();
    while (다음 < 곳들.length) {
      const 곳 = 곳들[다음++];
      try { 결과[곳.laf_cd] = await 한곳(탭, 곳); }
      catch (e) { 결과[곳.laf_cd] = { 번: null, 까닭: '재다가 멈췄다 — ' + String(e).slice(0, 60) }; }
      if (++끝난 % 10 === 0) console.log(`   ${끝난}/${곳들.length}`);
    }
    탭.ws.close();
    await fetch(`http://127.0.0.1:${PORT}/json/close/${탭.tab.id}`).catch(() => {});
  };
  await Promise.all(Array.from({ length: Math.min(한번에, 곳들.length) }, 일꾼));
  크롬.kill();

  if (한곳만.length) {
    console.log(JSON.stringify(결과, null, 1));
  } else {
    const 셈 = {};
    for (const v of Object.values(결과)) 셈[v.번 || '못 찾음'] = (셈[v.번 || '못 찾음'] || 0) + 1;
    console.log(`누른 수별 ${JSON.stringify(셈)}`);
    fs.writeFileSync(OUT, JSON.stringify({ 만든날: new Date().toISOString().slice(0, 10), 곳: 결과 }, null, 1));
    console.log('적음: data/disclosure_clicks.json');
  }
  await new Promise(r => setTimeout(r, 1500));
  try { fs.rmSync(프로필, { recursive: true, force: true }); } catch (_) { /* 임시 폴더다 */ }
}

main().catch(e => { console.error('FAIL', e); process.exit(1); });
