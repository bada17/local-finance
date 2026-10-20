// 3단계 ① — 게시판 글 안으로 들어가 **붙은 파일을 내려받고 본문 표를 적는다.** (2단계 fetch_boards.js 의 글 목록에서 시작)
//
//   node scripts/fetch_post_files.js                 아래 「고르기」 셋 전부
//   node scripts/fetch_post_files.js 단체장           하나만(단체장 · 의장 · 국외출장)
//   node scripts/fetch_post_files.js 단체장 4714000   그 곳만(시험, 파일에 안 적는다)
//   node scripts/fetch_post_files.js --몇=2           게시판마다 두 건만(시험 — 결과는 적는다, 이어 하면 나머지만 본다)
//
// 고르기 — 글이 5만 건이 넘어 다 열 수 없다(2026-10-13 셈). 쓸 데가 정해진 것부터:
//   단체장   지자체 업무추진비 게시판에서 제목에 시장·군수·구청장·도지사가 든 글(재료표 10번)
//   의장     의회 업무추진비 게시판에서 제목에 의장이 든 글
//   국외출장 의회 국외출장 게시판에서 제목에 국외·해외·출장·연수가 든 글(재료표 11번 — 계획과 결과보고서)
//
// 글 여는 법 — 주소가 있으면 바로, 없으면(눌러야 열리는 글) 목록을 열고 그 쪽까지 넘긴 뒤 **제목이 같은 링크를 누른다.**
// 파일 받는 법 — 내려받기 링크를 **누른다**(주소 없이 자바스크립트로 받는 곳이 많다). 크롬이 받은 파일을
//   캐시(저장소 밖, %LOCALAPPDATA%\local-finance-files)에 sha1 이름으로 옮긴다. 원본은 크고 많아서 저장소에 안 넣는다.
//   읽기는 read_post_files.py 가 한다.
//
// ⭐ 끊겨도 된다 — 글 하나마다 적고, 다시 부르면 남은 것만. 처음부터는 --다시
// 결과: data/post_files.json — {만든날, 글: {"laf|게시판|제목|날짜": {곳, 이름, 고르기, 제목, 날짜, 주소, 파일:[…], 표:[…], 까닭}}}

const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const { 크롬자리, 크롬띄우기, 붙을때까지, 탭열기, PORT, 기다림 } = require('./recheck_disclosure.js');

const ROOT = path.dirname(__dirname);
const OUT = path.join(ROOT, 'data', 'post_files.json');
const 캐시 = process.env.LF_FILES || path.join(process.env.LOCALAPPDATA || os.homedir(), 'local-finance-files');
const 한번에 = 10;

const 고르기 = {
  // 「○○시」의 구청장(성남 수정구청장 등 일반구)은 단체장이 아니다 — 시장이 없는 구청장 글은 뺀다
  단체장: { 파일: 'board_posts.json', 게시판: '업무추진비', 맞나: (t, 곳) => /시장|군수|구청장|도지사|단체장/.test(t) && !(/시$/.test(곳) && /구청장/.test(t) && !/시장/.test(t)) && !/부시장|부군수|부구청장|부지사/.test(t.replace(/(시장|군수|구청장|도지사)\s*(및|·|,|과|와)\s*부/, '')) },
  의장: { 파일: 'board_posts_council.json', 게시판: '업무추진비', 맞나: t => /의장/.test(t) },
  국외출장: { 파일: 'board_posts_council.json', 게시판: '국외출장', 맞나: t => /국외|해외|출장|연수/.test(t) },   // 게시판에 조례안·집회공고가 섞인 곳이 많다
};

// 글 화면 긁개 — 내려받기 후보(몇 번째 링크인지)와 본문 표
const 글긁개 = String.raw`(() => {
  const EXT = /\.(hwpx?|xlsx?|csv|pdf|docx?|zip|cell|show)(\b|$)/i;
  // fileid 는 낱말 앞이 끊긴 것만 — 번역 링크 profileId 가 걸렸다(수원)
  const 내려 = /download|filedown|file_down|atchfile|(^|[^a-z])file_?id|attach|getfile|fms\/|downfile|filedn|fileload|down\.do|down\(/i;
  // 「새창」은 거르지 않는다 — 내려받기 단추 설명에 「(새창)」이 붙는 곳이 많다(나주·여수). 화면 인쇄 pdf(screen_print)는 거른다
  const 아님 = /바로\s*보기|미리\s*보기|뷰어|preview|viewer|synap|docviewer|목록|이전|다음|인쇄|print|공유|sns|원격|remote|설치|플러그인|점자/i;   // 원격지원.zip(영덕)·점자 파일
  const 링크 = [...document.querySelectorAll('a,button,input[type=button]')];
  const 후보 = [], 본 = new Set();
  링크.forEach((a, i) => {
    const t = (a.textContent || a.value || '').replace(/\s+/g, ' ').trim();
    const h = a.getAttribute('href') || '';
    const oc = a.getAttribute('onclick') || '';
    if (아님.test(t) || 아님.test(a.title || '') || /preview|viewer|synap|docview|screen_print/i.test(h + oc)) return;
    // 누리집 머리·꼬리·메뉴의 링크는 글의 파일이 아니다(파주 「기업지원 시책 안내」 pdf)
    if (a.closest('header,footer,nav,#header,#footer,.header,.footer,#gnb,.gnb,#lnb,.lnb,.quick,#quick,.banner,.util')) return;
    if (!(EXT.test(t) || EXT.test(h) || 내려.test(h) || 내려.test(oc))) return;
    const 뚜렷 = EXT.test(t) || EXT.test(h) || EXT.test(a.title || '');
    const 열쇠 = (h && !/^(#|javascript:void)/i.test(h) ? h : '') + '|' + oc;
    if (열쇠 !== '|' && 본.has(열쇠)) return;
    본.add(열쇠);
    후보.push({ 번째: i, 이름: (t || a.title || '').slice(0, 120), 주소: (a.href || '').slice(0, 300), 뚜렷 });
  });
  // 파일 이름(확장자)이 보이는 링크가 있으면 그것만 — 「내려받기」 낱말만 걸린 메뉴 링크(여수 「행사축제원가회계」)를 뺀다
  if (후보.some(x => x.뚜렷)) 후보.splice(0, 후보.length, ...후보.filter(x => x.뚜렷));
  const 표 = [...document.querySelectorAll('table')].filter(t => !t.querySelector('table'))
    .map(t => [...t.rows].map(r => [...r.cells].map(c => (c.innerText || '').replace(/\s+/g, ' ').trim())))
    .filter(rs => rs.length >= 2 && rs.some(r => r.some(c => /\d{1,3}(,\d{3})+/.test(c))));
  return JSON.stringify({ 화면: (document.title || '').slice(0, 80), 주소: location.href.slice(0, 300), 후보: 후보.slice(0, 20), 표: 표.slice(0, 10) });
})()`;

// fetch_boards.js 와 같은 다음 쪽 찾기
const 쪽식 = n => String.raw`(() => {
  const as = [...document.querySelectorAll('a')];
  const 글 = a => (a.textContent || '').replace(/\s+/g, '').trim();
  const 쪽칸 = a => !!a.closest('[class*=pag],[id*=pag],[class*=Pag],[class*=page],nav');
  let i = as.findIndex(a => 글(a) === '${n}' && 쪽칸(a));
  if (i < 0) i = as.findIndex(a => 쪽칸(a) && /^(다음|다음페이지|next|›|>)$/i.test(글(a) || (a.title || '').replace(/\s+/g, '')));
  return String(i);
})()`;
const 제목찾기식 = 제목 => `(() => {
  const 같게 = s => (s || '').replace(/\\s+/g, ' ').trim();
  const 찾는 = ${JSON.stringify(제목)};
  const as = [...document.querySelectorAll('a')];
  let i = as.findIndex(a => 같게(a.textContent).slice(0, 120) === 찾는);
  if (i < 0) i = as.findIndex(a => 같게(a.textContent).startsWith(찾는.slice(0, 30)));
  return String(i);
})()`;

async function 기다리기(보내기, 먼저 = 0) {
  if (먼저) await new Promise(x => setTimeout(x, 먼저));
  const 끝 = Date.now() + 기다림;
  while (Date.now() < 끝) {
    const r = await 보내기('Runtime.evaluate', { expression: 'document.readyState + "|" + (document.body ? document.body.innerText.length : 0)', returnByValue: true });
    const [상태, 길이] = String((r.result && r.result.value) || '').split('|');
    if (상태 === 'complete' && Number(길이) > 100) break;
    await new Promise(x => setTimeout(x, 400));
  }
  await new Promise(x => setTimeout(x, 800));
}
const 값 = async (보내기, 식) => {
  const r = await 보내기('Runtime.evaluate', { expression: 식, returnByValue: true, timeout: 8000 });
  return r.result ? r.result.value : undefined;
};
const 누르기 = (보내기, i, 고르개 = 'a') => 보내기('Runtime.evaluate', {
  // 새 탭으로 여는 링크(target=_blank)는 그 속성을 떼고 누른다 — 새 탭은 연 탭 정보(opener)가 끊겨 어느 탭 파일인지 못 가린다(영덕·속초)
  expression: `(() => { const a = document.querySelectorAll(${JSON.stringify(고르개)})[${i}]; const h = a.getAttribute('href') || '';
    if (a.target && h && !/^(#|javascript)/i.test(h)) a.removeAttribute('target'); a.click(); })()`,
  userGesture: true,
});   // userGesture — 없으면 window.open 이 팝업 차단에 막힌다

// 글 하나 열기 — 주소가 있으면 바로, 없으면 목록에서 쪽을 넘겨 제목으로 찾아 누른다
// 쪽 번호가 주소에 실리는 게시판이면 그 틀을 한 번 배운다 — 2쪽·3쪽 주소에서 값이 다른 숫자 칸 하나를 찾는다.
//   ⭐ 성남(쪽 넘기기 1만 6천 번)·달성·파주처럼 글이 수백 쪽 뒤에 있는 곳을 1쪽부터 누르며 가지 않으려고(2026-10-13).
//   주소가 안 바뀌는 게시판(자바스크립트로 쪽을 그리는 곳)은 틀이 없고, 예전처럼 눌러서 간다.
async function 쪽틀배우기(탭, 판) {
  판.쪽틀 = null;
  await 탭.보내기('Page.navigate', { url: 판.주소 });
  await 기다리기(탭.보내기);
  const 주소들 = [];
  for (const n of [2, 3]) {
    const j = Number(await 값(탭.보내기, 쪽식(n)));
    if (!(j >= 0)) return;
    await 누르기(탭.보내기, j);
    await 기다리기(탭.보내기, 1500);
    주소들.push(await 값(탭.보내기, 'location.href'));
  }
  let a, b;
  try { [a, b] = 주소들.map(u => new URL(u)); } catch (e) { return; }
  for (const [k, v] of a.searchParams) {
    const w = b.searchParams.get(k);
    if (w !== null && w !== v && /^\d+$/.test(v) && /^\d+$/.test(w)) { 판.쪽틀 = { 칸: k, 이쪽: +v, 걸음: +w - +v, 주소: a.href }; return; }
  }
}
function 쪽주소(판, n) {
  const u = new URL(판.쪽틀.주소);
  u.searchParams.set(판.쪽틀.칸, String(판.쪽틀.이쪽 + (n - 2) * 판.쪽틀.걸음));
  return u.href;
}

// 글 하나 열기 — 주소가 있으면 바로, 없으면 목록의 그 쪽으로 가서 제목으로 찾아 누른다
async function 글열기(탭, 판, 글, 주소로 = true) {
  if (주소로 && 글.주소 && !/FileDown|fileDown|filedown|download/i.test(글.주소)) {
    판.목록자리 = null;
    await 탭.보내기('Page.navigate', { url: 글.주소 });
    await 기다리기(탭.보내기);
    return '';
  }
  // 2단계 뒤로 새 글이 올라오면 옛 글은 뒤 쪽으로 밀린다(파주 하루에 두 쪽) — 한 번 밀린 만큼은 다음 글에도 더한다
  const 쪽 = (글.쪽 || 1) + (판.밀림 || 0);
  const 찾기 = async () => Number(await 값(탭.보내기, 제목찾기식(글.제목)));
  const 찾음 = n => { 판.지금쪽 = n; 판.밀림 = Math.max(판.밀림 || 0, n - (글.쪽 || 1)); };
  let i = -1;
  // ① 방금 목록에서 글을 열었으면 그 목록(방문 기록의 그 자리)으로 돌아가 앞으로만 넘긴다 — 글은 쪽 순서로 연다.
  //    쪽 주소가 안 바뀌는 게시판(파주 — 폼으로 쪽을 넘김)에서 1쪽부터 다시 누르지 않으려고. 안 되면 아래 ②·③
  if (판.목록자리 && 판.지금쪽 && 판.지금쪽 <= 쪽 + 2) {
    await 탭.보내기('Page.navigateToHistoryEntry', { entryId: 판.목록자리 });
    await 기다리기(탭.보내기, 1000);
    for (let n = 판.지금쪽; n <= Math.max(쪽, 판.지금쪽) + 2; n++) {
      if (n > 판.지금쪽) {
        const j = Number(await 값(탭.보내기, 쪽식(n)));
        if (!(j >= 0)) break;
        await 누르기(탭.보내기, j);
        await 기다리기(탭.보내기, 1500);
      }
      i = await 찾기();
      if (i >= 0) { 찾음(n); break; }
    }
  }
  판.목록자리 = null;
  // ② 쪽 번호가 주소에 실리면 그 쪽으로 바로
  if (!(i >= 0) && 판.쪽틀 === undefined && 쪽 > 3) await 쪽틀배우기(탭, 판);
  if (!(i >= 0) && 판.쪽틀 && 쪽 >= 2) {
    for (let 더 = 0; !(i >= 0) && 더 <= 2; 더++) {
      await 탭.보내기('Page.navigate', { url: 쪽주소(판, 쪽 + 더) });
      await 기다리기(탭.보내기);
      i = await 찾기();
      if (i >= 0) 찾음(쪽 + 더);
    }
  }
  if (!(i >= 0)) {   // ③ 1쪽부터 눌러서
    await 탭.보내기('Page.navigate', { url: 판.주소 });
    await 기다리기(탭.보내기);
    let n = 1;
    for (n = 2; n <= 쪽; n++) {
      const j = Number(await 값(탭.보내기, 쪽식(n)));
      if (!(j >= 0)) return `${n}쪽으로 못 넘김`;
      await 누르기(탭.보내기, j);
      await 기다리기(탭.보내기, 1500);
    }
    n = 쪽;
    i = await 찾기();
    for (let 더 = 1; !(i >= 0) && 더 <= 2; 더++) {
      const j = Number(await 값(탭.보내기, 쪽식(쪽 + 더)));
      if (!(j >= 0)) break;
      await 누르기(탭.보내기, j);
      await 기다리기(탭.보내기, 1500);
      i = await 찾기();
      n = 쪽 + 더;
    }
    if (i >= 0) 찾음(n);
  }
  if (!(i >= 0)) return '목록에서 제목을 못 찾음';
  const 기록 = await 탭.보내기('Page.getNavigationHistory');
  판.목록자리 = 기록.entries ? 기록.entries[기록.currentIndex].id : null;
  await 누르기(탭.보내기, i);
  await 기다리기(탭.보내기, 1500);
  return '';
}

// 받은 파일을 캐시로 — sha1 이름, 확장자는 크롬이 알려 준 이름에서
function 캐시로(임시, 이름) {
  const 몸 = fs.readFileSync(임시);
  const sha1 = crypto.createHash('sha1').update(몸).digest('hex');
  const 확장자 = (path.extname(이름 || '') || '.bin').toLowerCase().slice(0, 6);
  const 자리 = path.join(캐시, sha1.slice(0, 2), sha1 + 확장자);
  fs.mkdirSync(path.dirname(자리), { recursive: true });
  if (!fs.existsSync(자리)) fs.copyFileSync(임시, 자리);
  fs.unlinkSync(임시);
  return { 이름, 확장자: 확장자.slice(1), 크기: 몸.length, sha1 };
}

// ⭐ 내려받기는 **크롬 전체(브라우저) 쪽**에서 듣는다 — 누리집 대부분이 window.open 으로 새 창을 띄워 받아서(안동 fn_egov_downFile)
//   탭 쪽에는 신호가 안 온다(2026-10-13 시험). 어느 탭 것인지는 frameId 로 가린다: 탭에서 바로 받으면 탭 id 와 같고,
//   새 창이면 그 창을 연 탭(openerId)을 따라간다. 그래서 탭 열이 동시에 받아도 섞이지 않는다.
async function 브라우저붙기(받는곳) {
  const v = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json();
  const ws = new WebSocket(v.webSocketDebuggerUrl);
  await new Promise(res => ws.addEventListener('open', res));
  let id = 0;
  const 기다리는 = new Map();
  const 판 = { 탭들: new Map(), 연탭: new Map(), 끝: {} };   // 탭들: 탭 id → {시작}, 연탭: 새 창 id → 연 탭 id
  const 주인 = f => 판.탭들.has(f) ? f : 판.연탭.get(f);
  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && 기다리는.has(m.id)) { 기다리는.get(m.id)(m.result || m.error || {}); 기다리는.delete(m.id); }
    if (m.method === 'Target.targetCreated' && m.params.targetInfo.openerId) 판.연탭.set(m.params.targetInfo.targetId, 주인(m.params.targetInfo.openerId) || m.params.targetInfo.openerId);
    if (m.method === 'Browser.downloadWillBegin') {
      let 탭 = 판.탭들.get(주인(m.params.frameId));
      if (!탭) { const 기다림탭 = [...판.탭들.values()].filter(t => t.시작); if (기다림탭.length === 1) 탭 = 기다림탭[0]; }   // 안쪽 틀(iframe)에서 받은 것
      if (탭 && 탭.시작) { const f = 탭.시작; 탭.시작 = null; f(m.params); }
    }
    if (m.method === 'Browser.downloadProgress' && m.params.state !== 'inProgress' && 판.끝[m.params.guid]) 판.끝[m.params.guid](m.params.state);
  });
  판.보내기 = (method, params = {}) => new Promise(res => { const i = ++id; 기다리는.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); setTimeout(() => { if (기다리는.has(i)) { 기다리는.delete(i); res({}); } }, 10000); });
  await 판.보내기('Browser.setDownloadBehavior', { behavior: 'allowAndName', downloadPath: 받는곳, eventsEnabled: true });
  await 판.보내기('Target.setDiscoverTargets', { discover: true });
  // 새 창으로 받는 곳이 남긴 빈 창을 닫는다(우리 일꾼 탭은 빼고)
  판.청소 = async (탭id) => {
    for (const [창, 연] of 판.연탭) if (!탭id || 연 === 탭id) { await 판.보내기('Target.closeTarget', { targetId: 창 }); 판.연탭.delete(창); }
  };
  판.처음청소 = async () => {
    const r = await 판.보내기('Target.getTargets');
    for (const t of (r.targetInfos || [])) if (t.type === 'page' && !판.탭들.has(t.targetId)) await 판.보내기('Target.closeTarget', { targetId: t.targetId });
  };
  판.ws = ws;
  return 판;
}

// 페이지 안에서 fetch 로 가져온다(쿠키 그대로). 웹 화면(html)이 오면 파일이 아니다. 30MB 넘으면 안 받는다
async function 직접받기(탭, h) {
  const r = await 탭.보내기('Runtime.evaluate', {
    expression: `(async () => { try {
      const r = await fetch(${JSON.stringify(h.주소)}, { credentials: 'include' });
      const ct = r.headers.get('content-type') || '', cd = r.headers.get('content-disposition') || '';
      if (!r.ok || /text\/html/i.test(ct)) return JSON.stringify({ 못: r.status + ' ' + ct });
      const b = new Uint8Array(await r.arrayBuffer());
      if (b.length > 30e6) return JSON.stringify({ 못: '30MB 넘음' });
      let s = ''; for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000));
      return JSON.stringify({ cd, b64: btoa(s) });
    } catch (e) { return JSON.stringify({ 못: String(e).slice(0, 60) }); } })()`,
    awaitPromise: true, returnByValue: true,
  });
  let v; try { v = JSON.parse((r.result && r.result.value) || '{}'); } catch (e) { return null; }
  if (!v.b64) return null;
  let 이름 = h.이름;
  const m = (v.cd || '').match(/filename\*?=(?:UTF-8'')?"?([^";]+)/i);
  if (m) { try { 이름 = decodeURIComponent(m[1]); } catch (e) { 이름 = m[1]; } }
  const 임시 = path.join(os.tmpdir(), 'lf-direct-' + crypto.randomBytes(6).toString('hex'));
  fs.writeFileSync(임시, Buffer.from(v.b64, 'base64'));
  return { ...캐시로(임시, 이름), 직접: true };
}

// 이름 맞추기 — 「…xlsx [12.9 KByte]」 같은 꼬리와 띄어쓰기를 뗀다
const 이름열쇠 = n => (n || '').replace(/\[[^\]]*\]|\([\d.,]+\s*[KMG]?B(yte)?\)/gi, '').replace(/[\s+]/g, '').toLowerCase();

async function 파일받기(탭, 판, 받는곳, 후보, 받은것) {
  const 받음 = [];
  const 글주소 = await 값(탭.보내기, 'location.href');
  const 내것 = 판.탭들.get(탭.tab.id);
  for (const h of 후보) {
    // 한 글을 열면 게시판 파일이 다 보이는 곳이 있다(대전 중구·유성구) — 같은 게시판에서 이미 받은 이름은 다시 안 누른다
    const 열쇠 = 이름열쇠(h.이름);
    if (열쇠.length > 6 && 받은것.has(열쇠)) { 받음.push({ ...받은것.get(열쇠), 앞서받음: true }); continue; }
    const 시작 = new Promise(res => { 내것.시작 = res; setTimeout(() => res(null), 5000); });
    await 누르기(탭.보내기, h.번째, 'a,button,input[type=button]');
    const 처음 = await 시작;
    내것.시작 = null;
    if (!처음) {
      await 판.청소(탭.tab.id);
      // 눌러도 안 받아지면(파일을 화면에 띄우는 곳 — 영덕) 주소가 있는 링크는 그 주소를 직접 가져온다
      const 직접 = /^https?:/.test(h.주소 || '') ? await 직접받기(탭, h) : null;
      if (직접) { if (열쇠.length > 6) 받은것.set(열쇠, 직접); 받음.push(직접); continue; }
      받음.push({ 이름: h.이름, 까닭: '내려받기가 안 일어남' });
      // 받기가 아니라 딴 화면으로 넘어갔으면 글로 돌아온다 — 다음 후보 번호가 어긋나지 않게
      if ((await 값(탭.보내기, 'location.href')) !== 글주소) { await 탭.보내기('Page.navigate', { url: 글주소 }); await 기다리기(탭.보내기); }
      continue;
    }
    const 끝 = await new Promise(res => { 판.끝[처음.guid] = res; setTimeout(() => res('시간 넘김'), 90000); });
    delete 판.끝[처음.guid];
    await 판.청소(탭.tab.id);
    const 임시 = path.join(받는곳, 처음.guid);
    if (끝 !== 'completed' || !fs.existsSync(임시)) { 받음.push({ 이름: 처음.suggestedFilename || h.이름, 까닭: String(끝) }); continue; }
    const f = 캐시로(임시, 처음.suggestedFilename || h.이름);
    if (열쇠.length > 6) 받은것.set(열쇠, f);
    받음.push(f);
  }
  return 받음;
}

async function main() {
  if (!크롬자리) throw new Error('크롬을 못 찾겠다');
  const 인자 = process.argv.slice(2);
  const 고른것 = 인자.filter(a => 고르기[a]);
  const 한곳만 = 인자.filter(a => /^\d{7}$/.test(a));
  const 몇 = Number((인자.find(a => a.startsWith('--몇=')) || '').slice(4)) || 0;   // 시험: 게시판마다 몇 건만(--몇=3)
  const 시험 = 한곳만.length > 0 || 몇 > 0;
  const 결과 = !process.argv.includes('--다시') && fs.existsSync(OUT) ? JSON.parse(fs.readFileSync(OUT, 'utf-8'))['글'] : {};
  const 적기 = () => { if (!한곳만.length) fs.writeFileSync(OUT, JSON.stringify({ 만든날: new Date().toISOString().slice(0, 10), 글: 결과 }, null, 1)); };

  // 게시판(곳·과녁) 하나가 일감 하나 — 같은 게시판 글은 한 탭이 차례로 연다(쪽 넘기기 때문)
  const 일감 = [];
  for (const [이름, g] of Object.entries(고르기)) {
    if (고른것.length && !고른것.includes(이름)) continue;
    const 곳들 = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', g.파일), 'utf-8'))['곳'];
    for (const [laf, v] of Object.entries(곳들)) {
      if (한곳만.length && !한곳만.includes(laf)) continue;
      const 판 = v[g.게시판];
      if (!판 || 판.종류 !== '게시판') continue;
      const 글들 = (판.글 || []).filter(x => g.맞나(x.제목, v.이름))
        .map(x => ({ ...x, 열쇠: [laf, (g.파일.includes('council') ? '의회 ' : '') + g.게시판, x.제목, x.날짜].join('|') }))
        .filter(x => 한곳만.length || !결과[x.열쇠] || 결과[x.열쇠].까닭)
        .slice(0, 몇 || undefined)
        .sort((a, b) => (a.쪽 || 1) - (b.쪽 || 1));   // 쪽 순서로 연다 — 「뒤로」 뒤 앞으로만 넘기게
      if (글들.length) 일감.push({ laf, 곳이름: v.이름, 고르기: 이름, 판, 글들 });
    }
  }
  // 고르기를 좁히면(성남 일반구 구청장을 뺌, 10-13) 예전에 받은 글이 남는다 — 전부 돌릴 때만 걷는다
  //   2단계 목록에서 빠진 것(봇이 한 달 실패)은 지우지 않는다 — 고르기 규칙에 안 맞는 것만
  if (!한곳만.length && !몇) for (const [k, x] of Object.entries(결과)) if (고르기[x.고르기] && !고르기[x.고르기].맞나(x.제목, x.이름)) delete 결과[k];
  const 모두 = 일감.reduce((s, x) => s + x.글들.length, 0);
  console.log(`게시판 ${일감.length}개 · 글 ${모두}건 · 캐시 ${캐시}`);
  if (!일감.length) return;
  일감.sort((a, b) => b.글들.length - a.글들.length);   // 긴 것부터 — 끝에 한 탭만 오래 남지 않게

  const 프로필 = fs.mkdtempSync(path.join(os.tmpdir(), 'lf-files-'));
  const 크롬 = 크롬띄우기(프로필);
  await 붙을때까지();
  const 받는곳 = fs.mkdtempSync(path.join(os.tmpdir(), 'lf-dl-'));
  const 판 = await 브라우저붙기(받는곳);
  await 판.처음청소();   // 크롬이 처음 띄운 about:blank
  let 다음 = 0, 끝난 = 0, 파일수 = 0;
  const 일꾼 = async () => {
    const 탭 = await 탭열기();
    판.탭들.set(탭.tab.id, { 시작: null });
    // 「다운로드 받으시겠습니까?」 확인 창(진주·함안·창원)이 뜨면 크롬이 멈춘다 — 늘 「확인」을 누른다
    탭.듣기('Page.javascriptDialogOpening', () => 탭.보내기('Page.handleJavaScriptDialog', { accept: true }));
    while (다음 < 일감.length) {
      const 일 = 일감[다음++];
      const 받은것 = new Map();
      for (const 글 of 일.글들) {
        let 줄;
        try {
          let 못연까닭 = await 글열기(탭, 일.판, 글);
          let 화면 = 못연까닭 ? {} : JSON.parse((await 값(탭.보내기, 글긁개)) || '{}');
          // 2단계가 적은 글 주소가 잘린 곳이 있다(밀양 — 글 번호가 빠짐). 주소로 열어 아무것도 없으면 목록에서 눌러 다시
          if (!못연까닭 && 글.주소 && !(화면.후보 || []).length && !(화면.표 || []).length) {
            못연까닭 = await 글열기(탭, 일.판, 글, false);
            if (!못연까닭) 화면 = JSON.parse((await 값(탭.보내기, 글긁개)) || '{}');
          }
          if (못연까닭) 줄 = { 까닭: 못연까닭 };
          else {
            const 파일 = await 파일받기(탭, 판, 받는곳, 화면.후보 || [], 받은것);
            파일수 += 파일.filter(f => f.sha1).length;
            줄 = { 주소: 화면.주소, 파일, 표: 화면.표 || [], ...(파일.some(f => f.sha1) || (화면.표 || []).length ? {} : { 까닭: '파일·표 없음' }) };
          }
        } catch (e) { 줄 = { 까닭: '멈췄다 ' + String(e).slice(0, 60) }; }
        결과[글.열쇠] = { 곳: 일.laf, 이름: 일.곳이름, 고르기: 일.고르기, 제목: 글.제목, 날짜: 글.날짜, ...줄 };
        if (시험) console.log(JSON.stringify({ ...결과[글.열쇠], 표: (결과[글.열쇠].표 || []).length }));
        try { 적기(); } catch (e) { /* 윈도 파일 잠김 — 다음에 쓴다 */ }
        if (++끝난 % 50 === 0) console.log(`   ${끝난}/${모두} · 파일 ${파일수}`);
      }
    }
    탭.ws.close();
    await fetch(`http://127.0.0.1:${PORT}/json/close/${탭.tab.id}`).catch(() => {});
  };
  await Promise.all(Array.from({ length: Math.min(한번에, 일감.length) }, 일꾼));
  판.ws.close();
  크롬.kill();
  적기();
  const 줄들 = Object.values(결과);
  const 셈 = {};
  for (const x of 줄들) { const k = x.까닭 ? x.까닭.replace(/\d+쪽/, 'n쪽').slice(0, 20) : '됨'; 셈[k] = (셈[k] || 0) + 1; }
  console.log(`글 ${줄들.length}건 · 파일 ${파일수}개 받음 ·`, JSON.stringify(셈));
}

// click_budget_books.js 가 크롬 받기를 빌려 쓴다(2026-10-20)
module.exports = { 브라우저붙기, 파일받기, 기다리기, 값, 캐시 };
if (require.main === module) main().catch(e => { console.error(e); process.exit(1); });
