export function selectRows(rows, filters = {}) {
  const query = (filters.query || '').trim().toLocaleLowerCase('ko');
  return rows.filter(row =>
    (filters.includePossible || row.상태 === '걸림') &&
    (!filters.year || row.해 === filters.year) &&
    (!filters.category || row.갈래 === filters.category) &&
    (!filters.item || row.품목 === filters.item) &&
    (!filters.region || row.시도 === filters.region) &&
    (!filters.municipality || row.코드 === filters.municipality) &&
    (!filters.vendor || row.업체묶음 === filters.vendor) &&
    (!query || [row.계약명, row.업체, row.업체묶음, row.지자체, row.시도].join(' ').toLocaleLowerCase('ko').includes(query))
  );
}

export function summarize(rows) {
  return {
    count: rows.length,
    amount: rows.reduce((sum, row) => sum + row.금액, 0),
    municipalities: new Set(rows.map(row => row.코드)).size,
    vendors: new Set(rows.map(row => row.업체묶음)).size,
    possible: rows.filter(row => row.상태 === '놓쳤을 수 있음').length,
  };
}

export function groupRows(rows, key) {
  const groups = new Map();
  for (const row of rows) {
    const name = row[key];
    if (!groups.has(name)) groups.set(name, []);
    groups.get(name).push(row);
  }
  return [...groups].map(([key, rows]) => ({ key, rows, ...summarize(rows) }))
    .sort((a, b) => b.amount - a.amount || a.key.localeCompare(b.key, 'ko'));
}

export function annualSeries(rows) {
  return [...new Set(rows.map(row => row.해))].sort().map(year => {
    const part = rows.filter(row => row.해 === year);
    return {
      year,
      install: summarize(part.filter(row => row.갈래 === '설치')),
      maintenance: summarize(part.filter(row => row.갈래 === '유지관리')),
      other: summarize(part.filter(row => !['설치', '유지관리'].includes(row.갈래))),
    };
  });
}
