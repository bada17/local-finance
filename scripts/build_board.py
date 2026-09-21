# 시황판 데이터를 만든다 — 243곳을 한 표에 놓고 칸을 골라 보는 판.
#
#   python scripts/build_board.py
#
# site/data/loc/*.json (자치단체별 지표)을 모아 **한 파일**로 눌러 담는다.
# 여기에 **계약 3년치를 우리가 직접 센 칸**(data/contracts_summary.json)을 덧붙인다.
# 화면에서 「어느 지표를 칸으로 세울지」 고를 수 있어야 하므로 값만 촘촘히 담는다.
#
# 결과: site/data/board.json.gz

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
LOC = os.path.join(ROOT, 'site', 'data', 'loc')
OUT = os.path.join(ROOT, 'site', 'data', 'board.json.gz')


# 계약은 **다른 자료·다른 기준**이다 — 지방재정365 지표와 섞이지 않게 축을 따로 둔다.
# ⚠️ 연도는 계약일 기준이고, 2026년은 아홉 달치뿐이라 **온전한 마지막 해인 2025년**만 올린다.
계약해 = '2025'
계약지표 = [
    # (이름, 단위, 높을수록나쁨, 여기서 꺼낼 칸, 비율인가)
    ('계약 총액', '원', False, '금액', False),
    ('수의계약 금액 비중', '%', True, '수의금액률', True),
    ('수의계약 건수 비중', '%', True, '수의건수율', True),
    ('상위 5개 업체 몫', '%', True, '상위5몫', True),
    ('거래 업체 수', '곳', False, '업체수', False),
]


def 계약칸(곳, 지표목록, 자리):
    """계약 원자료에서 센 칸을 시황판에 붙인다. 파일이 없으면 그냥 건너뛴다."""
    p = os.path.join(ROOT, 'data', 'contracts_summary.json')
    if not os.path.exists(p):
        print('   (계약 요약이 없어 계약 칸은 건너뛴다)')
        return 0
    cs = json.load(open(p, encoding='utf-8'))
    표 = cs['곳']
    시작 = len(지표목록)
    for 이름, 단위, 나쁨, 칸, 비율인가 in 계약지표:
        자리[이름] = len(지표목록)
        지표목록.append({'이름': 이름, '축': '계약 3년치(우리가 센 것)', '단위': 단위,
                       '기준': '계약', '연도': 계약해, '높을수록나쁨': 나쁨})
    붙은곳 = 0
    for r in 곳:
        d = 표.get(r['cd'], {}).get(계약해)
        if not d:
            continue
        붙은곳 += 1
        for k, (이름, 단위, 나쁨, 칸, 비율인가) in enumerate(계약지표):
            v = d.get(칸)
            if v is None:
                continue
            r['값'][시작 + k] = [v, None] if 비율인가 else [None, v]
    return 붙은곳


# 진행 중인 사업(QWGJK)은 **그달 누계**다 — 연 단위 지표와 기준이 또 다르다.
# ⚠️ 2026년에 구역이 바뀌어 광주본청·전남본청·인천중구·인천동구는 진행 자료가 없다.
#    없는 곳은 칸을 비워 둔다. **0 으로 채우지 말 것.**
진행지표 = [
    ('예산현액(진행 중인 사업)', '원', False, '예산현액'),
    ('집행률', '%', False, '집행률'),
    ('국비 비중', '%', False, '국비비중'),
]


def 진행칸(곳, 지표목록, 자리):
    """진행 중인 사업 파일에서 총액·집행률만 꺼내 시황판에 붙인다."""
    files = sorted(glob.glob(os.path.join(ROOT, 'site', 'data', 'ongoing', '*.json.gz')))
    if not files:
        print('   (진행 자료가 없어 진행 칸은 건너뛴다)')
        return 0, ''
    표 = {}
    기준 = ''
    for f in files:
        d = json.load(gzip.open(f, 'rt', encoding='utf-8'))
        기준 = 기준 or str(d.get('기준') or '')
        예산 = d.get('예산현액') or 0
        표[d['laf_cd']] = {
            '예산현액': 예산,
            '집행률': round((d.get('지출') or 0) / 예산 * 100, 1) if 예산 else None,
            '국비비중': round((d.get('국비') or 0) / 예산 * 100, 1) if 예산 else None,
        }
    달 = f'{기준[:4]}.{기준[4:6]}' if len(기준) >= 6 else 기준
    시작 = len(지표목록)
    for 이름, 단위, 나쁨, _ in 진행지표:
        자리[이름] = len(지표목록)
        지표목록.append({'이름': 이름, '축': f'진행 중인 사업({달} 누계)', '단위': 단위,
                       '기준': '진행', '연도': 달, '높을수록나쁨': 나쁨})
    붙은곳 = 0
    for r in 곳:
        d = 표.get(r['cd'])
        if not d:
            continue
        붙은곳 += 1
        for k, (이름, 단위, 나쁨, 칸) in enumerate(진행지표):
            v = d.get(칸)
            if v is None:
                continue
            r['값'][시작 + k] = [v, None] if 단위 == '%' else [None, v]
    return 붙은곳, 달


def main():
    files = sorted(glob.glob(os.path.join(LOC, '*.json')))
    files = [f for f in files if not f.endswith('index.json')]
    지표목록 = []       # [{이름, 축, 단위, 기준, 연도, 높을수록나쁨}]
    자리 = {}
    곳 = []

    for f in files:
        d = json.load(open(f, encoding='utf-8'))
        값 = {}
        for m in d['지표']:
            if m['이름'] not in 자리:
                자리[m['이름']] = len(지표목록)
                지표목록.append({'이름': m['이름'], '축': m['축'], '단위': m['단위'],
                               '기준': m['기준'], '연도': m['연도'],
                               '높을수록나쁨': m['높을수록나쁨']})
            # 비율이 있으면 비율, 없으면 금액을 칸 값으로 쓴다
            값[자리[m['이름']]] = [m.get('비율'), m.get('금액')]
        곳.append({'cd': d['laf_cd'], '이름': d['이름'], '시도': d['시도'],
                  '갈래': d['갈래'], '인구': d['인구'], '값': 값})

    붙임 = 계약칸(곳, 지표목록, 자리)
    진행붙임, 기준달 = 진행칸(곳, 지표목록, 자리)

    out = {'만든날': __import__('time').strftime('%Y-%m-%d'),
           '결산연도': d['결산연도'], '예산연도': d['예산연도'],
           '지표': 지표목록, '곳': 곳}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with gzip.open(OUT, 'wt', encoding='utf-8', compresslevel=9) as fp:
        json.dump(out, fp, ensure_ascii=False, separators=(',', ':'))
    print(f'구움: site/data/board.json.gz ({os.path.getsize(OUT)/1024:,.0f} KB) · '
          f'{len(곳)}곳 × 지표 {len(지표목록)}종 '
          f'(계약 칸 {붙임}곳 · 진행 칸 {진행붙임}곳 [{기준달}])')


if __name__ == '__main__':
    main()
