const test = require('node:test');
const assert = require('node:assert/strict');
const { 예산서주소 } = require('./budget_book_source');

test('예산서 자리 목록의 수정 주소가 이전 BUDLK보다 앞선다', () => {
  const places = { '2612000': { 주소: 'https://example.go.kr/2026-budget' } };
  assert.equal(예산서주소('2612000', 'https://example.go.kr/2024-budget', places), 'https://example.go.kr/2026-budget');
});

test('확인되지 않아 비운 주소는 이전 BUDLK로 되돌리지 않는다', () => {
  const places = { '2812000': { 주소: '', 어떻게: '못 찾음' } };
  assert.equal(예산서주소('2812000', 'https://old.example.go.kr/budget', places), '');
});

test('자리 목록에 없는 곳은 기존 BUDLK를 쓴다', () => {
  assert.equal(예산서주소('9999999', 'https://example.go.kr/budget', {}), 'https://example.go.kr/budget');
});
