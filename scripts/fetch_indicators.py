# 화면에 쓸 지표 묶음을 한 해치 받아 한 파일로 묶는다.
#
#   python scripts/fetch_indicators.py 2024
#
# 전부 243곳 전수로 오는 것들이라 인증키가 있으면 한 종에 한 번 호출이면 끝난다.
# 결산 시즌에 한 번, 예산 확정 뒤에 한 번 돌리면 되는 성격의 수집이다.
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

# (서비스코드, 우리가 쓸 이름, 축, 가져올 값)
# rate 는 비율 지표가 공통으로 쓰는 칸이다.
BUNDLE = [
    ('GAEJG', '수의계약비율', '새는 곳', 'rate'),
    ('DDJAB', '업무추진비비율', '새는 곳', 'boe_rt'),
    ('GAECF', '행사축제경비비율', '새는 곳', 'rate'),
    ('DADBC', '지방의회경비비율', '새는 곳', 'lcl_asmb_exps_rt'),
    ('EJIEH', '연말지출비율', '새는 곳', 'ynd_ep_rt'),
    ('GJFHC', '공무원인건비비율', '새는 곳', 'goem_lbst_rt'),

    ('EAGGD', '사회복지비중', '어디에 쓰나', 'rate'),
    ('FBHIF', '자체사업비중', '어디에 쓰나', 'rate'),
    ('IAFHI', '보조사업비중', '어디에 쓰나', 'rate'),
    ('CEIGF', '정책사업비중', '어디에 쓰나', 'rate'),
    ('FFHCB', '행정운영경비비중', '어디에 쓰나', 'rate'),
    ('GHDIE', '의회비비중', '어디에 쓰나', 'rate'),
    ('DIJGH', '지방보조금비율', '어디에 쓰나', 'lsa_rt'),

    ('HEDFC', '예산대비채무비율', '빚', 'rate'),
    ('ACCBI', '자산대비부채비율', '빚', 'laf_lat_rt'),
    ('CHEDJ', '보증채무비율', '빚', 'rate'),

    ('FNCST', '재정자립도', '자립', 'rate2'),
    ('FDOST', '재정자주도', '자립', 'rate2'),

    ('HCDIB', '1인당세출예산액', '규모', 'rate'),
    ('BJHJB', '1인당지방세부담액', '규모', 'one_llx_smam'),
]


def main():
    year = sys.argv[1] if len(sys.argv) > 1 else '2024'
    key = load_key()
    if not key:
        raise SystemExit('LOFIN_KEY 가 없다')

    # 자치단체 뼈대부터 (인구가 같이 오는 것으로)
    base, _ = fetch('HCDIB', {'fyr': year}, key)
    out = {}
    for r in base:
        out[r['laf_cd']] = {
            'laf_cd': r['laf_cd'],
            'laf_hg_nm': r['laf_hg_nm'],
            'wa_laf_hg_nm': r['wa_laf_hg_nm'],
            'wa_laf_cd': r['wa_laf_cd'],
            '인구': r.get('pptn_num'),
            '지표': {},
        }
    print(f'{year}년 · 자치단체 {len(out)}곳')

    meta = []
    for code, name, axis, field in BUNDLE:
        try:
            rows, total = fetch(code, {'fyr': year}, key)
        except SystemExit as e:
            print(f'  {code:8} {name:14} 못 받음 — {e}')
            continue
        got = 0
        for r in rows:
            cell = out.get(r['laf_cd'])
            if cell is not None and r.get(field) is not None:
                cell['지표'][name] = r[field]
                got += 1
        meta.append({'코드': code, '이름': name, '축': axis, '값 있는 곳': got})
        print(f'  {code:8} {name:14} {axis:8} {got:3}곳')

    path = os.path.join(ROOT, 'data', 'indicators', f'{year}.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'연도': year, '지표목록': meta,
                   '자치단체': sorted(out.values(), key=lambda x: x['laf_cd'])},
                  f, ensure_ascii=False, indent=1)
    print(f'\n저장 data/indicators/{year}.json ({os.path.getsize(path)/1024:,.0f} KB)')


if __name__ == '__main__':
    main()
