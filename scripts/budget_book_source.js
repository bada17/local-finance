// 사람이 확인한 예산서 자리를 우선한다. 빈 주소도 '미확인'이라는 판정이다.
function 예산서주소(코드, BUDLK, 자리목록) {
  return Object.hasOwn(자리목록, 코드) ? (자리목록[코드].주소 || '') : BUDLK;
}

module.exports = { 예산서주소 };
