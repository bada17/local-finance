# 보탬e 지방보조금을 자치단체별로 묶는다 — data/grants/<해>.json.gz → site/data/grants/<코드>.json
#
#   python scripts/build_grants.py
#
# ⑥ 「누가 받아 갔나」 판의 **보조금 칸**이 이걸 읽는다. 계약 칸(build_contracts_summary.py)과 짝이다.
# ⚠️ 보탬e 곳코드(6110000 등 행정표준코드)와 화면의 곳코드(1100000 등 지방재정365)가 **다르다.**
#    이름으로 잇는다 — 「중구」가 6곳이라 **시도를 붙여서** 맞춘다(시도 없이 세면 243곳이 222곳이 된다).
# ⚠️ 받는 쪽은 **보탬e 기관 ID(pfmInstId)로** 묶는다. 같은 ID 에 이름이 여럿이면 금액이 큰 이름을 쓴다.
#    「비공개기관」은 지우지 않고 한 줄로 따로 센다 — **얼마나 가렸나**도 세어야 할 숫자다.
# ✔ 받은 쪽이 개인이어도 그대로 띄운다(2026-09-22 사용자 결정 — 보고 나서 다시 정한다).
# ⭐ 해를 박지 않는다. data/grants/ 에 있는 해를 전부 굽는다.

import collections
import glob
import gzip
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'site', 'data', 'grants')
상위 = 30

시도줄임 = {'서울특별시': '서울', '부산광역시': '부산', '대구광역시': '대구', '인천광역시': '인천',
         '광주광역시': '광주', '대전광역시': '대전', '울산광역시': '울산', '세종특별자치시': '세종',
         '경기도': '경기', '강원특별자치도': '강원', '강원도': '강원', '충청북도': '충북', '충청남도': '충남',
         '전북특별자치도': '전북', '전라북도': '전북', '전라남도': '전남', '경상북도': '경북',
         '경상남도': '경남', '제주특별자치도': '제주'}
# 보탬e 이름이 화면 목록과 다른 곳 — 인천 서구는 2026년 서해구로 이름이 바뀌었다
딴이름 = {'인천서해구': '인천서구'}


def 화면이름(광역, 곳):
    시도 = 시도줄임[광역]
    n = 시도 + ('본청' if 곳 == 광역 else 곳)
    return 딴이름.get(n, n)


def main():
    idx = json.load(open(os.path.join(ROOT, 'site', 'data', 'loc', 'index.json'), encoding='utf-8'))
    코드찾기 = {x['이름']: x['cd'] for x in idx['곳']}

    곳별 = collections.defaultdict(dict)       # 코드 → 해 → 묶음
    못맞춤 = set()
    for 파일 in sorted(glob.glob(os.path.join(ROOT, 'data', 'grants', '*.json.gz'))):
        해 = os.path.basename(파일)[:4]
        for r in json.load(gzip.open(파일, 'rt', encoding='utf-8')):
            n = 화면이름(r['_광역'], r['_곳'])
            cd = 코드찾기.get(n)
            if not cd:
                못맞춤.add(n)
                continue
            y = 곳별[cd].setdefault(해, {'금액': 0, '건수': 0, '비공개금액': 0, '비공개건수': 0,
                                      '공시끝날': '', '받은곳': {}})
            금액 = int(r.get('bizctSbatAmt') or 0)
            y['금액'] += 금액
            y['건수'] += 1
            y['공시끝날'] = max(y['공시끝날'], r.get('pbaYmd') or '')
            이름 = (r.get('pfmInstNm') or '').strip()
            if 이름 == '비공개기관':
                y['비공개금액'] += 금액
                y['비공개건수'] += 1
            열쇠 = '비공개' if 이름 == '비공개기관' else (r.get('pfmInstId') or 이름)
            b = y['받은곳'].setdefault(열쇠, {'이름꼴': collections.Counter(), '금액': 0, '건수': 0,
                                           '사업': collections.Counter()})
            b['이름꼴'][이름] += 금액
            b['금액'] += 금액
            b['건수'] += 1
            b['사업'][(r.get('pfmBizNm') or '').strip()] += 금액

    if 못맞춤:
        raise SystemExit(f'화면 목록과 못 맞춘 곳 {len(못맞춤)} — {sorted(못맞춤)}')

    os.makedirs(OUT, exist_ok=True)
    for cd, 해들 in 곳별.items():
        낼 = {'laf_cd': cd, '칸': ['받은 곳', '금액', '건수', '가장 큰 사업'], '해': {}}
        for 해, y in 해들.items():
            줄 = sorted(y.pop('받은곳').values(), key=lambda b: -b['금액'])
            y['받은곳수'] = len(줄)
            y['받은곳'] = [[b['이름꼴'].most_common(1)[0][0], b['금액'], b['건수'],
                          b['사업'].most_common(1)[0][0]] for b in 줄[:상위]]
            y['상위몫'] = sum(b['금액'] for b in 줄[:5])
            낼['해'][해] = y
        with open(os.path.join(OUT, f'{cd}.json'), 'w', encoding='utf-8') as f:
            json.dump(낼, f, ensure_ascii=False, separators=(',', ':'))
    print(f'적음: site/data/grants/ {len(곳별)}곳')


if __name__ == '__main__':
    main()
