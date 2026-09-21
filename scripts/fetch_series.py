# 세출·세입 결산 총액을 여러 해치 받아 시계열로 묶는다.
#
#   python scripts/fetch_series.py 2009 2024
#
# 순서도 ② "10년 동안 어떻게 변했나" 에 쓴다. 두 종 모두 2009~2024 가 다 있고
# 한 해에 한 번 호출이면 243곳이 통째로 온다 — 16년치라야 32번이다.
#
# 결과: data/series.json

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

SERIES = [
    ('AJGCF', '세출', 'tot_pfa_amt'),
    ('IIBBH', '세입', 'total'),
]


def main():
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 2009
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 2024
    key = load_key()
    if not key:
        raise SystemExit('LOFIN_KEY 가 없다')

    out = {}
    names = {}
    for code, label, field in SERIES:
        for year in range(lo, hi + 1):
            rows, _ = fetch(code, {'fyr': str(year)}, key)
            n = 0
            for r in rows:
                v = r.get(field)
                if v is None:
                    continue
                names[r['laf_cd']] = {'이름': r['laf_hg_nm'], '시도': r['wa_laf_hg_nm']}
                out.setdefault(r['laf_cd'], {}).setdefault(str(year), {})[label] = v
                n += 1
            print(f'  {label} {year} · {n}곳')

    path = os.path.join(ROOT, 'data', 'series.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'기간': f'{lo}~{hi}', '단위': '원', '자치단체': names, '값': out},
                  f, ensure_ascii=False, separators=(',', ':'))
    print(f'\n저장 data/series.json ({os.path.getsize(path)/1024:,.0f} KB) · '
          f'{len(out)}곳 × {hi-lo+1}년')


if __name__ == '__main__':
    main()
