import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { selectRows, summarize, groupRows, annualSeries } from './model.mjs';

const { rows } = JSON.parse(await readFile(new URL('./data.json', import.meta.url), 'utf8'));
const selected = selectRows(rows);
assert(selected.every(row => row.상태 === '걸림'));
assert.equal(selected.length, rows.filter(row => row.상태 === '걸림' && row.갈래 !== '임차').length);
assert.equal(selectRows(rows, { includePossible: true }).length, rows.filter(row => row.갈래 !== '임차').length);
assert.equal(selectRows(rows, {category: '임차'}).length, rows.filter(row=>row.갈래 === '임차').length);
assert.equal(summarize(selected).amount, selected.reduce((total, row) => total + row.금액, 0));
assert.equal(summarize(selected).municipalities, new Set(selected.map(row => row.코드)).size);
const siheung = selectRows(rows, { municipality: '4125000' });
assert(siheung.length > 0);
assert(siheung.every(row => row.지자체.includes('시흥시') && row.상태 === '걸림'));
const filtered = selectRows(rows, { year: '2024', category: '유지관리', item: '페트', region: '경기' });
assert(filtered.length > 0);
assert(filtered.every(row => row.해 === '2024' && row.갈래 === '유지관리' && row.품목 === '페트' && row.시도 === '경기'));
assert.equal(groupRows(selected, '업체묶음').reduce((total, group) => total + group.amount, 0), summarize(selected).amount);
assert.equal(groupRows(selected, '코드').reduce((total, group) => total + group.count, 0), selected.length);
assert.equal(annualSeries(selected).reduce((total, year) => total + year.install.amount + year.maintenance.amount + year.other.amount, 0), summarize(selected).amount);
assert.equal(summarize([]).amount, 0);
assert.equal(summarize([]).municipalities, 0);
assert.deepEqual(selectRows(rows, { query: '<script>does-not-exist</script>' }), []);
// One code can have multiple historical names; it must remain one municipality.
assert.equal(summarize([{ 코드: 'one', 금액: 3 }, { 코드: 'one', 금액: 7 }]).municipalities, 1);
console.log('PASS: source totals, default exclusion, filters, municipality identity, vendor shares and annual reconciliation');
