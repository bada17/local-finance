# 계약현황(WCEGCF)을 과거로 거슬러 채운다.
#
#   python scripts/backfill_contracts.py                      2024-01-01 부터 어제까지
#   python scripts/backfill_contracts.py 20240101 20241231    그 사이만
#   python scripts/backfill_contracts.py --limit 200          200일치만 받고 멈춘다
#
# ⚠️ 계약은 **날짜로만** 뽑힌다(`smz_ctrt_ymd` 필수, 달·해로는 안 된다).
#    그래서 하루씩 부르는 수밖에 없고, 안 받아 두면 나중에 소급이 안 된다.
#
# **이어받기가 된다.** 이미 받아 둔 날은 건너뛴다. 트래픽 제한이 있을 수 있으니
# `--limit` 로 조금씩 나눠 받아 채워도 되고, 끊겨도 다시 부르면 그다음부터 간다.
# 자료가 없는 날(주말·공휴일)도 빈 파일로 남겨 다시 안 부른다.
#
# 결과: data/contracts/<YYYYMMDD>.json.gz (원본 그대로, 눌러서)

import gzip
import json
import os
import sys
import time
from datetime import date, timedelta

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lofin import fetch, load_key  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'contracts')
시작 = date(2024, 1, 1)          # 3년치 — 2024·2025·2026


def 하루(day, key):
    """그날 전국 계약을 받아 저장한다. (받은 건수, 불렀나)"""
    path = os.path.join(OUT, f'{day}.json.gz')
    if os.path.exists(path):
        return None, False
    try:
        rows, total = fetch('WCEGCF', {'smz_ctrt_ymd': day}, key)
    except SystemExit:
        rows, total = [], 0      # INFO-200 — 그날은 계약이 없다
    if total and len(rows) != total:
        print(f'  {day} {len(rows)}/{total} 덜 받았다 — 저장 안 함')
        return None, True

    os.makedirs(OUT, exist_ok=True)
    tmp = path + '.tmp'
    with gzip.open(tmp, 'wt', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False)
    os.replace(tmp, path)
    return len(rows), True


def main():
    args = [a for a in sys.argv[1:]]
    limit = None
    if '--limit' in args:
        i = args.index('--limit')
        limit = int(args[i + 1])
        del args[i:i + 2]

    부터 = args[0] if len(args) > 0 else 시작.strftime('%Y%m%d')
    까지 = args[1] if len(args) > 1 else (date.today() - timedelta(days=1)).strftime('%Y%m%d')

    key = load_key()
    if not key:
        raise SystemExit('LOFIN_KEY 가 없다')

    d = date(int(부터[:4]), int(부터[4:6]), int(부터[6:]))
    끝 = date(int(까지[:4]), int(까지[4:6]), int(까지[6:]))
    print(f'계약 채우기 {부터} ~ {까지}' + (f' · 이번엔 {limit}일까지' if limit else ''))

    부른날 = 건너뛴날 = 0
    행 = 0
    시각 = time.time()
    while d <= 끝:
        day = d.strftime('%Y%m%d')
        n, 불렀나 = 하루(day, key)
        if 불렀나:
            부른날 += 1
            행 += n or 0
            if 부른날 % 20 == 0:
                쓴시간 = time.time() - 시각
                print(f'  {day} 까지 {부른날}일 · {행:,}건 · {쓴시간/60:.0f}분')
            time.sleep(0.15)
        else:
            건너뛴날 += 1
        if limit and 부른날 >= limit:
            print(f'  {limit}일 채웠다. 다음엔 {day} 다음날부터 이어간다')
            break
        d += timedelta(days=1)

    있는날 = len([f for f in os.listdir(OUT) if f.endswith('.json.gz')]) if os.path.isdir(OUT) else 0
    크기 = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT)) / 1024 / 1024
    print(f'새로 {부른날}일 ({행:,}건) · 이미 있던 {건너뛴날}일 · '
          f'모두 {있는날}일 {크기:,.1f}MB · {(time.time()-시각)/60:.0f}분')


if __name__ == '__main__':
    main()
