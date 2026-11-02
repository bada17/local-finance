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
