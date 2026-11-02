import { selectRows, summarize, groupRows, annualSeries } from './model.mjs';

const $ = selector => document.querySelector(selector);
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
const n = value => new Intl.NumberFormat('ko-KR').format(value);
const won = value => `${n(value)}원`;
const shortMoney = value => value >= 100000000
  ? `${(value / 100000000).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}억`
  : value >= 10000 ? `${(value / 10000).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}만` : n(value);
const percent = (part, total) => total ? (part / total * 100).toFixed(1) : '0.0';
const palette = ['#e6eddf', '#c6d9b6', '#91b77c', '#4f8c60', '#216347'];
const state = { view: 'overview', year: '', category: '', item: '', query: '', includePossible: false, region: '', metric: 'amount', page: 1, detail: null, detailPage: 1, townPage: 1 };
const pageSize = 12;
let data, map, period;
const tooltip = document.createElement('div');
tooltip.className = 'map-tooltip';
tooltip.setAttribute('role', 'tooltip');
document.body.append(tooltip);

function filtered(extra = {}) {
  return selectRows(data.rows, { year: state.year, category: state.category, item: state.item, query: state.query, includePossible: state.includePossible, ...extra });
}

function filtersDescription() {
  return [state.year ? `${state.year}년 계약` : '전체 계약한 해', state.category, state.item, state.query ? `검색 ‘${state.query}’` : ''].filter(Boolean).join(' · ');
}

function tag(category) {
  return `<span class="tag ${category === '설치' ? 'install' : category === '유지관리' ? 'maintenance' : ''}">${escape(category)}</span>`;
}

function attention() {
  return state.includePossible ? '<div class="attention-note">‘놓쳤을 수 있음’을 포함했습니다. 회수기가 아닌 계약도 섞여 있으므로 확정 수치로 사용하지 마세요.</div>' : '';
}

function empty(message = '조건에 맞는 계약이 없습니다.') {
  return `<div class="empty-state"><strong>${escape(message)}</strong>필터를 바꾸거나 초기화해 보세요.</div>`;
}

function replaceContent(root, html) {
  const active = document.activeElement;
  const inside = root.contains(active);
  const key = inside && ['id', 'data-metric', 'data-year', 'data-paging', 'data-region', 'data-town', 'data-vendor']
    .find(name => active.hasAttribute(name));
  const value = key ? active.getAttribute(key) : null;
  const label = active?.textContent;
  root.innerHTML = html;
  if (!inside) return;
  const replacement = key && [...root.querySelectorAll(`[${key}]`)].find(element =>
    element.getAttribute(key) === value && (key !== 'data-paging' || element.textContent === label));
  const target = replacement || root.querySelector('h2,h3');
  if (target) { if (!replacement) target.tabIndex = -1; target.focus({ preventScroll: true }); }
}

function summaryMetrics(rows) {
  const s = summarize(rows);
  return `<div class="scope-line"><span class="scope-label">전국에서 찾은 계약</span><span class="scope-period">${escape(filtersDescription())} · ${state.includePossible ? '추가 확인 대상 포함' : '이름 거르기에 걸린 계약'}</span></div>
  <div class="metrics" aria-label="현재 조건의 전국 요약">
    <div class="metric"><div class="metric-label">계약 건수</div><div class="metric-value"><strong class="number" data-summary="count">${n(s.count)}</strong><span>건</span></div><div class="metric-note">계약 한 줄을 한 건으로 계산</div></div>
    <div class="metric metric-amount"><div class="metric-label">계약금액 합계</div><div class="metric-value"><strong class="number" data-summary="amount">${n(Math.round(s.amount / 100000000 * 10) / 10)}</strong><span>억 원</span></div><div class="metric-note">${won(s.amount)} · 실제 지출액과 다를 수 있음</div></div>
    <div class="metric"><div class="metric-label">계약이 있는 지자체</div><div class="metric-value"><strong class="number" data-summary="municipalities">${n(s.municipalities)}</strong><span>곳</span></div><div class="metric-note">지자체 코드를 기준으로 중복 제외</div></div>
  </div><p class="confidence">원자료 합산 기준 [신뢰도 높음] · 회수기 계약 범위는 검토 중</p>`;
}

function annualChart(rows) {
  const series = annualSeries(rows);
  if (!series.length) return empty();
  const isAmount = state.metric === 'amount';
  const unit = isAmount ? 100000000 : 1;
  const maximum = Math.max(...series.flatMap(s => [s.install[state.metric], s.maintenance[state.metric]])) / unit;
  const rough = (maximum || 1) / 4;
  const power = 10 ** Math.floor(Math.log10(rough));
  const step = Math.max(isAmount ? 0.1 : 1, Math.ceil(rough / power) * power);
  const top = step * 4;
  const compact = window.matchMedia('(max-width: 480px)').matches;
  const width = compact ? 350 : 760, height = 230, left = compact ? 30 : 42, right = compact ? 4 : 15, plotTop = 20, plotHeight = 163;
  const plotWidth = width - left - right;
  const slot = plotWidth / series.length;
  const barWidth = Math.min(25, slot * .24);
  const grid = Array.from({ length: 5 }, (_, i) => {
    const y = plotTop + plotHeight - plotHeight * i / 4;
    return `<line class="chart-grid" x1="${left}" y1="${y}" x2="${width - right}" y2="${y}"/><text class="chart-label number" x="${left - 10}" y="${y + 4}" text-anchor="end">${n(Math.round(step * i * 10) / 10)}</text>`;
  }).join('');
  const bars = series.map((s, i) => {
    const center = left + slot * (i + .5);
    const installHeight = s.install[state.metric] / unit / top * plotHeight;
    const maintenanceHeight = s.maintenance[state.metric] / unit / top * plotHeight;
    const label = `${s.year}년 설치 ${won(s.install.amount)}, ${n(s.install.count)}건 · 유지관리 ${won(s.maintenance.amount)}, ${n(s.maintenance.count)}건`;
    const partial = s.year === period.endYear;
    return `<g role="button" tabindex="0" data-year="${escape(s.year)}" aria-label="${escape(label)}. 해당 계약한 해 선택"><title>${escape(label)}</title>
      <rect class="chart-hit" x="${center - slot / 2 + 4}" y="0" width="${slot - 8}" height="${height}" rx="5"/>
      <rect class="chart-bar-install" x="${center - barWidth - 3}" y="${plotTop + plotHeight - installHeight}" width="${barWidth}" height="${installHeight}" rx="3"/>
      <rect class="chart-bar-maintenance" x="${center + 3}" y="${plotTop + plotHeight - maintenanceHeight}" width="${barWidth}" height="${maintenanceHeight}" rx="3"/>
      <text class="chart-year number" x="${center}" y="204" text-anchor="middle">${escape(s.year)}</text>
      ${partial ? `<text x="${center}" y="221" text-anchor="middle" fill="#87652b" font-size="9">${period.endMonth}월까지</text>` : ''}
    </g>`;
  }).join('');
  return `<div class="chart-legend"><span class="muted">단위: ${isAmount ? '억 원' : '건'}</span><span class="legend-item"><i class="legend-swatch"></i>설치</span><span class="legend-item"><i class="legend-swatch maintenance"></i>유지관리</span></div>
    <svg class="chart" viewBox="0 0 ${width} ${height}" role="group" aria-label="계약한 해별 설치와 유지관리 ${isAmount ? '계약금액' : '계약 건수'} 비교">${grid}${bars}</svg>`;
}

function annualPanel(rows) {
  const categories = ['설치', '유지관리', '임차', '기타'].map(key => ({ key, ...summarize(rows.filter(r => r.갈래 === key)) }));
  return `<section class="panel annual-panel panel-inner" aria-labelledby="annual-title">
    <div class="panel-heading"><h2 id="annual-title">설치와 유지관리, 해마다 나란히</h2><div class="segmented" aria-label="차트 기준"><button type="button" data-metric="amount" class="${state.metric === 'amount' ? 'active' : ''}" aria-pressed="${state.metric === 'amount'}">금액</button><button type="button" data-metric="count" class="${state.metric === 'count' ? 'active' : ''}" aria-pressed="${state.metric === 'count'}">건수</button></div></div>
    <p class="panel-subtitle">계약한 해 기준입니다. 막대를 누르면 그 해의 계약만 볼 수 있어요.</p>
    <div class="chart-layout"><div class="chart-column">${annualChart(rows)}<p class="chart-note">유지관리는 전년도 말에 다음 해치를 계약하기도 합니다. 돈을 쓴 해와는 다릅니다.</p></div>
    <aside class="chart-breakdown"><p>갈래별 계약금액 <span class="muted">/ 현재 조건</span></p>${categories.map(c => `<div class="category-row"><span><i class="category-dot ${c.key === '설치' ? 'install' : c.key === '유지관리' ? 'maintenance' : ''}"></i>${c.key} <small class="muted number">${n(c.count)}건</small></span><strong class="number" title="${won(c.amount)}">${shortMoney(c.amount)} 원</strong></div>`).join('')}
    <div class="partial-note"><strong>${period.endYear}년은 ${period.endMonth}월까지</strong>자료가 덜 찼으므로 앞선 해와 단순 비교하지 마세요.</div></aside></div>
  </section>`;
}

function color(amount, maximum) {
  return maximum > 0 && amount > 0 ? palette[Math.min(palette.length - 1, Math.floor(Math.sqrt(amount / maximum) * (palette.length - 1)))] : '#eef1e9';
}

function mapGraphic(rows, region = '') {
  if (!map) return '<div class="empty-state">지도를 불러오지 못했습니다.<br>지역 목록에서 탐색할 수 있습니다.</div>';
  if (region && !map.regions[region]) return '<div class="empty-state">‘전남광주’는 원자료의 별도 지역 표기입니다.<br>지자체 목록에서 확인해 주세요.</div>';
  const groups = groupRows(rows, region ? '코드' : '시도');
  const amounts = new Map(groups.map(g => [g.key, g]));
  const maximum = Math.max(0, ...groups.map(g => g.amount));
  const shapes = region ? map.municipalities : map.regions;
  let entries = Object.entries(shapes);
  if (region) {
    const codes = new Set(data.rows.filter(r => r.시도 === region).map(r => r.코드));
    entries = entries.filter(([key]) => codes.has(key));
  }
  const box = region ? map.regions[region].box : map.overviewBox;
  const pad = 20;
  const viewBox = [box[0] - pad, box[1] - pad, box[2] + pad * 2, box[3] + pad * 2].join(' ');
  const paths = entries.map(([key, shape]) => {
    const group = amounts.get(key);
    const name = region ? data.rows.find(r => r.코드 === key)?.지자체 || key : key;
    const label = `${name} · ${n(group?.count || 0)}건 · ${won(group?.amount || 0)}${group ? '' : ' · 현재 조건에 계약 없음'}`;
    return `<path class="map-path" fill="${color(group?.amount || 0, maximum)}" fill-rule="evenodd" d="${escape(shape.d)}" role="button" tabindex="0" data-${region ? 'town' : 'region'}="${escape(key)}" data-tooltip="${escape(label)}" aria-label="${escape(label)}"><title>${escape(label)}</title></path>`;
  }).join('');
  const labels = !region ? Object.entries(map.regions).filter(([key]) => ['경기', '강원', '충북', '충남', '경북', '경남', '전북', '전남', '제주'].includes(key)).map(([key, shape]) => {
    const [x, y] = shape.label;
    return `<text class="map-label" x="${x}" y="${y}" text-anchor="middle">${escape(key)}</text>`;
  }).join('') : '';
  return `<svg class="map-svg" viewBox="${viewBox}" aria-label="${escape(region || '전국')} 지역별 계약금액 지도" role="group">${region ? `<path d="${escape(map.regions[region].d)}" fill="#eef1e9" stroke="#d6dfce" stroke-width="1" vector-effect="non-scaling-stroke"/>` : ''}${paths}${labels}</svg>`;
}

function mapScale() {
  return `<div class="map-scale">적음 <span class="scale-colors">${palette.map(c => `<i style="--c:${c}"></i>`).join('')}</span> 많음 <span>· 계약금액</span></div>`;
}

function mapCaption() {
  return `<p class="map-caption">경계: <a href="https://github.com/vuski/admdongkor" target="_blank" rel="noopener noreferrer">vuski/admdongkor</a> · CC BY 4.0 · 전국 지도는 본토·제주 중심(일부 도서 생략)<br>‘전남광주’는 목록에서 별도 집계합니다. 계약 없음은 설치 없음과 다릅니다.${map?.unmatched.length ? `<br>경계 미연결: ${map.unmatched.map(item => escape(item.name)).join(', ')}. 목록·합계에는 포함됩니다.` : ''}</p>`;
}

function regionPreview(rows) {
  const groups = groupRows(rows, '시도');
  return `<section class="panel panel-inner"><div class="panel-heading"><h2>어느 지역에서 계약했을까</h2><button type="button" class="text-link" data-view="regions">지역 전체 보기 ↗</button></div><p class="panel-subtitle">시도를 누르면 시군구별로 볼 수 있어요.</p>
    <div class="region-preview"><div><div class="map-wrap">${mapGraphic(rows)}</div>${mapScale()}</div><div class="mini-rank">${groups.slice(0, 7).map((g, i) => `<button type="button" class="mini-rank-row" data-region="${escape(g.key)}"><span class="rank-number number">${n(i + 1)}</span><span class="region-name">${escape(g.key)}<small>${n(g.municipalities)}곳 · ${n(g.count)}건</small></span><span class="rank-amount number">${shortMoney(g.amount)} 원</span></button>`).join('') || empty()}</div></div>${mapCaption()}</section>`;
}

function vendorPreview(rows) {
  const total = summarize(rows).amount;
  const groups = groupRows(rows, '업체묶음');
  return `<section class="panel panel-inner"><div class="panel-heading"><h2>어떤 업체와 계약했을까</h2><button type="button" class="text-link" data-view="vendors">업체 전체 보기 ↗</button></div><p class="panel-subtitle">업체를 누르면 계약한 지자체가 나옵니다.</p>
    <div class="vendor-preview-head"><span>업체묶음</span><span>계약금액</span><span>금액 몫</span></div>
    ${groups.slice(0, 6).map((g, i) => `<button type="button" class="vendor-row" data-vendor="${escape(g.key)}"><span class="rank-number number">${n(i + 1)}</span><span class="vendor-name">${escape(g.key)}<span class="vendor-mini-bar"><i style="width:${percent(g.amount, total)}%"></i></span></span><strong class="vendor-amount number">${shortMoney(g.amount)} 원</strong><span class="vendor-share number">${percent(g.amount, total)}%</span></button>`).join('') || empty()}
    <p class="vendor-footnote">몫은 현재 조건의 전체 계약금액 기준입니다.<br>업체묶음은 법인 표기·띄어쓰기를 정리한 이름으로, 계열사 묶음이 아닙니다.</p>
  </section>`;
}

function renderOverview(rows) {
  return `${summaryMetrics(rows)}${attention()}${annualPanel(rows)}<div class="explore-grid">${regionPreview(rows)}${vendorPreview(rows)}</div>`;
}

function pagination(count, page, kind = 'main') {
  const pages = Math.max(1, Math.ceil(count / pageSize));
  const unit = kind === 'towns' ? '곳' : kind === 'vendors' ? '개 업체묶음' : '건';
  return `<div class="pagination"><span>총 ${n(count)}${unit} ${count ? `중 ${n((page - 1) * pageSize + 1)}–${n(Math.min(page * pageSize, count))}${unit}` : ''}</span><div><button type="button" data-paging="${kind}" data-page="${page - 1}" ${page <= 1 ? 'disabled' : ''}>이전</button><span class="number">${n(page)} / ${n(pages)}</span><button type="button" data-paging="${kind}" data-page="${page + 1}" ${page >= pages ? 'disabled' : ''}>다음</button></div></div>`;
}

function townName(group) {
  return [...group.rows].sort((a, b) => b.날.localeCompare(a.날))[0]?.지자체 || group.key;
}

function townTable(rows, context = '', paginate = false) {
  const groups = groupRows(rows, '코드');
  const shown = paginate ? groups.slice((state.townPage - 1) * pageSize, state.townPage * pageSize) : groups;
  const total = summarize(rows).amount;
  return `<div class="table-scroll"><table class="data-table"><caption class="sr-only">${escape(context)} 지자체별 계약금액과 건수</caption><thead><tr><th>지자체</th><th class="numeric">계약금액</th><th class="numeric">건수</th><th class="numeric">금액 몫</th></tr></thead><tbody>${shown.map(g => `<tr><td><button type="button" class="table-link" data-town="${escape(g.key)}">${escape(townName(g))} ↗</button><span class="table-sub">${n(g.vendors)}개 업체묶음</span></td><td class="numeric number" title="${won(g.amount)}">${shortMoney(g.amount)} 원</td><td class="numeric number">${n(g.count)}</td><td class="numeric number">${percent(g.amount, total)}%</td></tr>`).join('')}</tbody></table></div>${groups.length ? '' : empty()}${paginate ? pagination(groups.length, state.townPage, 'towns') : ''}`;
}

function renderRegions(rows) {
  const region = state.region;
  const selected = region ? rows.filter(r => r.시도 === region) : rows;
  const s = summarize(selected);
  const regionKeys = [...new Set(data.rows.map(r => r.시도))].sort((a, b) => a.localeCompare(b, 'ko'));
  const groups = groupRows(rows, '시도');
  return `<div class="view-heading"><h2>지역에서 계약까지</h2><p>시도에서 시군구로 좁혀 보고, 지자체를 눌러 개별 계약을 확인하세요.</p></div>${attention()}
  <div class="breadcrumb"><button type="button" data-region="">전국</button>${region ? `<span>›</span><strong>${escape(region)}</strong>` : ''}<span>· ${escape(filtersDescription())}</span></div>
  <div class="regional-layout"><section class="panel panel-inner regional-map"><div class="panel-heading"><h3>${escape(region || '전국')} 계약 지도</h3><select class="region-select" id="region-select" aria-label="지도에서 볼 시도"><option value="">전국</option>${regionKeys.map(key => `<option value="${escape(key)}" ${key === region ? 'selected' : ''}>${escape(key)}</option>`).join('')}</select></div><p class="panel-subtitle">${region ? '지자체를 누르면 계약 목록이 열립니다.' : '색이 짙을수록 계약금액이 큽니다.'}</p><div class="map-wrap">${mapGraphic(selected, region)}</div>${mapScale()}${mapCaption()}</section>
  <section class="panel"><div class="table-toolbar"><div><h3>${escape(region || '시도별')} 계약</h3><p>${n(s.municipalities)}곳 · ${n(s.count)}건 · ${won(s.amount)}</p></div>${region ? '<button type="button" class="text-link" data-region="">전국으로 ↗</button>' : ''}</div>
  ${region ? townTable(selected, region, true) : `<div class="table-scroll"><table class="data-table"><caption class="sr-only">시도별 계약 목록</caption><thead><tr><th>시도</th><th class="numeric">계약금액</th><th class="numeric">계약 건수</th><th class="numeric">지자체</th></tr></thead><tbody>${groups.map(g => `<tr><td><button type="button" class="table-link" data-region="${escape(g.key)}">${escape(g.key)} ›</button></td><td class="numeric number" title="${won(g.amount)}">${shortMoney(g.amount)} 원</td><td class="numeric number">${n(g.count)}</td><td class="numeric number">${n(g.municipalities)}곳</td></tr>`).join('')}</tbody></table></div>${groups.length ? '' : empty()}`}</section></div>`;
}

function renderVendors(rows) {
  const groups = groupRows(rows, '업체묶음');
  const total = summarize(rows).amount;
  const shown = groups.slice((state.page - 1) * pageSize, state.page * pageSize);
  const leader = groups[0];
  return `<div class="view-heading"><h2>업체별 계약금액과 몫</h2><p>업체를 누르면 어느 지자체와 계약했는지 확인할 수 있습니다.</p></div>${attention()}
    <div class="vendor-layout"><section class="panel table-container"><div class="table-toolbar"><div><h3>업체묶음 <span class="section-tag">${n(groups.length)}곳</span></h3><p>계약금액순 · ${escape(filtersDescription())}</p></div></div>
    <div class="table-scroll"><table class="data-table"><caption class="sr-only">업체별 계약금액 및 전체 대비 비중</caption><thead><tr><th>순위</th><th>업체묶음</th><th class="numeric">계약금액</th><th>금액 몫</th><th class="numeric">지자체</th><th class="numeric">건수</th></tr></thead><tbody>${shown.map((g, i) => `<tr><td class="number muted">${n((state.page - 1) * pageSize + i + 1)}</td><td><button type="button" class="table-link" data-vendor="${escape(g.key)}">${escape(g.key)} ↗</button></td><td class="numeric number" title="${won(g.amount)}">${shortMoney(g.amount)} 원</td><td class="share-cell"><span class="number">${percent(g.amount, total)}%</span><span class="vendor-mini-bar"><i style="width:${percent(g.amount, total)}%"></i></span></td><td class="numeric number">${n(g.municipalities)}곳</td><td class="numeric number">${n(g.count)}</td></tr>`).join('')}</tbody></table></div>${groups.length ? '' : empty()}${pagination(groups.length, state.page, 'vendors')}</section>
    <aside class="panel vendor-insight"><h3>계약금액을 기준으로<br>계산한 몫입니다.</h3><p>현재 조건에서 가장 큰 금액을 계약한 업체묶음</p><div class="insight-value number">${percent(leader?.amount || 0, total)}<span>%</span></div><p><strong>${escape(leader?.key || '해당 없음')}</strong><br>${won(leader?.amount || 0)} / ${won(total)}</p><div class="vendor-tablesub">자료에 잡힌 계약의 금액 비중이며, 전체 회수기 시장점유율이 아닙니다.<br><br>업체묶음은 법인 표기와 띄어쓰기를 정리하고 ‘슈퍼빈’을 ‘수퍼빈’으로 맞춘 것입니다. 계열사나 실제 동일 법인 여부까지 검증한 묶음은 아닙니다.</div></aside></div>`;
}

function contractTable(rows, page = state.page, kind = 'main') {
  const sorted = [...rows].sort((a, b) => b.날.localeCompare(a.날) || b.금액 - a.금액);
  const shown = sorted.slice((page - 1) * pageSize, page * pageSize);
  return `<div class="table-scroll"><table class="data-table contracts-table"><caption class="sr-only">계약 원자료 목록 · 계약일 내림차순</caption><thead><tr><th>계약한 날</th><th>지자체 / 계약명</th><th>업체</th><th>갈래 / 품목</th><th class="numeric">계약금액(원)</th><th>방법 / 상태</th></tr></thead><tbody>${shown.map(r => `<tr><td class="date number">${escape(r.날)}<span class="table-sub">계약한 해 ${escape(r.해)}</span></td><td class="contract-title"><button type="button" class="table-link" data-town="${escape(r.코드)}">${escape(r.지자체)} ↗</button><div class="contract-name">${escape(r.계약명)}</div><span class="table-sub">지자체 코드 ${escape(r.코드)}</span></td><td>${escape(r.업체)}<span class="table-sub">묶음: <button type="button" class="table-link" data-vendor="${escape(r.업체묶음)}">${escape(r.업체묶음)}</button></span></td><td>${tag(r.갈래)}<span class="table-sub">${escape(r.품목)}</span></td><td class="numeric number">${n(r.금액)}</td><td>${escape(r.방법)}<span class="table-sub">${r.상태 === '놓쳤을 수 있음' ? '<span class="tag possible">놓쳤을 수 있음</span>' : '걸림'}</span></td></tr>`).join('')}</tbody></table></div>${rows.length ? '' : empty()}${pagination(rows.length, page, kind)}`;
}

function renderContracts(rows) {
  const regionRows = state.region ? rows.filter(r => r.시도 === state.region) : rows;
  const regions = [...new Set(data.rows.map(r => r.시도))].sort((a, b) => a.localeCompare(b, 'ko'));
  return `<div class="view-heading"><h2>계약 한 건씩 살펴보기</h2><p>표의 금액은 원 단위입니다. 계약명을 함께 읽고 회수기 계약인지 확인하세요.</p></div>${attention()}
  <section class="panel table-container"><div class="table-toolbar"><div><h3>${state.region ? escape(state.region) : '전국'} 계약 <span class="section-tag">${n(regionRows.length)}건</span></h3><p>계약한 날 최신순 · ${escape(filtersDescription())}</p></div><select id="contract-region" class="region-select" aria-label="계약 목록의 시도"><option value="">시도 전체</option>${regions.map(r => `<option value="${escape(r)}" ${r === state.region ? 'selected' : ''}>${escape(r)}</option>`).join('')}</select></div>${contractTable(regionRows)}</section>`;
}

function render() {
  const rows = filtered();
  replaceContent($('#app'), ({ overview: renderOverview, regions: renderRegions, vendors: renderVendors, contracts: renderContracts })[state.view](rows));
  document.querySelectorAll('.nav-tab').forEach(button => {
    const current = button.dataset.view === state.view;
    button.classList.toggle('active', current);
    if (current) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
  });
  $('#filter-description').textContent = state.includePossible
    ? `추가 확인 대상 ${n(summarize(rows).possible)}건 포함 · 회수기가 아닌 계약도 섞여 있습니다.`
    : '이름 거르기에 걸린 계약만 보고 있습니다.';
  tooltip.style.display = 'none';
}

function openDetail(type, key, vendor = '') {
  state.detail = { type, key, vendor };
  state.detailPage = 1;
  state.townPage = 1;
  renderDetail();
  if (!$('#detail-dialog').open) $('#detail-dialog').showModal();
  $('#detail-dialog').scrollTop = 0;
  $('#detail-title').tabIndex = -1;
  $('#detail-title').focus({ preventScroll: true });
}

function renderDetail() {
  const detail = state.detail;
  if (!detail) return;
  const rows = filtered(detail.type === 'vendor' ? { vendor: detail.key } : { municipality: detail.key, ...(detail.vendor ? { vendor: detail.vendor } : {}) });
  const s = summarize(rows);
  const name = detail.type === 'vendor' ? detail.key : data.rows.filter(r => r.코드 === detail.key).sort((a, b) => b.날.localeCompare(a.날))[0]?.지자체 || detail.key;
  $('#detail-eyebrow').textContent = detail.type === 'vendor' ? '업체묶음 → 계약한 지자체' : '지자체 → 개별 계약';
  replaceContent($('#dialog-content'), `<header class="detail-header"><h2 id="detail-title" tabindex="-1">${escape(name)}</h2><p>${escape(filtersDescription())} · ${state.includePossible ? '추가 확인 대상 포함' : '‘걸림’ 상태만 집계'}${detail.vendor ? ` · 업체묶음 ${escape(detail.vendor)}` : ''}</p></header>
    <div class="detail-metrics"><div>계약금액 합계<strong>${shortMoney(s.amount)} 원</strong></div><div>계약 건수<strong>${n(s.count)}건</strong></div><div>${detail.type === 'vendor' ? '계약한 지자체' : '계약한 업체묶음'}<strong>${n(detail.type === 'vendor' ? s.municipalities : s.vendors)}곳</strong></div></div>
    <p class="dialog-note">정확한 합계 ${won(s.amount)} · 계약한 해 기준 · ${period.endYear}년은 ${period.endMonth}월까지<br>원자료 합산 기준 [신뢰도 높음] · 회수기 계약 범위는 검토 중</p>
    ${detail.type === 'vendor' ? `<h3 class="dialog-section">어느 지자체와 계약했을까</h3><div class="dialog-town-table">${townTable(rows, detail.key, true)}</div><p class="dialog-note">금액 몫은 이 업체묶음의 현재 조건 계약금액 합계 기준입니다.</p>` : `${detail.vendor ? `<div class="dialog-context">${escape(detail.vendor)}와 맺은 계약만 보고 있습니다. <button type="button" class="table-link" data-town-all="${escape(detail.key)}">이 지자체의 모든 업체 계약 보기 ↗</button></div>` : ''}${contractTable(rows, state.detailPage, 'detail')}`}
    <p class="dialog-note">‘수의’ 표기에 조달청 구매가 섞여 있습니다. 계약방법만으로 수의계약 여부를 단정하지 마세요.</p>`);
}

function updateFilters() {
  state.year = $('#year').value;
  state.category = $('#category').value;
  state.item = $('#item').value;
  state.query = $('#query').value;
  state.includePossible = $('#include-possible').checked;
  state.page = 1;
  state.townPage = 1;
  render();
  if ($('#detail-dialog').open) renderDetail();
}

function navigate(view) {
  state.view = view;
  state.page = 1;
  state.townPage = 1;
  render();
}

document.addEventListener('click', event => {
  const target = event.target.closest('[data-view],[data-region],[data-town],[data-vendor],[data-metric],[data-year],[data-paging],[data-town-all]');
  if (!target || !data) return;
  if (target.hasAttribute('data-view')) navigate(target.dataset.view);
  else if (target.hasAttribute('data-region')) {
    state.region = target.dataset.region;
    navigate('regions');
  } else if (target.hasAttribute('data-town-all')) openDetail('town', target.dataset.townAll);
  else if (target.hasAttribute('data-town')) {
    const vendor = $('#detail-dialog').open && state.detail?.type === 'vendor' ? state.detail.key : '';
    openDetail('town', target.dataset.town, vendor);
  } else if (target.hasAttribute('data-vendor')) openDetail('vendor', target.dataset.vendor);
  else if (target.hasAttribute('data-metric')) { state.metric = target.dataset.metric; render(); }
  else if (target.hasAttribute('data-year')) {
    $('#year').value = target.dataset.year;
    updateFilters();
  } else if (target.hasAttribute('data-paging')) {
    const page = Number(target.dataset.page);
    if (target.dataset.paging === 'detail') { state.detailPage = page; renderDetail(); }
    else if (target.dataset.paging === 'towns') {
      state.townPage = page;
      if ($('#detail-dialog').open) renderDetail(); else render();
    } else { state.page = page; render(); }
  }
});

document.addEventListener('keydown', event => {
  const target = event.target.closest('svg [role="button"]');
  if (target && (event.key === 'Enter' || event.key === ' ')) {
    event.preventDefault(); target.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  }
});

document.addEventListener('pointerover', event => {
  const target = event.target.closest('[data-tooltip]');
  if (target) { tooltip.textContent = target.dataset.tooltip; tooltip.style.display = 'block'; }
});
document.addEventListener('pointermove', event => {
  if (tooltip.style.display === 'block') {
    tooltip.style.left = `${Math.max(8, Math.min(event.clientX + 14, window.innerWidth - 250))}px`;
    tooltip.style.top = `${Math.min(event.clientY + 15, window.innerHeight - tooltip.offsetHeight - 8)}px`;
  }
});
document.addEventListener('pointerout', event => { if (event.target.closest('[data-tooltip]')) tooltip.style.display = 'none'; });
document.addEventListener('change', event => {
  if (['year', 'category', 'item', 'include-possible'].includes(event.target.id)) updateFilters();
  if (['region-select', 'contract-region'].includes(event.target.id)) {
    state.region = event.target.value; state.page = 1; state.townPage = 1; render();
  }
});
let searchTimer;
$('#query').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(updateFilters, 160); });
$('#reset').addEventListener('click', () => {
  for (const id of ['year', 'category', 'item', 'query']) $(`#${id}`).value = '';
  $('#include-possible').checked = false;
  state.region = ''; state.metric = 'amount';
  updateFilters();
});
$('#close-dialog').addEventListener('click', () => $('#detail-dialog').close());
$('#detail-dialog').addEventListener('click', event => {
  if (event.target === $('#detail-dialog')) {
    const box = event.target.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) event.target.close();
  }
});
$('a[href="#reading-notes"]').addEventListener('click', () => { $('#reading-notes').open = true; });

async function load() {
  try {
    const response = await fetch('./data.json');
    if (!response.ok) throw new Error('data');
    data = await response.json();
    if (!Array.isArray(data.rows) || !data.rows.every(r => Number.isSafeInteger(r.금액) && r.금액 >= 0)) throw new Error('invalid data');
    const description = data.meta.설명;
    const dates = description.match(/(\d{4}-\d{2}-\d{2})~(\d{4}-\d{2}-\d{2})/);
    if (!dates) throw new Error('missing period');
    period = { start: dates[1], end: dates[2], endYear: dates[2].slice(0, 4), endMonth: Number(dates[2].slice(5, 7)) };
    try { const result = await fetch('./map.json'); if (result.ok) map = await result.json(); } catch { /* The regional table remains available without map assets. */ }
    const years = [...new Set(data.rows.map(r => r.해))].sort();
    $('#period').textContent = `${years[0]}–${years.at(-1)} · ${period.endYear}년 ${period.endMonth}월까지`;
    for (const [id, key] of [['year', '해'], ['category', '갈래'], ['item', '품목']]) {
      const values = [...new Set(data.rows.map(r => r[key]))];
      if (id === 'year') values.sort();
      $(`#${id}`).innerHTML = `<option value="">전체</option>${values.map(value => `<option value="${escape(value)}">${escape(value)}${id === 'year' ? '년' : ''}</option>`).join('')}`;
    }
    $('#possible-count').textContent = `(${n(data.rows.filter(r => r.상태 === '놓쳤을 수 있음').length)}건)`;
    $('#notes-content').innerHTML = `<p>${escape(description)}</p><ul>${data.meta.주의.map(note => `<li>${escape(note)}</li>`).join('')}<li>‘걸림’은 계약명으로 찾았다는 뜻이며, 검증을 마쳤다는 뜻이 아닙니다. 건수는 계약 수이며 회수기 대수가 아닙니다.</li><li>모든 금액·건수·몫은 현재 조건에 포함되는 원자료 행에서 계산합니다. 업체 묶음의 몫은 시장점유율이 아닙니다.</li><li>지자체는 코드로 중복을 제거합니다. 지도에 연결되지 않는 지역도 목록과 합계에는 포함합니다. ‘전남광주’는 원자료 표기를 보존해 별도 집계합니다.</li><li>경계 기준: ${map ? escape(map.source) : '지도 파일을 읽지 못했습니다.'}.</li></ul><p class="source-note">출처: 지방재정365 계약현황(WCEGCF), 수록 기간 ${escape(period.start)}~${escape(period.end)}.<br>원자료 합산의 정확성과 회수기 계약 분류의 확실성은 별개입니다. 숫자는 확정 전입니다. [신뢰도 보통]</p>`;
    render();
    $('#load-status').hidden = true;
    $('#app').hidden = false;
  } catch {
    $('#load-status').className = 'load-state error';
    $('#load-status').innerHTML = '자료를 불러오지 못했습니다. 로컬 미리보기 서버에서 열었는지 확인해 주세요.<button type="button" id="retry">다시 불러오기 ↻</button>';
    $('#retry').addEventListener('click', () => location.reload());
  }
}

load();
window.matchMedia('(max-width: 480px)').addEventListener('change', () => { if (data && period) render(); });
