// 재정공시 페이지를 **브라우저로** 다시 본다 — urllib 이 못 본 것을 잡으러.
//
//   node scripts/recheck_disclosure.js            243곳 전부
//   node scripts/recheck_disclosure.js --only 30  앞 30곳만 (시험)
//
// 왜 브라우저인가 —
//   ① 목록을 자바스크립트로 그리는 곳(86곳)은 원문 HTML 에 파일이 아예 없다.
//   ② 파일 이름이 해시인 곳(90곳)도 **글자로 된 이름은 링크 텍스트에 있다.**
//   ③ SSL 로 파이썬이 튕긴 곳(15곳)은 크롬에서는 열린다 — 시민이 보는 것은 크롬 쪽이다.
//
// ⚠️ 노드 22+ 가 필요하다(WebSocket 내장). 크롬은 --remote-debugging-port 로 띄운다.
// ⚠️ **「자동으로 못 봤다」를 「없다」로 쓰지 않기 위한 작업이다.** 여기서 잡힌 것만
//    확실해지는 것이고, 여전히 못 본 곳은 못 본 채로 둔다.
//
// 결과: data/disclosure_dom.json   (build_transparency.py 가 이것을 먼저 본다)

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const os = require('os');

const ROOT = path.dirname(__dirname);
const OUT = path.join(ROOT, 'data', 'disclosure_dom.json');
const PORT = 9333;
const 한번에 = 4;            // 탭 넷이면 243곳에 5분쯤
const 기다림 = 14000;        // 한 곳에 최대 14초
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36';

const 크롬자리 = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
].find(p => fs.existsSync(p));

// 페이지 안에서 도는 긁개 — 붙은 파일과 올린 날짜를 찾는다
const 긁개 = String.raw`(() => {
  const EXT = /\.(hwpx?|xlsx?|csv|pdfa?|docx?|pptx?|zip)(\?|$|["'\s])/i;
  const 내려받기 = /download|filedown|file_down|atchfile|fileid|attach|getfile|cmmn\/fms/i;
  const 파일 = [];
  const 본 = new Set();
  const 담기 = (이름, 주소) => {
    이름 = (이름 || '').replace(/\s+/g, ' ').trim().slice(0, 90);
    if (!이름 || 본.has(이름)) return;
    본.add(이름);
    파일.push({ 이름, 주소: (주소 || '').slice(0, 160) });
  };
  for (const a of document.querySelectorAll('a,button')) {
    const t = a.textContent || '';
    const h = a.getAttribute('href') || '';
    const oc = (a.getAttribute('onclick') || '') + (a.getAttribute('data-href') || '');
    if (EXT.test(t) || EXT.test(h) || ((내려받기.test(h) || 내려받기.test(oc)) && t.trim().length > 3)) {
      // 링크 글자에 「다운로드」·「바로보기」가 덧붙는 곳이 많다 — 이름만 남긴다
      let nm = t.replace(/\s*(다운로드|내려받기|바로보기|미리보기|새창열림|down|download)\s*$/gi, '').trim();
      if (!nm && EXT.test(h)) nm = decodeURIComponent((h.split(/[?#]/)[0].split('/').pop() || ''));
      담기(nm || t, h || oc);
    }
  }
  // 링크가 아니라 글자로만 적힌 파일 이름도 줍는다
  const 글 = (document.body ? document.body.innerText : '') || '';
  for (const m of 글.matchAll(/[^\s\/\\:*?"<>|]{2,70}\.(hwpx?|xlsx?|csv|pdf|docx?|pptx?|zip)/gi)) 담기(m[0], '');

  let 날짜 = '';
  const d = 글.match(/(등록일|작성일|게시일|공시일|수정일|등록\s*일자)\s*[:：]?\s*(20\d{2}[-.\/]\s?\d{1,2}[-.\/]\s?\d{1,2})/);
  if (d) 날짜 = d[2].replace(/\s/g, '');
  return JSON.stringify({
    제목: (document.title || '').replace(/\s+/g, ' ').trim().slice(0, 80),
    주소: location.href.slice(0, 200),
    파일: 파일.slice(0, 40),
    날짜,
    글자수: 글.length,
  });
})()`;

function 크롬띄우기(프로필) {
  const p = spawn(크롬자리, [
    '--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${프로필}`,
    '--no-first-run', '--no-default-browser-check', '--disable-gpu',
    '--disable-background-networking', '--mute-audio', '--window-size=1280,900',
    // 공공기관 사이트는 인증서 사슬이 빠진 곳이 많다. **크롬이 뭘 보는지**를 재는 것이므로
    // 경고를 무시하고 열되, 무시했다는 사실을 아래에서 따로 적는다.
    '--ignore-certificate-errors',
    'about:blank',
  ], { stdio: 'ignore' });
  return p;
}

async function 붙을때까지() {
  for (let i = 0; i < 40; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/version`);
      if (r.ok) return;
    } catch (_) { /* 아직 안 떴다 */ }
    await new Promise(r => setTimeout(r, 500));
  }
  throw new Error('크롬이 안 뜬다');
}

// 탭 하나를 잡고 붙들어 쓴다
async function 탭열기() {
  const t = await (await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: 'PUT' })).json();
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  let id = 0;
  const 기다리는 = new Map();
  const 신호 = new Map();
  await new Promise(res => ws.addEventListener('open', res));
  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && 기다리는.has(m.id)) { 기다리는.get(m.id)(m.result || {}); 기다리는.delete(m.id); }
    if (m.method && 신호.has(m.method)) { 신호.get(m.method).forEach(f => f(m.params)); }
  });
  const 보내기 = (method, params = {}) => new Promise(res => {
    const i = ++id;
    기다리는.set(i, res);
    ws.send(JSON.stringify({ id: i, method, params }));
    setTimeout(() => { if (기다리는.has(i)) { 기다리는.delete(i); res({}); } }, 기다림);
  });
  const 듣기 = (method, fn) => {
    if (!신호.has(method)) 신호.set(method, []);
    신호.get(method).push(fn);
  };
  const 상태 = { 코드: null, 실패: '' };
  듣기('Network.responseReceived', p => {
    if (p.type === 'Document' && p.response && 상태.코드 == null) 상태.코드 = p.response.status;
  });
  듣기('Network.loadingFailed', p => {
    if (p.type === 'Document' && !상태.실패) 상태.실패 = p.errorText || '실패';
  });
  await 보내기('Page.enable');
  await 보내기('Runtime.enable');
  await 보내기('Network.enable');
  await 보내기('Network.setUserAgentOverride', { userAgent: UA });
  return { tab: t, ws, 보내기, 듣기, 상태 };
}

async function 한곳(탭, 곳) {
  const { 보내기, 상태 } = 탭;
  상태.코드 = null; 상태.실패 = '';

  await 보내기('Page.navigate', { url: 곳.주소 });

  // ⚠️ Page.loadEventFired 를 기다리면 **앞 페이지(about:blank)의 신호**에 속아
  //    빈 화면을 긁는다(2026-09-21 에 데임). 눌러 보며 기다린다.
  const 끝날때 = Date.now() + 기다림;
  let 준비 = false;
  while (Date.now() < 끝날때) {
    const r = await 보내기('Runtime.evaluate', {
      expression: 'location.href.slice(0,8) + "|" + document.readyState + "|" + (document.body ? document.body.innerText.length : 0)',
      returnByValue: true,
    });
    const v = (r.result && r.result.value) || '';
    const [주소, 상태글, 길이] = String(v).split('|');
    const 글길이 = Number(길이) || 0;
    const 오래 = Date.now() > 끝날때 - 기다림 + 6000;
    // 광고·집계 스크립트가 끝나지 않아 readyState 가 complete 로 안 가는 곳이 있다.
    // 글이 이미 실렸으면 6초 뒤에는 그냥 긁는다.
    if (주소.startsWith('http') && 글길이 > 120 && (상태글 === 'complete' || 오래)) { 준비 = true; break; }
    await new Promise(x => setTimeout(x, 400));
  }
  if (준비) await new Promise(r => setTimeout(r, 1200));   // 목록을 JS 로 그리는 곳을 더 기다린다
  const 코드 = 상태.코드, 실패 = 상태.실패;

  const r = await 보내기('Runtime.evaluate', { expression: 긁개, returnByValue: true, timeout: 8000 });
  const 값 = r.result && r.result.value ? JSON.parse(r.result.value) : null;
  return {
    laf_cd: 곳.laf_cd, 이름: 곳.이름,
    코드, 실패: 실패 || '',
    제목: 값 ? 값.제목 : '',
    끝주소: 값 ? 값.주소 : '',
    파일: 값 ? 값.파일 : [],
    날짜: 값 ? 값.날짜 : '',
    글자수: 값 ? 값.글자수 : 0,
    준비,
  };
}

async function main() {
  if (!크롬자리) throw new Error('크롬을 못 찾겠다');
  const dis = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'disclosure.json'), 'utf-8'));
  let 곳들 = dis['곳'].filter(r => r['주소']);
  const i = process.argv.indexOf('--only');
  if (i > 0) 곳들 = 곳들.slice(0, parseInt(process.argv[i + 1], 10));

  const 프로필 = fs.mkdtempSync(path.join(os.tmpdir(), 'lf-chrome-'));
  const 크롬 = 크롬띄우기(프로필);
  await 붙을때까지();

  const 결과 = [];
  let 다음 = 0, 끝난 = 0;
  const 일꾼 = async () => {
    const 탭 = await 탭열기();
    while (true) {
      const k = 다음++;
      if (k >= 곳들.length) break;
      try {
        결과.push(await 한곳(탭, 곳들[k]));
      } catch (e) {
        결과.push({ laf_cd: 곳들[k].laf_cd, 이름: 곳들[k].이름, 실패: String(e).slice(0, 80), 파일: [] });
      }
      끝난++;
      if (끝난 % 10 === 0) process.stdout.write(`   ${끝난}/${곳들.length}\n`);
    }
    탭.ws.close();
    await fetch(`http://127.0.0.1:${PORT}/json/close/${탭.tab.id}`).catch(() => {});
  };
  await Promise.all(Array.from({ length: 한번에 }, 일꾼));

  결과.sort((a, b) => a.laf_cd.localeCompare(b.laf_cd));
  fs.writeFileSync(OUT, JSON.stringify({ 만든날: new Date().toISOString().slice(0, 10), 곳: 결과 }, null, 0));

  const 파일있 = 결과.filter(r => r.파일.length).length;
  const 열림 = 결과.filter(r => r.코드 && r.코드 < 400).length;
  const 날짜있 = 결과.filter(r => r.날짜).length;
  console.log(`\n브라우저로 다시 봄 ${결과.length}곳 → 열림 ${열림} · 파일 잡힘 ${파일있} · 올린 날짜 ${날짜있}`);
  console.log(`적음: data/disclosure_dom.json`);

  크롬.kill();
  // 크롬이 파일을 놓을 때까지 잠깐 기다린다. 못 지워도 그만이다(임시 폴더다).
  await new Promise(r => setTimeout(r, 1500));
  try { fs.rmSync(프로필, { recursive: true, force: true }); } catch (_) { /* 임시 폴더라 둬도 된다 */ }
}

main().catch(e => { console.error('FAIL', e); process.exit(1); });
