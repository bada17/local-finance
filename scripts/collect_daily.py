# 날마다 도는 수집. 깃허브 액션이 새벽에 부른다.
#
#   python scripts/collect_daily.py            어제 것
#   python scripts/collect_daily.py 20260918   그날 것
#
# 두 가지를 받는다.
#
#   계약현황(WCEGCF) — 하루 1,300~2,300건. 작아서 원본 그대로 날마다 쌓는다.
#                      업체명·계약방법·금액·하도급유무가 들어 있는, 이 사이트의 승부처.
#   세부사업별 세출(QWGJK) — 그 달 누계로 44만 행. 원본은 깃에 안 넣고 집계만 남긴다.
#                          ep_amt 가 누계라 날마다 원본을 쌓을 이유도 없다.
#                          원본이 필요하면 fetch_lofin.py 로 8분이면 다시 받는다.
#
# ⚠️ 한 번 실패했다고 지난 파일을 지우지 말 것. 못 받은 것은 없어졌다는 뜻이 아니다.

import gzip
import json
import os
import sys
from collections import defaultdict
from datetime import date, timedelta

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lofin import fetch, load_key  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def save_gz(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with gzip.open(tmp, 'wt', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)          # 다 받은 뒤에만 갈아끼운다
    return os.path.getsize(path)


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    return os.path.getsize(path)


def contracts(day, key):
    """계약현황 하루치를 원본 그대로."""
    rows, total = fetch('WCEGCF', {'smz_ctrt_ymd': day}, key)
    if len(rows) != total:
        print(f'  ⚠ 계약현황 {len(rows)}/{total} — 덜 받았다. 저장 안 함')
        return False
    path = os.path.join(ROOT, 'data', 'contracts', f'{day}.json.gz')
    size = save_gz(path, rows)
    su = sum(1 for r in rows if '수의' in (r.get('ctrt_mth_nm') or ''))
    amt = sum(r.get('ctrt_tot_tott_amt') or 0 for r in rows)
    print(f'  계약현황 {len(rows):,}건 (수의 {su:,}건) · 계약액 {amt:,}원 · {size/1024:,.0f}KB')
    return True


def spending(month, key):
    """세부사업별 세출 그 달 누계를 받아 자치단체 x 분야로 집계."""
    rows, total = fetch('QWGJK', {'fyr': month[:4], 'exe_ymd': month}, key)
    if len(rows) != total:
        print(f'  ⚠ 세출 {len(rows)}/{total} — 덜 받았다. 저장 안 함')
        return False

    agg = defaultdict(lambda: defaultdict(int))
    for r in rows:
        k = (r['laf_cd'], r['laf_hg_nm'], r['wa_laf_hg_nm'], r.get('fld_cd') or '', r.get('fld_nm') or '')
        a = agg[k]
        a['사업수'] += 1
        a['예산현액'] += r.get('bdg_cash_amt') or 0
        a['집행누계'] += r.get('ep_amt') or 0
        a['국비'] += r.get('bdg_ntep') or 0
        a['시도비'] += r.get('capep') or 0
        a['시군구비'] += r.get('sggep') or 0

    out = []
    for (laf_cd, laf_nm, wa_nm, fld_cd, fld_nm), a in sorted(agg.items()):
        out.append({'laf_cd': laf_cd, 'laf_hg_nm': laf_nm, 'wa_laf_hg_nm': wa_nm,
                    'fld_cd': fld_cd, 'fld_nm': fld_nm, **a})

    path = os.path.join(ROOT, 'data', 'spending', f'{month}.json')
    size = save_json(path, out)
    print(f'  세출 원본 {len(rows):,}행 → 집계 {len(out):,}행 '
          f'({len({o["laf_cd"] for o in out})}곳) · {size/1024:,.0f}KB')
    return True


def main():
    key = load_key()
    if not key:
        raise SystemExit('LOFIN_KEY 가 없다. .env 나 깃허브 Secrets 에 넣을 것')

    if len(sys.argv) > 1:
        day = sys.argv[1]
    else:
        day = (date.today() - timedelta(days=1)).strftime('%Y%m%d')
    month = day[:6]

    print(f'수집 {day} (키 있음)')
    ok = contracts(day, key)
    ok = spending(month, key) and ok
    print('끝' if ok else '⚠ 덜 받은 것이 있다')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
