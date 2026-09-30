/* 살림을 보는 시민 — 그래프 몇 가지. 라이브러리 없이 SVG·HTML 로 그린다.
 *
 * 쓰는 곳: dashboard.html(한눈에) · index.html(자치단체별 결산·예산·세입 판).
 * 그리는 법: 화면 글 안에 자리만 두고(Chart.자리(무엇, 설정) → <div class="ch">), 글을 넣은 뒤
 *   Chart.그리기(뿌리) 를 부른다. 폭을 재서 그리고, 창 폭이 바뀌면 다시 그린다.
 *
 * 색은 CSS 변수로만 쓴다(--c1 초록 · --c2 주황 · --faint 회색). 다크 모드는 변수가 갈아 준다.
 *   두 색 짝은 dataviz 검증기로 밝은·어두운 판 모두 통과한 것이다(2026-09-30):
 *   밝은 #1f7a4a / #e0661f, 어두운 #3aa36b / #e0702e. 바꾸면 다시 돌릴 것.
 * 원칙: 고른 곳 하나만 색, 나머지는 회색(강조). 값 글자는 색을 입히지 않는다. 그래프마다 표가 곁에 있다.
 */
(() => {
const NS = 'http://www.w3.org/2000/svg';
const 자리들 = new Map();
let 번호 = 0;

const esc = t => String(t ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const n0 = v => v == null ? '' : Math.round(v).toLocaleString('ko-KR');
function 돈(v){
  if (v == null) return '';
  const a = Math.abs(v);
  if (a >= 1e12) return (v/1e12).toLocaleString('ko-KR',{maximumFractionDigits:2}) + '조';
  if (a >= 1e8)  return (v/1e8 ).toLocaleString('ko-KR',{maximumFractionDigits:0}) + '억';
  if (a >= 1e4)  return (v/1e4 ).toLocaleString('ko-KR',{maximumFractionDigits:0}) + '만';
  return n0(v);
}
/* 지표 값 글자 — 단위를 보고 고른다. 1 밑의 비율은 소수 셋째 자리까지(국외여비 0.02% 따위) */
function 값글(v, 단위){
  if (v == null) return '—';
  if (단위 === '원') return 돈(v) + '원';
  if (단위 === '천원') return n0(v) + '천원';
  if (단위 === '1인당원') return n0(v) + '원';
  if (단위 === '%') return (Math.abs(v) > 0 && Math.abs(v) < 1 ? v.toFixed(3) : v.toLocaleString('ko-KR', {maximumFractionDigits: 1})) + '%';
  return v.toLocaleString('ko-KR') + (단위 || '');
}

/* ── 말풍선 — 하나를 돌려 쓴다. 마우스·키보드 둘 다 ── */
let tip;
function 말풍선(html, x, y){
  if (!tip) { tip = document.createElement('div'); tip.className = 'ch-tip'; tip.setAttribute('role', 'status'); document.body.appendChild(tip); }
  if (html == null) { tip.hidden = true; return; }
  tip.innerHTML = html; tip.hidden = false;
  const r = tip.getBoundingClientRect();
  let L = x + 14, T = y + 14;
  if (L + r.width > innerWidth - 8) L = x - r.width - 14;
  if (T + r.height > innerHeight - 8) T = y - r.height - 14;
  tip.style.left = Math.max(8, L) + 'px'; tip.style.top = Math.max(8, T) + 'px';
}
addEventListener('scroll', () => 말풍선(null), {passive: true});

function svg(w, h, 속, 이름){
  return `<svg xmlns="${NS}" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(이름 || '')}">${속}</svg>`;
}
/* 깔끔한 눈금 — 0 부터 최댓값 위까지 네댓 칸 */
function 눈금(최대, 칸 = 4){
  if (!(최대 > 0)) return [0, 1];
  const 거친 = 최대 / 칸, 자릿 = 10 ** Math.floor(Math.log10(거친));
  const 걸음 = [1, 2, 2.5, 5, 10].map(k => k * 자릿).find(s => s >= 거친);
  const 끝 = Math.ceil(최대 / 걸음) * 걸음;
  const out = []; for (let v = 0; v <= 끝 + 걸음 / 2; v += 걸음) out.push(v);
  return out;
}
/* 위가 둥근 막대(4px), 바닥은 각지게 */
function 기둥길(x, y, w, h){
  const r = Math.min(4, w / 2, h);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}

/* ════════ 점띠 — 같은 갈래 곳들 사이에서 이 곳이 어디쯤인가 ════════
   설정: {값:[{cd,이름,v}], 나:cd, 단위, 로그:bool, 나쁨:bool, 누르면:fn(cd)}
   회색 점 하나가 한 곳. 세로 흔들림은 겹침을 피하려는 것일 뿐 뜻이 없다. 세로 금은 가운데값. */
function 점띠(el, o){
  const W = Math.max(260, el.clientWidth), H = 58, 좌 = 8, 우 = 8, 가운데y = 26;
  const vs = o.값.filter(x => x.v != null && (!o.로그 || x.v > 0));
  if (!vs.length) { el.innerHTML = '<p class="ch-none">견줄 값이 없다</p>'; return; }
  const 값만 = vs.map(x => x.v).sort((a, b) => a - b);
  let lo = 값만[0], hi = 값만[값만.length - 1];
  if (!o.로그 && lo > 0 && lo < hi * 0.35) lo = 0;          // 0 가까이 몰린 것은 0 부터
  const f = o.로그 ? Math.log10 : (v => v);
  const [a, b] = [f(lo), f(hi)];
  const X = v => 좌 + (b === a ? 0.5 : (f(v) - a) / (b - a)) * (W - 좌 - 우);
  const 중 = 값만.length % 2 ? 값만[(값만.length - 1) / 2] : (값만[값만.length / 2 - 1] + 값만[값만.length / 2]) / 2;
  /* 겹침 피하기 — 같은 자리(3px 안)에 먼저 온 점이 있으면 위아래로 번갈아 비킨다 */
  const 칸 = new Map();
  const 점 = vs.map(x => {
    const px = X(x.v), k = Math.round(px / 3), n = 칸.get(k) || 0; 칸.set(k, n + 1);
    const dy = n === 0 ? 0 : (n % 2 ? 1 : -1) * Math.ceil(n / 2) * 4.2;
    return {...x, px, py: 가운데y + Math.max(-15, Math.min(15, dy))};
  });
  const 나 = 점.find(x => x.cd === o.나);
  const 속 = [
    `<line x1="${좌}" x2="${W - 우}" y1="${가운데y}" y2="${가운데y}" class="ch-axis"/>`,
    `<line x1="${X(중)}" x2="${X(중)}" y1="6" y2="${가운데y + 18}" class="ch-mid"/>`,
    ...점.filter(x => x !== 나).map(x => `<circle cx="${x.px.toFixed(1)}" cy="${x.py.toFixed(1)}" r="3.4" class="ch-peer"/>`),
    나 ? `<circle cx="${나.px}" cy="${가운데y}" r="7" class="ch-me"/>` : '',
    `<text x="${좌}" y="${H - 2}" class="ch-tick">${esc(값글(lo, o.단위))}</text>`,
    `<text x="${W - 우}" y="${H - 2}" class="ch-tick" text-anchor="end">${esc(값글(hi, o.단위))}</text>`,
    `<text x="${X(중)}" y="${H - 2}" class="ch-tick" text-anchor="middle">가운데 ${esc(값글(중, o.단위))}</text>`,
  ].join('');
  el.innerHTML = svg(W, H, 속, o.제목);
  el.classList.toggle('ch-emph', !!나);
  /* 가운데 글자가 양 끝 글자와 겹치면 뺀다(끝값은 남긴다) */
  const t = el.querySelectorAll('.ch-tick');
  const [L, R, M] = [...t].map(x => x.getBBox());
  if (M && (M.x < L.x + L.width + 6 || M.x + M.width > R.x - 6)) t[2].remove();
  const s = el.querySelector('svg');
  const 가까운 = e => {
    const r = s.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
    let best = null, bd = 1e9;
    for (const p of 점) { const d = (p.px - mx) ** 2 + (p.py - my) ** 2 * 0.3; if (d < bd) { bd = d; best = p; } }
    return bd < 900 ? best : null;
  };
  let 켜진 = null;
  s.addEventListener('mousemove', e => {
    const p = 가까운(e);
    if (p !== 켜진) {
      s.querySelector('.ch-hot')?.remove();
      if (p) s.insertAdjacentHTML('beforeend', `<circle cx="${p.px}" cy="${p.py}" r="6" class="ch-hot"/>`);
      켜진 = p;
    }
    말풍선(p ? `<b>${esc(p.이름)}</b> ${esc(값글(p.v, o.단위))}${p.꼬리 ? `<br><small>${esc(p.꼬리)}</small>` : ''}${o.누르면 ? '<br><small>누르면 이 곳으로</small>' : ''}` : null, e.clientX, e.clientY);
    s.style.cursor = p && o.누르면 ? 'pointer' : '';
  });
  s.addEventListener('mouseleave', () => { s.querySelector('.ch-hot')?.remove(); 켜진 = null; 말풍선(null); });
  if (o.누르면) s.addEventListener('click', e => { const p = 가까운(e); if (p) o.누르면(p.cd); });
}

/* ════════ 선 — 해마다 (계열 1~2개) ════════
   설정: {해:[...], 계열:[{이름, 값:[...], 색:1|2}], 단위, 제목} */
function 선(el, o){
  const W = Math.max(280, el.clientWidth), H = o.높이 || 220;
  const 좌 = 54, 위 = 14, 아래 = 26;
  const 이름폭 = Math.min(150, Math.max(...o.계열.map(s => s.이름.length)) * 13 + 70);
  const 우 = W < 480 ? 12 : 이름폭;
  /* 선은 막대와 달리 0 에서 시작하지 않아도 된다 — 값이 사는 범위에 눈금을 맞춰 흐름이 보이게 */
  const 모든 = o.계열.flatMap(s => s.값).filter(v => v != null);
  const 위끝 = Math.max(...모든, 0), 아래끝 = Math.min(...모든, 위끝);
  const 폭 = (위끝 - 아래끝) || 위끝 || 1;
  const 걸 = 눈금(폭 * 1.25)[1];
  const 시작 = Math.max(0, Math.floor((아래끝 - 폭 * 0.15) / 걸) * 걸);
  const tk = []; for (let v = 시작; v <= 위끝 + 걸 * 0.999; v += 걸) tk.push(v);
  if (tk[tk.length - 1] < 위끝) tk.push(tk[tk.length - 1] + 걸);
  const 처음 = tk[0], 끝 = tk[tk.length - 1];
  const X = i => 좌 + (o.해.length === 1 ? 0.5 : i / (o.해.length - 1)) * (W - 좌 - 우);
  const Y = v => 위 + (1 - (v - 처음) / (끝 - 처음 || 1)) * (H - 위 - 아래);
  const 줄 = o.계열.map(s => {
    const 점 = s.값.map((v, i) => v == null ? null : [X(i), Y(v)]);
    const d = 점.reduce((acc, p, i) => p ? acc + (acc && 점[i - 1] ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1) : acc, '');
    const 마지막 = 점.map((p, i) => p && i).filter(i => i !== false && i != null).pop();
    return {s, 점, d, 마지막};
  });
  const 속 = [
    ...tk.map(v => `<line x1="${좌}" x2="${W - 우}" y1="${Y(v)}" y2="${Y(v)}" class="ch-grid"/>
      <text x="${좌 - 8}" y="${Y(v) + 4}" class="ch-tick" text-anchor="end">${esc(값글(v, o.단위))}</text>`),
    ...o.해.map((h, i) => `<text x="${X(i)}" y="${H - 6}" class="ch-tick" text-anchor="middle">${esc(h)}</text>`),
    ...줄.map(({s, d}) => `<path d="${d}" class="ch-line c${s.색 || 1}"/>`),
    ...줄.map(({s, 점, 마지막}) => 마지막 == null ? '' : `<circle cx="${점[마지막][0]}" cy="${점[마지막][1]}" r="4.5" class="ch-dot c${s.색 || 1}"/>`),
  ];
  /* 끝 이름표 — 둘이 14px 안으로 붙으면 달지 않고 위 범례에 맡긴다 */
  const 끝y = 줄.map(({점, 마지막}) => 마지막 == null ? null : 점[마지막][1]);
  const 붙음 = 끝y.length === 2 && 끝y[0] != null && 끝y[1] != null && Math.abs(끝y[0] - 끝y[1]) < 30;
  if (W >= 480 && !붙음) 줄.forEach(({s, 점, 마지막}) => { if (마지막 != null)
    속.push(`<text x="${점[마지막][0] + 10}" y="${점[마지막][1] - 2}" class="ch-lab">${esc(s.이름)}</text>
      <text x="${점[마지막][0] + 10}" y="${점[마지막][1] + 13}" class="ch-tick">${esc(값글(s.값[마지막], o.단위))}</text>`); });
  const 범례 = o.계열.length > 1 ? `<div class="ch-legend">${o.계열.map(s => `<span><i class="c${s.색 || 1}"></i>${esc(s.이름)}</span>`).join('')}</div>` : '';
  el.innerHTML = 범례 + svg(W, H, 속.join(''), o.제목);
  const s = el.querySelector('svg');
  s.addEventListener('mousemove', e => {
    const r = s.getBoundingClientRect(), mx = e.clientX - r.left;
    let i = Math.round((mx - 좌) / ((W - 좌 - 우) / Math.max(1, o.해.length - 1)));
    i = Math.max(0, Math.min(o.해.length - 1, i));
    s.querySelector('.ch-cross')?.remove();
    s.insertAdjacentHTML('afterbegin', `<line x1="${X(i)}" x2="${X(i)}" y1="${위}" y2="${H - 아래}" class="ch-cross"/>`);
    말풍선(`<b>${esc(o.해[i])}</b>` + o.계열.map(x => `<br><i class="ch-key c${x.색 || 1}"></i>${esc(x.이름)} ${esc(값글(x.값[i], o.단위))}`).join(''), e.clientX, e.clientY);
  });
  s.addEventListener('mouseleave', () => { s.querySelector('.ch-cross')?.remove(); 말풍선(null); });
}

/* ════════ 기둥 — 해마다 한 값 ════════
   설정: {칸:[{x, v, 꼬리}], 단위, 제목} — 마지막 칸과 가장 큰 칸에만 값을 적는다 */
function 기둥(el, o){
  const W = Math.max(260, el.clientWidth), H = o.높이 || 190, 좌 = 54, 우 = 8, 위 = 22, 아래 = 26;
  const vs = o.칸.map(c => c.v ?? 0);
  const tk = 눈금(Math.max(...vs, 0)), 끝 = tk[tk.length - 1] || 1;
  const 띠 = (W - 좌 - 우) / o.칸.length, bw = Math.min(24, 띠 * 0.6);
  const Y = v => 위 + (1 - v / 끝) * (H - 위 - 아래);
  const 최대 = vs.indexOf(Math.max(...vs));
  const 속 = [
    ...tk.map(v => `<line x1="${좌}" x2="${W - 우}" y1="${Y(v)}" y2="${Y(v)}" class="ch-grid"/>
      <text x="${좌 - 8}" y="${Y(v) + 4}" class="ch-tick" text-anchor="end">${esc(값글(v, o.단위))}</text>`),
    ...o.칸.map((c, i) => {
      const x = 좌 + 띠 * i + (띠 - bw) / 2, v = c.v ?? 0, h = Math.max(0, Y(0) - Y(v));
      const 적기 = (i === o.칸.length - 1 || i === 최대) && c.v != null;
      return `<path d="${기둥길(x, Y(v), bw, h)}" class="ch-col${i === o.칸.length - 1 ? ' last' : ''}"/>
        ${적기 ? `<text x="${x + bw / 2}" y="${Y(v) - 6}" class="ch-lab" text-anchor="middle">${esc(값글(c.v, o.단위))}</text>` : ''}
        <text x="${x + bw / 2}" y="${H - 6}" class="ch-tick" text-anchor="middle">${esc(c.x)}</text>`;
    }),
  ];
  el.innerHTML = svg(W, H, 속.join(''), o.제목);
  const s = el.querySelector('svg');
  s.addEventListener('mousemove', e => {
    const r = s.getBoundingClientRect(), i = Math.floor((e.clientX - r.left - 좌) / 띠);
    const c = o.칸[i];
    말풍선(c ? `<b>${esc(c.x)}</b> ${esc(값글(c.v, o.단위))}${c.꼬리 ? `<br><small>${esc(c.꼬리)}</small>` : ''}` : null, e.clientX, e.clientY);
  });
  s.addEventListener('mouseleave', () => 말풍선(null));
}

/* ════════ 막대 줄 — 줄 세우기 (HTML) ════════
   설정: {줄:[{cd, 이름, v, 꼬리, 강조}], 단위, 누르면} — 값은 막대 끝에. 0 이 바닥이다 */
function 막대(el, o){
  const 최대 = Math.max(...o.줄.map(r => Math.abs(r.v ?? 0)), 0) || 1;
  // 강조할 곳이 없으면 한 계열이다 — 모두 초록. 있으면 그 곳만 초록, 나머지 회색
  el.innerHTML = `<ol class="ch-bars${o.줄.some(r => r.강조) ? ' emph' : ''}">${o.줄.map(r => `<li class="${r.강조 ? 'hot' : ''}"${o.누르면 && r.cd ? ` data-cd="${esc(r.cd)}" tabindex="0"` : ''}>
    <span class="nm">${r.순 != null ? `<small>${r.순}</small>` : ''}${esc(r.이름)}</span>
    <span class="tr"><i style="width:${(Math.abs(r.v ?? 0) / 최대 * 100).toFixed(2)}%"></i></span>
    <span class="v">${esc(값글(r.v, o.단위))}${r.꼬리 ? `<small>${esc(r.꼬리)}</small>` : ''}</span></li>`).join('')}</ol>`;
  if (o.누르면) {
    const 가기 = e => { const li = e.target.closest('li[data-cd]'); if (li) o.누르면(li.dataset.cd); };
    el.onclick = 가기;
    el.onkeydown = e => { if (e.key === 'Enter') 가기(e); };
  }
}

/* ════════ 쌓은 띠 — 몫 나누기 (HTML) ════════
   설정: {칸:[{이름, 몫, 금액}], 색:{이름: n}} — 색은 정해진 차례로만(순위로 칠하지 않는다) */
function 쌓기(el, o){
  const 칸 = o.칸.filter(x => x.몫 > 0);
  el.innerHTML = `<div class="ch-stack">${칸.map(x => `<span class="k${o.색[x.이름] ?? 0}" style="flex:${x.몫}"
      data-t="${esc(x.이름)} ${x.몫}%${x.금액 != null ? ' · ' + 돈(x.금액) + '원' : ''}">${x.몫 >= 9 ? `<em>${Math.round(x.몫)}%</em>` : ''}</span>`).join('')}</div>
    <div class="ch-legend">${칸.map(x => `<span><i class="k${o.색[x.이름] ?? 0}"></i>${esc(x.이름)} ${x.몫}%</span>`).join('')}</div>`;
  el.querySelectorAll('[data-t]').forEach(s => {
    s.onmousemove = e => 말풍선(esc(s.dataset.t), e.clientX, e.clientY);
    s.onmouseleave = () => 말풍선(null);
  });
}

const 그림 = {점띠, 선, 기둥, 막대, 쌓기};

/* 그래프 모양 — 두 화면이 같이 쓰므로 여기 한 곳에 둔다.
   k1~k7 은 dataviz 기준 팔레트의 정해진 차례(밝은/어두운 판 따로 검증된 것) — 세입 재원 띠에 쓴다 */
const 옷 = document.createElement('style');
옷.textContent = `
:root{--c1:#1f7a4a;--c2:#e0661f;--peer:#8a978f;
  --k1:#2a78d6;--k2:#eb6834;--k3:#1baf7a;--k4:#eda100;--k5:#e87ba4;--k6:#008300;--k7:#4a3aa7;--k0:#9a9a92}
@media(prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){--c1:#3aa36b;--c2:#e0702e;--peer:#7d8c82;
  --k1:#3987e5;--k2:#d95926;--k3:#199e70;--k4:#c98500;--k5:#d55181;--k6:#008300;--k7:#9085e9;--k0:#6f786f}}
:root[data-theme="dark"]{--c1:#3aa36b;--c2:#e0702e;--peer:#7d8c82;
  --k1:#3987e5;--k2:#d95926;--k3:#199e70;--k4:#c98500;--k5:#d55181;--k6:#008300;--k7:#9085e9;--k0:#6f786f}
.ch{width:100%;min-width:0;position:relative}.ch svg{display:block;overflow:visible;max-width:100%}
.ch-axis,.ch-grid{stroke:var(--line-soft);stroke-width:1}.ch-axis{stroke:var(--line)}
.ch-mid{stroke:var(--muted);stroke-width:1}.ch-cross{stroke:var(--line);stroke-width:1}
.ch-tick{font:11px var(--body);fill:var(--muted);font-variant-numeric:tabular-nums}
.ch-lab{font:700 12px var(--body);fill:var(--ink)}
.ch-peer{fill:var(--c1);opacity:.55}.ch-emph .ch-peer{fill:var(--peer);opacity:.6}
.ch-me{fill:var(--c1);stroke:var(--paper,#fff);stroke-width:2}
.ch-hot{fill:none;stroke:var(--ink);stroke-width:1.5}
.ch-line{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.ch-line.c1{stroke:var(--c1)}.ch-line.c2{stroke:var(--c2)}
.ch-dot{stroke:var(--paper,#fff);stroke-width:2}.ch-dot.c1{fill:var(--c1)}.ch-dot.c2{fill:var(--c2)}
.ch-col{fill:var(--peer);opacity:.75}.ch-col.last{fill:var(--c1);opacity:1}
.ch-legend{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:12px;color:var(--muted);margin:6px 0}
.ch-legend i,.ch-key{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:-1px}
.ch-legend i.c1,.ch-key.c1{background:var(--c1)}.ch-legend i.c2,.ch-key.c2{background:var(--c2)}
${[0,1,2,3,4,5,6,7].map(k => `.k${k}{background:var(--k${k})}`).join('')}
.ch-stack{display:flex;gap:2px;height:30px;margin:12px 0 4px}
.ch-stack span{min-width:2px;display:flex;align-items:center;justify-content:center}
.ch-stack span:first-child{border-radius:4px 0 0 4px}.ch-stack span:last-child{border-radius:0 4px 4px 0}
.ch-stack em{font:700 11px var(--body);font-style:normal;color:#fff;text-shadow:0 0 3px rgba(0,0,0,.45)}
.ch-bars{list-style:none;margin:8px 0;padding:0}
.ch-bars li{display:grid;grid-template-columns:minmax(96px,170px) minmax(0,1fr) minmax(88px,auto);gap:12px;align-items:center;padding:3px 4px;border-radius:3px}
.ch-bars li[data-cd]{cursor:pointer}.ch-bars li[data-cd]:hover,.ch-bars li:focus-visible{background:var(--green-bg)}
.ch-bars .nm{font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ch-bars .nm small{display:inline-block;min-width:26px;color:var(--muted);font:11px var(--mono)}
.ch-bars .tr{height:14px;display:block}
.ch-bars .tr i{display:block;height:100%;background:var(--c1);border-radius:0 4px 4px 0;min-width:1px}
.ch-bars.emph .tr i{background:var(--peer);opacity:.6}
.ch-bars li.hot .tr i{background:var(--c1);opacity:1}.ch-bars li.hot .nm{font-weight:800}
.ch-bars .v{font-size:12.5px;font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.ch-bars .v small{display:block;font-size:11px;color:var(--muted)}
.ch-none{font-size:12px;color:var(--muted);margin:6px 0}
.ch-axisbox{margin:6px 0 26px}.ch-axisbox h3{font-size:15px;margin:22px 0 4px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.ch-axisbox h3 small{font-weight:400;color:var(--muted);font-size:12px;margin-left:8px}
.ch-row{display:grid;grid-template-columns:minmax(170px,250px) minmax(0,1fr);gap:18px;align-items:center;padding:6px 0;border-bottom:1px solid var(--line-soft)}
.ch-row .nm{font-size:13.5px;line-height:1.45}.ch-row .nm button{all:unset;cursor:pointer;font-weight:700;color:var(--ink);text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:4px}
.ch-row .nm button:hover{color:var(--accent)}.ch-row .nm small{display:block;color:var(--muted);font-size:11.5px}
.ch-row .nm .me{display:block;font-size:12.5px;color:var(--ink)}.ch-row .nm .me b{font-size:15px}
.ch-row .nm b.big{display:block;font-size:17px;line-height:1.35}
.ch-fold{margin:10px 0 0}.ch-fold summary{cursor:pointer;font-size:12.5px;color:var(--muted);padding:6px 0}.ch-fold summary:hover{color:var(--accent)}
@media(max-width:700px){.ch-row{grid-template-columns:1fr;gap:2px}}
.ch-tip{position:fixed;z-index:200;pointer-events:none;background:var(--paper,#fff);color:var(--ink);border:1px solid var(--line);
  box-shadow:0 4px 16px rgba(0,0,0,.14);padding:7px 10px;font-size:12.5px;line-height:1.55;border-radius:4px;max-width:280px}
.ch-tip small{color:var(--muted)}
@media(max-width:600px){.ch-bars li{grid-template-columns:minmax(80px,112px) minmax(0,1fr) auto;gap:8px}}
`;
document.head.appendChild(옷);

/* 자리 두기 — 글 속에 넣을 <div>. 설정은 여기 맡겨 두고 그리기 때 꺼낸다 */
function 자리(무엇, 설정, 높이 = ''){
  const id = 'ch' + (++번호);
  자리들.set(id, [무엇, 설정]);
  return `<div class="ch ch-${무엇}" data-ch="${id}"${높이 ? ` style="min-height:${높이}px"` : ''}></div>`;
}
function 그리기(뿌리 = document){
  // 화면에서 사라진 자리의 설정은 버린다
  for (const id of 자리들.keys()) if (!document.querySelector(`[data-ch="${id}"]`)) 자리들.delete(id);
  뿌리.querySelectorAll('.ch[data-ch]').forEach(el => {
    const [무엇, 설정] = 자리들.get(el.dataset.ch) || [];
    if (무엇) 그림[무엇](el, 설정);
  });
}
/* 폭이 바뀌면 다시 — 글자 크기가 폭에 안 끌려가게 viewBox 를 늘리지 않고 새로 그린다 */
let 늦춤, 옛폭 = innerWidth;
addEventListener('resize', () => { clearTimeout(늦춤); 늦춤 = setTimeout(() => { if (innerWidth !== 옛폭) { 옛폭 = innerWidth; 그리기(); } }, 150); });

/* 시도 차례 — 행정구역 순서(가나다 아님). 시도를 늘어놓는 칸은 모두 이 차례를 쓴다 */
const 시도순 = ['서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종', '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주'];
const 시도차례 = 목록 => [...new Set(목록)].sort((a, b) => (시도순.indexOf(a) + 99) % 99 - (시도순.indexOf(b) + 99) % 99 || a.localeCompare(b));

window.Chart = {자리, 그리기, 값글, 돈, esc, 시도순, 시도차례};
})();
