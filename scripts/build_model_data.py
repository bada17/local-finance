# 모델 화면에 넣을 데이터를 뽑는다. 자치단체 몇 곳만.
#
#   python scripts/build_model_data.py 2600000 4373000
#
# 지표마다 그 자치단체의 값·순위·견줄 무리의 분포를 같이 담는다.
# 광역은 광역끼리(17곳), 기초는 기초끼리(226곳) 견준다 — 섞으면 순위가 뜻을 잃는다.
#
# 결과: data/model/<자치단체코드>.json

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
YEAR = '2024'

# 값이 높을수록 나쁜 지표 — 순위를 매길 때 방향이 다르다
HIGH_IS_BAD = {'수의계약비율', '업무추진비비율', '행사축제경비비율', '지방의회경비비율',
               '연말지출비율', '공무원인건비비율', '행정운영경비비중', '의회비비중',
               '예산대비채무비율', '자산대비부채비율', '보증채무비율'}


def main():
    codes = sys.argv[1:] or ['2600000', '4373000']
    d = json.load(open(os.path.join(ROOT, 'data', 'indicators', f'{YEAR}.json'), encoding='utf-8'))
    locs = {x['laf_cd']: x for x in d['자치단체']}
    meta = {m['이름']: m for m in d['지표목록']}

    key = load_key()
    links = {}
    for code, label in (('BUDLK', '예산서'), ('SETLK', '결산서'), ('FINLK', '재정공시')):
        try:
            rows, _ = fetch(code, {'fyr': '2025' if code != 'SETLK' else '2024'}, key)
            for r in rows:
                links.setdefault(r['laf_cd'], {})[label] = r.get('lnk_url_nm')
        except SystemExit:
            pass

    os.makedirs(os.path.join(ROOT, 'data', 'model'), exist_ok=True)
    for cd in codes:
        me = locs[cd]
        wide = cd.endswith('00000')
        peers = [x for x in locs.values() if x['laf_cd'].endswith('00000') == wide]

        out = {
            '연도': YEAR,
            'laf_cd': cd,
            '이름': me['laf_hg_nm'],
            '시도': me['wa_laf_hg_nm'],
            '갈래': '광역' if wide else '기초',
            '인구': me['인구'],
            '견줄곳수': len(peers),
            '원문': links.get(cd, {}),
            '지표': [],
        }

        for name, m in meta.items():
            v = me['지표'].get(name)
            if v is None:
                continue
            vals = sorted(x['지표'][name] for x in peers if name in x['지표'])
            bad_high = name in HIGH_IS_BAD
            # 순위는 늘 "1위 = 값이 가장 큰 곳". 방향을 지표마다 바꾸면 읽는 사람이 헷갈린다.
            # 그 값이 좋은 일인지 나쁜 일인지는 순위가 아니라 bad_high 가 말한다.
            # 같은 값이 여럿이면 공동 순위로 준다(자기보다 큰 값의 수 + 1).
            rank = sum(1 for x in vals if x > v) + 1
            out['지표'].append({
                '이름': name,
                '축': m['축'],
                '값': v,
                '순위': rank,
                '전체': len(vals),
                '높을수록나쁨': bad_high,
                '중앙값': round(statistics.median(vals), 2),
                '최소': vals[0],
                '최대': vals[-1],
                '분포': vals,
            })

        path = os.path.join(ROOT, 'data', 'model', f'{cd}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f"{out['이름']} ({out['갈래']}) · 지표 {len(out['지표'])}개 · 원문 {len(out['원문'])}개 "
              f"· {os.path.getsize(path)/1024:,.0f}KB")


if __name__ == '__main__':
    main()
