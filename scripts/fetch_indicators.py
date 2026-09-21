# 화면에 쓸 지표 묶음을 한 해치 받아 한 파일로 묶는다.
#
#   python scripts/fetch_indicators.py 2024
#
# 전부 243곳 전수로 오는 것들이라 인증키가 있으면 한 종에 한 번 호출이면 끝난다.
# 결산 시즌에 한 번, 예산 확정 뒤에 한 번 돌리면 되는 성격의 수집이다.
#
# ⚠️ 비율만 뽑지 말 것. 비율 지표는 분자·분모 금액이 **같은 응답에 이미 들어 있다.**
#    "행사축제경비 1.2%"만 보여주면 그게 몇 억인지 모른다. 호출 수는 똑같으니
#    비율·금액·분모를 늘 함께 담는다. (2026-09-21 에 비율만 뽑고 있던 것을 고쳤다)
#
# 결과: data/indicators/<연도>.json — 자치단체별로 지표를 한 줄에 모아 둔다.

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

# 코드, 이름, 축, 단위, {비율 / 금액(분자) / 분모} 가 응답의 어느 칸인지
BUNDLE = [
    # ① 규모 — 절대 금액. 다른 모든 비율의 분모가 되는 수다
    ('AJGCF', '세출결산 총액', '규모', '원',
     {'금액': 'tot_pfa_amt', '일반회계': 'pfa_amt1'}),
    ('IIBBH', '세입결산 총액', '규모', '원',
     {'금액': 'total', '일반회계': 'pfa_amt1'}),
    ('HCDIB', '1인당 세출예산액', '규모', '천원',
     {'비율': 'rate', '금액': 'bfae_totl_amt'}),
    ('BJHJB', '1인당 지방세부담액', '규모', '천원',
     {'비율': 'one_llx_smam', '금액': 'ltax_efir_tott_amt'}),

    # ③ 어디서 오나
    ('FNCST', '재정자립도', '어디서 오나', '%',
     {'비율': 'rate2', '금액': 'pfa_amt3', '분모': 'pfa_amt2'}),
    # 자주도의 분자는 자체수입 + 자주재원이다. 한 칸만 쓰면 비율과 안 맞는다
    ('FDOST', '재정자주도', '어디서 오나', '%',
     {'비율': 'rate2', '금액': ('pfa_amt4', 'pfa_amt2'), '분모': 'pfa_amt3'}),

    # ④ 어디에 쓰나
    ('EAGGD', '사회복지비중', '어디에 쓰나', '%',
     {'비율': 'rate', '금액': 'sum_social_bfae_totl_amt', '분모': 'sum_bfae_totl_amt'}),
    ('FBHIF', '자체사업비중', '어디에 쓰나', '%',
     {'비율': 'rate', '금액': 'self_biz_bdg_tott_amt', '분모': 'bfae_totl_amt'}),
    ('IAFHI', '보조사업비중', '어디에 쓰나', '%',
     {'비율': 'rate', '금액': 'aid_biz_bdg_tott_amt', '분모': 'bfae_totl_amt'}),
    ('CEIGF', '정책사업비중', '어디에 쓰나', '%',
     {'비율': 'rate', '금액': 'bdg_tott_amt', '분모': 'bfae_totl_amt'}),
    ('DIJGH', '지방보조금비율', '어디에 쓰나', '%',
     {'비율': 'lsa_rt', '금액': 'lsa_amt', '분모': 'ane_stl_amt'}),

    # ⑤ 제대로 쓰나 — 새는 곳
    ('GAEJG', '수의계약비율', '새는 곳', '%',
     {'비율': 'rate', '금액': 'pfa_amt1', '분모': 'pfa_amt2'}),
    ('DDJAB', '업무추진비비율', '새는 곳', '%',
     {'비율': 'boe_rt', '금액': 'boe', '분모': 'ane_stl_amt'}),
    ('GAECF', '행사축제경비비율', '새는 곳', '%',
     {'비율': 'rate', '금액': 'total', '분모': 'pfa_amt1'}),
    ('DADBC', '지방의회경비비율', '새는 곳', '%',
     {'비율': 'lcl_asmb_exps_rt', '금액': 'lcl_asmb_exps', '분모': 'ane_stl_amt'}),
    ('EJIEH', '연말지출비율', '새는 곳', '%',
     {'비율': 'ynd_ep_rt', '금액': 'ynd_amt', '분모': 'ane_stl_amt'}),
    ('GJFHC', '공무원인건비비율', '새는 곳', '%',
     {'비율': 'goem_lbst_rt', '금액': 'goem_lbst', '분모': 'ane_stl_amt'}),
    ('FFHCB', '행정운영경비비중', '새는 곳', '%',
     {'비율': 'rate', '금액': 'padm_oper_exps_tott_amt', '분모': 'bfae_totl_amt'}),
    ('GHDIE', '의회비비중', '새는 곳', '%',
     {'비율': 'rate', '금액': 'asmb_bdg_amt', '분모': 'bfae_totl_amt'}),

    # ⑥ 빚
    ('HEDFC', '예산대비채무비율', '빚', '%',
     {'비율': 'rate', '금액': 'pfa_amt1', '분모': 'pfa_amt2'}),
    ('ACCBI', '자산대비부채비율', '빚', '%',
     {'비율': 'laf_lat_rt', '금액': 'lat_amt', '분모': 'ast_amt'}),
    ('CHEDJ', '보증채무비율', '빚', '%',
     {'비율': 'rate', '금액': 'pfa_amt1', '분모': 'pfa_amt2'}),
]


def main():
    year = sys.argv[1] if len(sys.argv) > 1 else '2024'
    key = load_key()
    if not key:
        raise SystemExit('LOFIN_KEY 가 없다')

    base, _ = fetch('HCDIB', {'fyr': year}, key)
    out = {}
    for r in base:
        out[r['laf_cd']] = {
            'laf_cd': r['laf_cd'], 'laf_hg_nm': r['laf_hg_nm'],
            'wa_laf_hg_nm': r['wa_laf_hg_nm'], 'wa_laf_cd': r['wa_laf_cd'],
            '인구': r.get('pptn_num'), '지표': {},
        }
    print(f'{year}년 · 자치단체 {len(out)}곳')

    meta = []
    for code, name, axis, unit, slots in BUNDLE:
        rows, _ = fetch(code, {'fyr': year}, key)
        got = 0
        for r in rows:
            cell = out.get(r['laf_cd'])
            if cell is None:
                continue
            vals = {}
            for k, f in slots.items():
                if isinstance(f, tuple):        # 여러 칸을 더해야 하는 것(자주재원 따위)
                    parts = [r[x] for x in f if r.get(x) is not None]
                    if parts:
                        vals[k] = sum(parts)
                elif r.get(f) is not None:
                    vals[k] = r[f]
            if vals:
                cell['지표'][name] = vals
                got += 1
        meta.append({'코드': code, '이름': name, '축': axis, '단위': unit,
                     '칸': list(slots), '값 있는 곳': got})
        print(f"  {code:8} {name:16} {axis:8} {'·'.join(slots):16} {got:3}곳")

    path = os.path.join(ROOT, 'data', 'indicators', f'{year}.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'연도': year, '지표목록': meta,
                   '자치단체': sorted(out.values(), key=lambda x: x['laf_cd'])},
                  f, ensure_ascii=False, indent=1)
    print(f'\n저장 data/indicators/{year}.json ({os.path.getsize(path)/1024:,.0f} KB)')


if __name__ == '__main__':
    main()
