const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const { 긁개 } = require('./recheck_disclosure');

test('파일이 많은 예산서 화면에서도 뒤쪽 사업명세서를 놓치지 않는다', () => {
  const links = Array.from({ length: 45 }, (_, i) => {
    const name = `세출예산사업명세서(부서${i}).pdf`;
    const href = `/files/${i}.pdf`;
    return {
      textContent: name,
      href: `https://example.go.kr${href}`,
      getAttribute: key => key === 'href' ? href : null,
      closest: () => null,
      parentElement: null,
    };
  });
  const document = {
    title: '2026년 본예산',
    body: { innerText: '' },
    querySelectorAll: () => links,
  };
  const location = { href: 'https://example.go.kr/budget', hostname: 'example.go.kr' };
  const result = JSON.parse(vm.runInNewContext(긁개, { document, location, URL }));
  assert.equal(result.파일.length, 45);
  assert.equal(result.파일.at(-1).이름, '세출예산사업명세서(부서44).pdf');
});

test('fileName 속성 단추(대구본청)와 file_id 그림 단추(계룡)도 파일로 줍는다', () => {
  const 링크 = (text, attrs) => ({
    textContent: text,
    href: '',
    getAttribute: key => attrs[key] ?? null,
    closest: () => null,
    parentElement: null,
  });
  const links = [
    링크('공보관', { href: '#none', filename: '2026_본예산_2_세출예산사업명세서_1_공보관.pdf' }),
    링크('', { href: '/_prog/dn00/?file_id=9b0a947dd099', title: '본청(전략기획감사실~상하수도과) pdf 다운로드' }),
  ];
  const document = { title: '예산', body: { innerText: '' }, querySelectorAll: () => links };
  const location = { href: 'https://example.go.kr/budget', hostname: 'example.go.kr' };
  const result = JSON.parse(vm.runInNewContext(긁개, { document, location, URL }));
  assert.deepEqual(result.파일.map(f => f.이름), ['2026_본예산_2_세출예산사업명세서_1_공보관.pdf', '본청(전략기획감사실~상하수도과)']);
});
