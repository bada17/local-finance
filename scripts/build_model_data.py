# 화면에 넣을 자치단체별 데이터를 뽑는다.
#
#   python scripts/build_model_data.py --all           243곳 전부
#   python scripts/build_model_data.py 2600000 4612000 몇 곳만
#
# 지표마다 금액·분모·비율을 다 담고, 견줄 무리 안에서의 순위와 중앙값·최소·최대를 붙인다.
# 광역은 광역끼리(17곳), 기초는 기초끼리(226곳) 견준다 — 섞으면 순위가 뜻을 잃는다.
# 시계열(세출·세입 16년치)도 같이 담는다(화면에서는 아직 안 쓴다).
#
# 결과: site/data/loc/<자치단체코드>.json · site/data/loc/index.json(고르개에 쓸 243곳 목록)
# 화면이 고른 곳의 파일만 그때그때 읽는다. 243곳을 페이지에 다 담으면 3MB 가 넘는다.

import json
import os
import statistics
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lofin import fetch, load_key  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDICATORS = '2024-2026'      # data/indicators/<이것>.json

# 값이 높을수록 눈여겨볼 지표
HIGH_IS_BAD = {'수의계약비율', '업무추진비비율', '행사축제경비비율', '지방의회경비비율',
               '연말지출비율', '공무원인건비비율', '행정운영경비비중', '의회비비중',
               '예산대비채무비율', '자산대비부채비율', '보증채무비율'}

# 화면에 나오는 차례 — README 의 순서도와 같다
축순서 = ['규모', '어디서 오나', '어디에 쓰나', '새는 곳', '빚']


def main():
    args = list(sys.argv[1:])
    모두 = '--all' in args
    if 모두:
        args.remove('--all')
    d = json.load(open(os.path.join(ROOT, 'data', 'indicators', f'{INDICATORS}.json'), encoding='utf-8'))
    locs = {x['laf_cd']: x for x in d['자치단체']}
    meta = {m['이름']: m for m in d['지표목록']}
    codes = sorted(locs) if 모두 else (args or ['2600000', '4373000'])

    series_path = os.path.join(ROOT, 'data', 'series.json')
    series = json.load(open(series_path, encoding='utf-8')) if os.path.exists(series_path) else None

    key = load_key()
    links = {}
    for code, label in (('BUDLK', '예산서'), ('SETLK', '결산서'), ('FINLK', '재정공시')):
        rows, _ = fetch(code, {'fyr': d['결산연도'] if code == 'SETLK' else '2025'}, key)
        for r in rows:
            links.setdefault(r['laf_cd'], {})[label] = r.get('lnk_url_nm')

    OUT = os.path.join(ROOT, 'site', 'data', 'loc')
    os.makedirs(OUT, exist_ok=True)
    목록 = []
    총크기 = 0
    for cd in codes:
        me = locs[cd]
        wide = cd.endswith('00000')
        peers = [x for x in locs.values() if x['laf_cd'].endswith('00000') == wide]

        out = {
            '결산연도': d['결산연도'], '예산연도': d['예산연도'], 'laf_cd': cd, '이름': me['laf_hg_nm'], '시도': me['wa_laf_hg_nm'],
            '갈래': '광역' if wide else '기초', '인구': me['인구'],
            '견줄곳수': len(peers), '원문': links.get(cd, {}),
            '지표': [], '시계열': [],
        }

        for name, m in meta.items():
            cell = me['지표'].get(name)
            if not cell:
                continue
            # 순위는 비율이 있으면 비율로, 없으면(규모) 금액으로 매긴다
            key_slot = '비율' if '비율' in cell else '금액'
            v = cell.get(key_slot)
            if v is None:
                continue
            vals = [x['지표'][name][key_slot] for x in peers
                    if name in x['지표'] and x['지표'][name].get(key_slot) is not None]
            out['지표'].append({
                '이름': name, '축': m['축'], '단위': m['단위'],
                '기준': m['기준'], '연도': m['연도'],
                '비율': cell.get('비율'), '금액': cell.get('금액'),
                '분모': cell.get('분모'), '일반회계': cell.get('일반회계'),
                '순위기준': key_slot,
                # 순위는 늘 "1위 = 값이 가장 큰 곳". 같은 값이 여럿이면 공동 순위
                '순위': sum(1 for x in vals if x > v) + 1,
                '전체': len(vals),
                '높을수록나쁨': name in HIGH_IS_BAD,
                '중앙값': round(statistics.median(vals), 2),
                '최소': min(vals), '최대': max(vals),
            })
        out['지표'].sort(key=lambda m: (축순서.index(m['축']) if m['축'] in 축순서 else 9))

        if series and cd in series['값']:
            for year in sorted(series['값'][cd]):
                row = series['값'][cd][year]
                out['시계열'].append({'연도': year, '세출': row.get('세출'), '세입': row.get('세입')})

        path = os.path.join(OUT, f'{cd}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
        총크기 += os.path.getsize(path)
        목록.append({'cd': cd, '이름': out['이름'], '시도': out['시도'],
                    '갈래': out['갈래'], '인구': out['인구']})
        if len(codes) <= 5:
            print(f"{out['이름']} ({out['갈래']}) · 지표 {len(out['지표'])} · "
                  f"시계열 {len(out['시계열'])}년 · 원문 {len(out['원문'])} · "
                  f"{os.path.getsize(path)/1024:,.0f}KB")

    # 고르개에 쓸 목록. 이것만 화면에 통째로 박힌다
    idx_path = os.path.join(OUT, 'index.json')
    if len(목록) < 243 and os.path.exists(idx_path):
        # 몇 곳만 다시 구운 것이면 있던 목록을 그대로 둔다
        print(f'{len(목록)}곳 구움 (목록은 그대로 둔다) · {총크기/1024:,.0f}KB')
        return
    with open(idx_path, 'w', encoding='utf-8') as f:
        json.dump({'결산연도': d['결산연도'], '예산연도': d['예산연도'],
                   '곳': sorted(목록, key=lambda x: (x['갈래'] != '광역', x['시도'], x['이름']))},
                  f, ensure_ascii=False, separators=(',', ':'))
    print(f"{len(목록)}곳 구움 · {총크기/1024/1024:,.1f}MB · "
          f"목록 {os.path.getsize(idx_path)/1024:,.0f}KB → site/data/loc/")


if __name__ == '__main__':
    main()
