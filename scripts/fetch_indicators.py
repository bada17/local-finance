# 화면에 쓸 지표 묶음을 받아 한 파일로 묶는다.
#
#   python scripts/fetch_indicators.py 2024 2026     (결산연도, 예산연도)
#
# 전부 243곳 전수로 오는 것들이라 인증키가 있으면 한 종에 한 번 호출이면 끝난다.
# 결산 시즌에 한 번, 예산 확정 뒤에 한 번 돌리면 되는 성격의 수집이다.
#
# ⚠️ 기준이 다른 것을 섞지 말 것. 세 가지가 있다.
#    결산 — 확정된 실적. 2024 가 최신(2025 결산은 아직 안 올라옴)
#    예산[당초] — 그 해 처음 짠 예산. 2026 까지 있다
#    예산[최종] — 추경까지 반영된 예산. 추경이 끝나야 나오므로 한 해 늦다(2025)
#    ★ 당초와 최종의 차이가 곧 추경이다. 전국 중앙값이 +13.7%,
#      최대 +49.7% 라서 당초만 보면 살림의 8분의 1을 놓친다.
#    구분이 아예 없는 비중 지표들은 '예산' 으로 적었다 — API 가 시점을 말해 주지 않는다.
#
# ⚠️ 비율만 뽑지 말 것. 분자·분모 금액이 **같은 응답에 이미 들어 있다.**
#    "행사축제경비 1.2%" 만 보여주면 그게 몇 억인지 모른다. 호출 수는 똑같다.
#
# 결과: data/indicators/<결산연도>-<예산연도>.json

import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lofin import fetch, load_key  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 코드, 이름, 축, 단위, 기준, {비율 / 금액(분자) / 분모} 가 응답의 어느 칸인지
BUNDLE = [
    # ① 규모
    ('AJGCF', '세출결산 총액', '규모', '원', '결산',
     {'금액': 'tot_pfa_amt', '일반회계': 'pfa_amt1'}),
    ('IIBBH', '세입결산 총액', '규모', '원', '결산',
     {'금액': 'total', '일반회계': 'pfa_amt1'}),
    ('ACEXBG', '세출예산 총액', '규모', '원', '예산',
     {'금액': 'ane_tott_amt', '일반회계': 'gen_acnt_amt'}),
    ('HCDIB', '1인당 세출예산액', '규모', '천원', '예산',
     {'비율': 'rate', '금액': 'bfae_totl_amt'}),
    ('BJHJB', '1인당 지방세부담액', '규모', '천원', '예산',
     {'비율': 'one_llx_smam', '금액': 'ltax_efir_tott_amt'}),

    # ② 어디서 오나 — 당초·최종·결산 세 판을 나란히. 차이가 추경이다
    ('DCFCE', '재정자립도[당초]', '어디서 오나', '%', '예산[당초]',
     {'비율': 'rate2', '금액': 'pfa_amt3', '분모': 'pfa_amt2'}),
    ('JFIED', '재정자립도[최종]', '어디서 오나', '%', '예산[최종]',
     {'비율': 'rate2', '금액': 'pfa_amt3', '분모': 'pfa_amt2'}),
    ('FNCST', '재정자립도[결산]', '어디서 오나', '%', '결산',
     {'비율': 'rate2', '금액': 'pfa_amt3', '분모': 'pfa_amt2'}),
    ('FIFGB', '재정자주도[당초]', '어디서 오나', '%', '예산[당초]',
     {'비율': 'rate2', '금액': ('pfa_amt4', 'pfa_amt2'), '분모': 'pfa_amt3'}),
    ('EJAEE', '재정자주도[최종]', '어디서 오나', '%', '예산[최종]',
     {'비율': 'rate2', '금액': ('pfa_amt4', 'pfa_amt2'), '분모': 'pfa_amt3'}),
    ('FDOST', '재정자주도[결산]', '어디서 오나', '%', '결산',
     {'비율': 'rate2', '금액': ('pfa_amt4', 'pfa_amt2'), '분모': 'pfa_amt3'}),

    # ③ 어디에 쓰나 — 전부 예산 기준. 당초/최종 구분이 없다
    ('EAGGD', '사회복지비중', '어디에 쓰나', '%', '예산',
     {'비율': 'rate', '금액': 'sum_social_bfae_totl_amt', '분모': 'sum_bfae_totl_amt'}),
    ('FBHIF', '자체사업비중', '어디에 쓰나', '%', '예산',
     {'비율': 'rate', '금액': 'self_biz_bdg_tott_amt', '분모': 'bfae_totl_amt'}),
    ('IAFHI', '보조사업비중', '어디에 쓰나', '%', '예산',
     {'비율': 'rate', '금액': 'aid_biz_bdg_tott_amt', '분모': 'bfae_totl_amt'}),
    ('CEIGF', '정책사업비중', '어디에 쓰나', '%', '예산',
     {'비율': 'rate', '금액': 'bdg_tott_amt', '분모': 'bfae_totl_amt'}),
    ('DIJGH', '지방보조금비율', '어디에 쓰나', '%', '결산',
     {'비율': 'lsa_rt', '금액': 'lsa_amt', '분모': 'ane_stl_amt'}),

    # ④ 제대로 쓰나 — 새는 곳
    ('GAEJG', '수의계약비율', '새는 곳', '%', '실적',
     {'비율': 'rate', '금액': 'pfa_amt1', '분모': 'pfa_amt2'}),
    ('DDJAB', '업무추진비비율', '새는 곳', '%', '결산',
     {'비율': 'boe_rt', '금액': 'boe', '분모': 'ane_stl_amt'}),
    ('GAECF', '행사축제경비비율', '새는 곳', '%', '결산',
     {'비율': 'rate', '금액': 'total', '분모': 'pfa_amt1'}),
    ('DADBC', '지방의회경비비율', '새는 곳', '%', '결산',
     {'비율': 'lcl_asmb_exps_rt', '금액': 'lcl_asmb_exps', '분모': 'ane_stl_amt'}),
    ('EJIEH', '연말지출비율', '새는 곳', '%', '결산',
     {'비율': 'ynd_ep_rt', '금액': 'ynd_amt', '분모': 'ane_stl_amt'}),
    ('GJFHC', '공무원인건비비율', '새는 곳', '%', '결산',
     {'비율': 'goem_lbst_rt', '금액': 'goem_lbst', '분모': 'ane_stl_amt'}),
    ('FFHCB', '행정운영경비비중', '새는 곳', '%', '예산',
     {'비율': 'rate', '금액': 'padm_oper_exps_tott_amt', '분모': 'bfae_totl_amt'}),
    ('GHDIE', '의회비비중', '새는 곳', '%', '예산',
     {'비율': 'rate', '금액': 'asmb_bdg_amt', '분모': 'bfae_totl_amt'}),

    # ⑤ 빚
    ('HEDFC', '예산대비채무비율', '빚', '%', '예산',
     {'비율': 'rate', '금액': 'pfa_amt1', '분모': 'pfa_amt2'}),
    ('ACCBI', '자산대비부채비율', '빚', '%', '결산',
     {'비율': 'laf_lat_rt', '금액': 'lat_amt', '분모': 'ast_amt'}),
    ('CHEDJ', '보증채무비율', '빚', '%', '결산',
     {'비율': 'rate', '금액': 'pfa_amt1', '분모': 'pfa_amt2'}),
]


def pull(code, slots, year, key, back=3):
    """그 해 것을 받되, 아직 안 올라왔으면 한 해씩 물러난다. (연도, 행목록)"""
    for i in range(back):
        y = str(int(year) - i)
        try:
            rows, _ = fetch(code, {'fyr': y}, key)
        except SystemExit:
            # INFO-200(해당 데이터 없음) — 아직 그 해가 안 올라온 것이다. 한 해 물러난다
            continue
        if rows:
            return y, rows
    return None, []


def main():
    # 기본값도 박아 두지 않는다 — 결산은 재작년, 예산은 올해가 최신이다
    # (2026년에 2024 결산이 최신. 자세한 것은 README 「기준을 섞지 말 것」).
    올해 = __import__('datetime').date.today().year
    결산연도 = sys.argv[1] if len(sys.argv) > 1 else str(올해 - 2)
    예산연도 = sys.argv[2] if len(sys.argv) > 2 else str(올해)
    key = load_key()
    if not key:
        raise SystemExit('LOFIN_KEY 가 없다')

    _, base = pull('HCDIB', None, 예산연도, key)
    out = {}
    for r in base:
        out[r['laf_cd']] = {
            'laf_cd': r['laf_cd'], 'laf_hg_nm': r['laf_hg_nm'],
            'wa_laf_hg_nm': r['wa_laf_hg_nm'], 'wa_laf_cd': r['wa_laf_cd'],
            '인구': r.get('pptn_num'), '지표': {},
        }
    print(f'결산 {결산연도} · 예산 {예산연도} · 자치단체 {len(out)}곳\n')

    meta = []
    for code, name, axis, unit, basis, slots in BUNDLE:
        want = 결산연도 if basis in ('결산', '실적') else 예산연도
        year, rows = pull(code, slots, want, key)
        got = 0
        for r in rows:
            cell = out.get(r['laf_cd'])
            if cell is None:
                continue
            vals = {}
            for k, f in slots.items():
                if isinstance(f, tuple):     # 여러 칸을 더해야 하는 것(자주재원 따위)
                    parts = [r[x] for x in f if r.get(x) is not None]
                    if parts:
                        vals[k] = sum(parts)
                elif r.get(f) is not None:
                    vals[k] = r[f]
            if vals:
                cell['지표'][name] = vals
                got += 1
        meta.append({'코드': code, '이름': name, '축': axis, '단위': unit,
                     '기준': basis, '연도': year, '값 있는 곳': got})
        늦음 = ' ←한 해 물러남' if year and year != want else ''
        print(f"  {code:8} {name:18} {basis:10} {year}년 {got:3}곳{늦음}")

    # 추경은 같은 해의 당초와 최종을 견줘야 나온다.
    # 당초는 2026 까지, 최종은 2025 까지 있으므로 비교는 최종이 있는 해로 맞춘다.
    최종해 = next((m['연도'] for m in meta if m['기준'] == '예산[최종]' and m['연도']), None)
    if 최종해:
        _, 당초rows = pull('DCFCE', None, 최종해, key, back=1)
        _, 최종rows = pull('JFIED', None, 최종해, key, back=1)
        당초 = {r['laf_cd']: r.get('pfa_amt2') for r in 당초rows}
        got = 0
        for r in 최종rows:
            cell = out.get(r['laf_cd'])
            a, b = 당초.get(r['laf_cd']), r.get('pfa_amt2')
            if cell is None or not a or not b:
                continue
            cell['지표']['추경 증가율'] = {
                '비율': round((b - a) / a * 100, 2), '금액': b - a, '분모': a}
            got += 1
        meta.append({'코드': 'DCFCE↔JFIED', '이름': '추경 증가율', '축': '어디서 오나',
                     '단위': '%', '기준': f'예산[당초→최종]', '연도': 최종해, '값 있는 곳': got})
        print(f"  {'DCFCE↔JFIED':8} {'추경 증가율':18} {'예산[당초→최종]':10} {최종해}년 {got:3}곳")

    path = os.path.join(ROOT, 'data', 'indicators', f'{결산연도}-{예산연도}.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        # ⚠️ 만든날을 꼭 적는다 — 없으면 이 숫자가 언제 것인지 나중에 알 길이 없다
        json.dump({'결산연도': 결산연도, '예산연도': 예산연도,
                   '만든날': __import__('datetime').date.today().isoformat(),
                   '지표목록': meta,
                   '자치단체': sorted(out.values(), key=lambda x: x['laf_cd'])},
                  f, ensure_ascii=False, indent=1)
    print(f'\n저장 data/indicators/{결산연도}-{예산연도}.json '
          f'({os.path.getsize(path)/1024:,.0f} KB)')


if __name__ == '__main__':
    main()
