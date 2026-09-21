# 시황판 데이터를 만든다 — 243곳을 한 표에 놓고 칸을 골라 보는 판.
#
#   python scripts/build_board.py
#
# site/data/loc/*.json (자치단체별 지표)을 모아 **한 파일**로 눌러 담는다.
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

    out = {'만든날': __import__('time').strftime('%Y-%m-%d'),
           '결산연도': d['결산연도'], '예산연도': d['예산연도'],
           '지표': 지표목록, '곳': 곳}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with gzip.open(OUT, 'wt', encoding='utf-8', compresslevel=9) as fp:
        json.dump(out, fp, ensure_ascii=False, separators=(',', ':'))
    print(f'구움: site/data/board.json.gz ({os.path.getsize(OUT)/1024:,.0f} KB) · '
          f'{len(곳)}곳 × 지표 {len(지표목록)}종')


if __name__ == '__main__':
    main()
