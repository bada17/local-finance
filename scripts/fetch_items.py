# 재료표 「API 받기만」 아이템들 — 해마다 전부 받아 한 종에 한 파일로 둔다.
#
#   python scripts/fetch_items.py            (아래 목록 전부)
#   python scripts/fetch_items.py LLBSR      (하나만)
#
# 모두 243곳 전수로 오는 것들이라 한 해에 한두 번 호출이면 된다. 해 범위는
# data/lofin365_146.json 의 years 에서 시작해 올해까지 — 늦게 올라온 해도 잡힌다.
# 비는 해는 건너뛴다(오류 대신 0행).
#
# 결과: data/items/<코드>.json.gz — {코드, 이름, 만든날, 해별: {해: 행수}, 행: [...]}
# 화면은 아직 없다. 회의(재료표 「선정 회의」)에서 고른 것만 화면으로 간다.

import datetime
import gzip
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

# 재료표 번호 → 코드
ITEMS = {
    'LLBSR': 16,   # 교부세가 깎인 곳
    'FBHFE': 15,   # 민자사업
    'EVFTCT': 9,   # 축제 하나하나
    'KBAAD': 9, 'YCEHF': 9, 'AUEVR': 9,   # 축제에 돈이 들어가는 길(2026-10-16) — 행사경비 갈래별(~2022)·편성(올해)·출자출연기관까지(결산)
    'HHRNV': 14,   # 공공시설 적자
    'NBRILV': 10, 'YQMZYF': 10,   # 업무추진비 편성
    'VZATVL': 8, 'GVBDAC': 8,     # 청사
    'DJIELS': 13,  # 예비비
    'NTASEX': 12,  # 의원 연수(지방의회 관련경비)
    'LIMHJ': 17, 'RHJDKD': 17,    # 현금성 복지
}


def 받기(code, cat, key):
    lo = int(cat['years'].split('~')[0])
    hi = datetime.date.today().year
    행, 해별 = [], {}
    for y in range(lo, hi + 1):
        try:
            rows, total = fetch(code, {'fyr': str(y)}, key)
        except SystemExit as e:   # 「해당 데이터 없음」도 RESULT 로 온다
            if '없' in str(e) or 'INFO-200' in str(e):
                continue
            raise
        if not rows:
            continue
        if len(rows) != total:
            raise SystemExit(f'{code} {y}: {len(rows)}/{total} — 건수가 안 맞는다')
        해별[str(y)] = len(rows)
        행 += rows
        print(f'  {y}: {len(rows):,}행')
    return 행, 해별


def main():
    key = load_key()
    if not key:
        raise SystemExit('LOFIN_KEY 가 없다')
    cats = {c['code']: c for c in json.load(open(os.path.join(ROOT, 'data', 'lofin365_146.json'), encoding='utf-8'))}
    codes = sys.argv[1:] or list(ITEMS)
    os.makedirs(os.path.join(ROOT, 'data', 'items'), exist_ok=True)
    for code in codes:
        print(f'{code} — 재료표 {ITEMS.get(code, "?")}번 · {cats[code]["name"][:40]}')
        행, 해별 = 받기(code, cats[code], key)
        out = {'코드': code, '이름': cats[code]['name'], '재료표': ITEMS.get(code),
               '만든날': datetime.date.today().isoformat(), '해별': 해별, '행': 행}
        path = os.path.join(ROOT, 'data', 'items', f'{code}.json.gz')
        with gzip.open(path, 'wt', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False)
        print(f'  → data/items/{code}.json.gz · {len(행):,}행 · {os.path.getsize(path) // 1024:,} KB')


if __name__ == '__main__':
    main()
