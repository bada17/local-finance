# 한눈에(대시보드)와 자치단체별 그래프가 같이 쓰는 전국 표를 굽는다 — site/data/dash.json
#
#   python scripts/build_dashboard.py
#
# 243곳 × 지표 30여 종을 **곳 차례대로 늘어선 배열**로 담는다(곳마다 파일을 받지 않고 한 번에 견주려고).
# 지표는 data/indicators/ 의 가장 새 파일, 5년 추이는 data/series.json 에서.
# 화면(site/index.html 의 대시보드 모드 ./?g)은 이 파일을 받아 그래프를 그린다. 숫자는 여기서 바꾸지 않는다.
#
# ⚠️ 광역과 기초를 한데 더하지 말 것 — 광역이 기초에 내려준 돈(조정교부금·보조금)이 두 번 세진다.
#    화면은 갈래(광역·시·군·구)별로만 더하고 견준다.

import json
import os
import sys
from datetime import date

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_model_data import HIGH_IS_BAD, 최신지표, 축순서  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
해수 = 5   # 추이는 5년만 — 2026-09-21 사용자 결정(16년치는 받아만 둔다)


def 갈래(cd, 이름):
    if cd.endswith('00000'):
        return '광역'
    return {'시': '시', '군': '군', '구': '구'}.get(이름[-1], '기초')


def main():
    이름 = 최신지표()
    d = json.load(open(os.path.join(ROOT, 'data', 'indicators', f'{이름}.json'), encoding='utf-8'))
    곳들 = sorted(d['자치단체'], key=lambda x: x['laf_cd'])
    곳 = [[x['laf_cd'], x['laf_hg_nm'], x['wa_laf_hg_nm'], 갈래(x['laf_cd'], x['laf_hg_nm']), x['인구']]
         for x in 곳들]

    지표 = []
    for m in sorted(d['지표목록'], key=lambda m: 축순서.index(m['축']) if m['축'] in 축순서 else 9):
        n = m['이름']
        칸 = [x['지표'].get(n, {}) for x in 곳들]
        지표.append({'이름': n, '축': m['축'], '단위': m['단위'], '기준': m['기준'], '연도': m['연도'],
                    '나쁨': int(n in HIGH_IS_BAD),
                    '비율': [c.get('비율') for c in 칸], '금액': [c.get('금액') for c in 칸]})

    s = json.load(open(os.path.join(ROOT, 'data', 'series.json'), encoding='utf-8'))
    해들 = sorted({y for v in s['값'].values() for y in v})[-해수:]
    추이 = {'해': 해들}
    for k in ('세출', '세입'):
        추이[k] = [[(s['값'].get(x['laf_cd'], {}).get(y) or {}).get(k) for y in 해들] for x in 곳들]

    out = {'만든날': date.today().isoformat(), '결산연도': d['결산연도'], '예산연도': d['예산연도'],
           '곳칸': ['코드', '이름', '시도', '갈래', '인구'], '곳': 곳, '지표': 지표, '추이': 추이}
    path = os.path.join(ROOT, 'site', 'data', 'dash.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    print(f'구움: site/data/dash.json ({os.path.getsize(path)/1024:,.0f} KB) · '
          f'{len(곳)}곳 · 지표 {len(지표)}종 · 추이 {해들[0]}~{해들[-1]}')


if __name__ == '__main__':
    main()
