// 예산서 봇(read_budget_books.py)이 못 받는 「누르는 단추」 파일을 크롬으로 눌러 받는다 — fetch_post_files.js 의 받기를 빌려 쓴다.
//   node scripts/click_budget_books.js 일감.json     일감 = [{바탕, 이름, 주소, 자리}] — read_budget_books.py 가 만들어 부른다
// 찾는 법 — check_budget_docs.js 의 긁개가 적은 주소(href 또는 onclick, 160자)와 같은 단추. 여럿이면 이름이 같은 줄에 있는 것.
const fs = require('fs');
const path = require('path');
const os = require('os');
const { 크롬자리, 크롬띄우기, 붙을때까지, 탭열기 } = require('./recheck_disclosure.js');
const { 브라우저붙기, 파일받기, 기다리기, 값, 캐시 } = require('./fetch_post_files.js');

const 찾개 = (주소, 이름) => `(() => {
  const 열쇠 = s => (s || '').replace(/\s+/g, '');
  const 이름 = 열쇠(${JSON.stringify(이름)}).slice(0, 8);
  const 다 = [...document.querySelectorAll('a,button,input[type=button]')];
  const 맞 = 다.map((a, i) => [a, i]).filter(([a]) => {
    const h = a.getAttribute('href') || '', oc = (a.getAttribute('onclick') || '') + (a.getAttribute('data-href') || '');
    return (h || oc).slice(0, 160) === ${JSON.stringify(주소)};
  });
  const 줄 = 맞.find(([a]) => 열쇠((a.closest('tr,li,dd') || a.parentElement || a).innerText).includes(이름));
  return (줄 || 맞[0] || [null, -1])[1];
})()`;

(async () => {
  const 일감 = JSON.parse(fs.readFileSync(process.argv[2], 'utf-8'));
  if (!크롬자리) throw new Error('크롬을 못 찾겠다');
  const 크롬 = 크롬띄우기(fs.mkdtempSync(path.join(os.tmpdir(), 'lf-books-')));
  await 붙을때까지();
  const 받는곳 = fs.mkdtempSync(path.join(os.tmpdir(), 'lf-dl-'));
  const 판 = await 브라우저붙기(받는곳);
  await 판.처음청소();
  const 탭 = await 탭열기();
  판.탭들.set(탭.tab.id, { 시작: null });
  탭.듣기('Page.javascriptDialogOpening', () => 탭.보내기('Page.handleJavaScriptDialog', { accept: true }));
  let 됨 = 0;
  for (const 일 of 일감) {
    try {
      await 탭.보내기('Page.navigate', { url: 일.바탕 });
      await 기다리기(탭.보내기);
      const 번째 = await 값(탭.보내기, 찾개(일.주소, 일.이름));
      if (!(번째 >= 0)) { console.log('단추 못 찾음', 일.이름); continue; }
      const [f] = await 파일받기(탭, 판, 받는곳, [{ 이름: 일.이름, 번째, 주소: '' }], new Map());
      if (!f || !f.sha1) { console.log('안 받아짐', 일.이름, f && f.까닭); continue; }
      fs.copyFileSync(path.join(캐시, f.sha1.slice(0, 2), f.sha1 + '.' + f.확장자), 일.자리);
      됨++;
    } catch (e) { console.log('틀림', 일.이름, String(e).slice(0, 60)); }
  }
  console.log(`누르기 ${일감.length}개 중 ${됨}개 받음`);
  판.ws.close(); 탭.ws.close(); 크롬.kill();
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
