# 계약현황(WCEGCF)을 다시 받아, 그사이 새로 올라오거나 고쳐진 줄만 쌓는다.
#
#   python scripts/refresh_contracts.py                     최근 120일 + 옛 날짜 30분의 1 (날마다 봇)
#   python scripts/refresh_contracts.py 20260901 20261103   그 사이만
#   python scripts/refresh_contracts.py --분 60             60분 되면 받은 데까지 남기고 멈춘다
#
# 왜 — 지자체는 계약을 며칠~몇 달 뒤에 올리고, 올린 뒤에도 고친다. `collect_daily.py` 는 어제 치를 한 번만
#    받으므로 그 뒤 것을 영영 못 봤다. 2026-11-04 실측: 저장본이 9월 35%·10월 48% 모자람, 2026 금액 바뀐 줄
#    2만여 줄, 2024년 날짜도 몇 줄씩 바뀐다. 등록일로는 못 묻는다(ERROR-300) — 날마다 다시 받아 견주는 수밖에 없다.
#
# ⭐ 하루 파일은 안 건드리고 `data/contracts_late/<받은 날>.json.gz` 에 변경분만 쌓는다.
#    하루 파일을 덮어쓰면 옛 판이 저장소 역사에 통째로 남는다(150일 × 150KB = 날마다 20MB 남짓).
#    변경분은 눌러서 한 줄 55바이트쯤이다.
# ⚠️ 계약 원본을 읽을 때는 `data/contracts/` 만 보지 말고 **합친하루()** 로 읽을 것.
# ⚠️ 등록일 칸만 바뀐 줄은 안 쌓는다(날마다 수천 줄이 그렇게 바뀐다) — 그 두 칸은 처음 받은 값일 수 있다.
# ⚠️ 저쪽에서 사라진 줄은 지우지 않고 세기만 한다(2026-11-04 까지 0). 받다 끊긴 것과 구별이 안 된다.
# ponytail: 2023 이전(data/contracts_old, R2)은 안 다시 본다. 늦은 고침이 쌓여 문제가 되면 시작일을 당길 것.

import collections
import glob
import gzip
import json
import os
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backfill_contracts import 시작  # noqa: E402
from collect_daily import save_gz  # noqa: E402
from fetch_lofin import fetch, load_key  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
등록칸 = {'rgstr_dt', 'data_crt_ymd'}
금액칸 = 'ctrt_tot_tott_amt'
내리실패한도 = 3


def 하루길(날, root=ROOT):
    return os.path.join(root, 'data', 'contracts', f'{날}.json.gz')


def 늦은길(받은날, root=ROOT):
    return os.path.join(root, 'data', 'contracts_late', f'{받은날}.json.gz')


def 읽기(길):
    with gzip.open(길, 'rt', encoding='utf-8') as f:
        return json.load(f)


def 열쇠(r):
    """저장본 327만 줄에서 하루 안에 겹치거나 번호가 빈 줄이 없다(2026-11-04 확인)."""
    return r.get('laf_cd'), r.get('ctrt_ldgr_mng_no')


def 늦은줄읽기(root=ROOT):
    """{계약일: {열쇠: 줄}} — 받은 날 차례로 덮어 가장 늦게 받은 줄이 남는다."""
    모음 = {}
    for 길 in sorted(glob.glob(늦은길('*', root))):
        for r in 읽기(길):
            모음.setdefault(str(r.get('smz_ctrt_ymd')), {})[열쇠(r)] = r
    return 모음


def 합친하루(날, 늦은, root=ROOT):
    """하루 파일에 그날의 변경분을 얹은 줄들 — 계약 원본은 이것으로 읽는다."""
    줄들 = 읽기(하루길(날, root)) if os.path.exists(하루길(날, root)) else []
    덧 = dict(늦은.get(날) or {})
    합 = [덧.pop(열쇠(r), r) for r in 줄들]
    return 합 + list(덧.values())


def 고를날(오늘, 최근=120, 바퀴=30):
    """어제부터 거슬러 최근 며칠 전부 + 그보다 옛날은 `바퀴` 일에 한 번씩 돌아가며."""
    날들 = []
    d = 오늘 - timedelta(days=1)
    나이 = 0
    while d >= 시작:
        if 나이 < 최근 or d.toordinal() % 바퀴 == 오늘.toordinal() % 바퀴:
            날들.append(d.strftime('%Y%m%d'))
        d -= timedelta(days=1)
        나이 += 1
    return 날들


def 내용(r):
    return {k: v for k, v in r.items() if k not in 등록칸}


def 다시받기(날들, 받은날, 불러오기, root=ROOT, 쉬기=0.15, 초=None, 저장마다=20):
    """날들을 차례로 다시 받아 변경분을 `contracts_late/<받은날>` 에 쌓고 셈을 돌려준다."""
    셈 = collections.Counter()
    늦은 = 늦은줄읽기(root)
    길 = 늦은길(받은날, root)
    이번 = {(str(r.get('smz_ctrt_ymd')), 열쇠(r)): r for r in 읽기(길)} if os.path.exists(길) else {}
    마감 = None if 초 is None else time.time() + 초
    내리실패 = 0
    덜씀 = False

    def 쓰기():
        nonlocal 덜씀
        if 덜씀:
            save_gz(길, [이번[k] for k in sorted(이번, key=str)])
            덜씀 = False

    for i, 날 in enumerate(날들):
        if 내리실패 >= 내리실패한도 or (마감 is not None and time.time() >= 마감):
            셈['못 본 날'] = len(날들) - i
            break
        if not os.path.exists(하루길(날, root)):
            셈['파일 없는 날'] += 1       # 채우기(backfill_contracts) 몫 — 파일이 없으면 요약도 그날을 안 읽는다
            continue
        try:
            줄들, 전체 = 불러오기(날)
        except SystemExit as e:           # fetch_lofin 은 오류를 SystemExit 로 올린다
            if 'INFO-200' not in str(e):
                print(f'  ⚠ {날} 못 받음 — {str(e)[:120]}', flush=True)
                셈['실패'] += 1
                내리실패 += 1
                continue
            줄들, 전체 = [], 0
        if len(줄들) != 전체:
            print(f'  ⚠ {날} {len(줄들)}/{전체} 덜 받음 — 안 쌓음', flush=True)
            셈['실패'] += 1
            내리실패 += 1
            continue
        내리실패 = 0
        셈['본 날'] += 1
        셈['저쪽 줄'] += 전체

        알던 = {열쇠(r): r for r in 합친하루(날, 늦은, root)}
        새것 = {열쇠(r): r for r in 줄들}
        셈['사라진 줄'] += len(set(알던) - set(새것))
        for k, r in 새것.items():
            옛 = 알던.get(k)
            if 옛 is None:
                셈['새 줄'] += 1
            elif 내용(옛) == 내용(r):
                continue
            else:
                셈['고쳐진 줄'] += 1
                셈['금액 바뀐 줄'] += 옛.get(금액칸) != r.get(금액칸)
            이번[(날, k)] = r
            늦은.setdefault(날, {})[k] = r
            덜씀 = True
        if (i + 1) % 저장마다 == 0:
            쓰기()                        # 시간이 다 돼 잘려도 받은 만큼은 남는다
        if 쉬기:
            time.sleep(쉬기)
    쓰기()
    return 셈


def main():
    args = sys.argv[1:]
    분 = None
    if '--분' in args:
        i = args.index('--분')
        분 = float(args[i + 1])
        del args[i:i + 2]
    key = load_key()
    if not key:
        raise SystemExit('LOFIN_KEY 가 없다')

    오늘 = date.today()
    if args:
        부터, 까지 = args[0], args[1] if len(args) > 1 else args[0]
        d = date(int(까지[:4]), int(까지[4:6]), int(까지[6:]))
        끝 = date(int(부터[:4]), int(부터[4:6]), int(부터[6:]))
        날들 = []
        while d >= 끝:
            날들.append(d.strftime('%Y%m%d'))
            d -= timedelta(days=1)
    else:
        날들 = 고를날(오늘)
    print(f'계약 다시 받기 {len(날들)}일 ({날들[-1]} ~ {날들[0]})', flush=True)

    시각 = time.time()
    받은날 = 오늘.strftime('%Y%m%d')
    셈 = 다시받기(날들, 받은날, lambda 날: fetch('WCEGCF', {'smz_ctrt_ymd': 날}, key),
              초=None if 분 is None else 분 * 60)

    길 = 늦은길(받은날)
    크기 = os.path.getsize(길) / 1024 if os.path.exists(길) else 0
    print(f"본 날 {셈['본 날']} · 저쪽 {셈['저쪽 줄']:,}줄 · 새 줄 {셈['새 줄']:,} · 고쳐진 줄 {셈['고쳐진 줄']:,}"
          f"(금액 {셈['금액 바뀐 줄']:,}) · 사라진 줄 {셈['사라진 줄']:,} · 실패 {셈['실패']} · 못 본 날 {셈['못 본 날']}"
          f" · 파일 없는 날 {셈['파일 없는 날']} · 오늘 변경분 {크기:,.0f}KB · {(time.time() - 시각) / 60:.0f}분")
    return 1 if 셈['실패'] else 0


if __name__ == '__main__':
    sys.exit(main())
