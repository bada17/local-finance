# 지방의정포털 CLIK **상세** 수집기 — 정책정보 본문 · 의안 처리 경과.
#
#   python scripts/fetch_clik_detail.py               하루 남은 한도로 이어받는다
#   python scripts/fetch_clik_detail.py --limit 50    이번에 50회만
#   python scripts/fetch_clik_detail.py --selftest    고르는 규칙만 시험한다(호출 0회)
#
# 왜 — 2026-10-01 사용자 결정: "지방정책정보, 의안은 지금 받자. 회의록은 나중에."
#      목록(fetch_clik.py)을 다 받은 뒤로 목록 수집은 하루 수십 회만 쓴다. 나머지 900여 회가
#      날마다 그냥 사라지고 있어서, 그 몫으로 상세를 한 건씩 받는다.
#
# ⭐ **한 건에 1회다.** 기간(2022-07-01~) 안 정책정보 약 3.6만 + 의안 약 18.5만 = 약 22만 회,
#    하루 900회면 **약 240일**. 정책정보(본문이 있다)를 먼저 끝내고 의안으로 넘어간다.
#    목록 수집기가 날마다 붙이는 새 건도 저절로 따라 받는다(받을 것 = 목록 − 받은 것).
#
# 받아 보고 안 것 (2026-10-01, 10건씩 표본)
# - **의안 상세의 `BI_OUTLINE`(의안 요지)은 10건 모두 비어 있었다.** 상세가 더 주는 것은
#   위원회·본회의 상정/처리 날짜와 결과, 이송·공포, 원안 파일 이름이다. 건당 약 0.7KB.
# - 정책정보 상세는 `EXTRACTHTML`(본문 HTML)과 원문 `URL`. 건당 약 1.3KB.
#   기상상황·선석배정표 같은 일일 보고도 섞여 있다 — 거르는 것은 쓰는 쪽에서 한다.
#
# ⭐ **아직 처리 안 된 의안은 다시 받는다.** 상세의 처리 결과는 나중에 채워진다 — 한 번 받고 끝내면
#    「미처리」로 굳는다(2026-09-22 사용자 — "업데이트되는 자료를 받아오는 형식으로"). 본회의 처리일·
#    철회일이 없는 의안은 받은 지 `다시볼날`이 지나면 새 건을 다 받은 뒤에 다시 부른다.
#
# 담는 곳 — `data/clik/상세/<갈래>_<받은날>_<n>.json.gz`. **한 번 쓴 파일은 다시 열지 않는다**
#    (덮어쓰면 옛 판이 날마다 저장소 역사에 쌓인다). 다시 받은 의안은 새 파일에 들어가고,
#    읽을 때 같은 DOCID 는 **받은날이 늦은 것**이 이긴다.
#    ⚠️ 하위 폴더라 데이터 지도(`data/clik/*.json.gz`)에는 안 잡힌다 — 일부러 그렇게 뒀다.
#    ⭐ **이 폴더는 저장소에 안 올라간다 — Cloudflare R2(버킷 local-finance-raw, clik/상세)에 산다**(2026-10-01).
#       봇이 받기 전에 R2 에서 내려받고(scripts/r2_sync.sh down), 받은 뒤 새 파일을 올린다(up).
#       로컬에서 돌리면 R2 에 있는 것을 모르니 **로컬에서는 --selftest 말고는 돌리지 말 것.**
#
# ⚠️ 호출 수는 목록 수집기와 **같은 장부**(`data/clik/상태.json` 의 `날짜별호출`)에 적는다.
#    봇에서는 목록 수집 **뒤에** 돈다 — 목록이 쓰고 남은 만큼만 쓴다.

import argparse
import glob
import gzip
import json
import os
import sys
import time

from fetch_clik import 받는곳, 기본시작, 날짜성한가, 부르기, 상태읽기, 상태쓰기, 오늘, 키읽기

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

상세곳 = os.path.join(받는곳, '상세')
하루한도 = 1000
남길몫 = 60          # 손으로 확인하거나 내부 표본(clik_action.py, 예비 20)이 쓸 몫
조각크기 = 500       # 이만큼 모이면 파일로 쓴다 — 중간에 끊겨도 받은 것은 남는다
다시볼날 = 30        # 처리 안 된 의안을 다시 받기까지
실패한도 = 3         # 이만큼 실패한 DOCID 는 더 부르지 않는다(날마다 한도만 먹는다)

# 이름 · 끝점 · 목록 날짜칸 — **이 차례대로** 받는다
갈래들 = [
    ('정책정보', 'policyinfoDetail.do', 'CDATE'),
    ('의안', 'bill.do', 'ITNC_DE'),
]


def 목록DOCID(갈래, 날짜칸, 시작날):
    """목록 조각에서 기간 안 DOCID — 오래된 것부터(받는 차례가 날마다 같게)."""
    줄들 = []
    for 경로 in glob.glob(os.path.join(받는곳, f'{갈래}_*.json.gz')):
        with gzip.open(경로, 'rt', encoding='utf-8') as f:
            줄들 += [(str(r.get(날짜칸) or ''), r['DOCID']) for r in json.load(f) if r.get('DOCID')]
    본 = set()
    out = []
    for 날, d in sorted(줄들):
        if d not in 본 and 날짜성한가(날[:8]) and 날[:8] >= 시작날:
            본.add(d)
            out.append(d)
    return out


def 받은것(갈래):
    """DOCID → 가장 늦게 받은 줄."""
    out = {}
    for 경로 in sorted(glob.glob(os.path.join(상세곳, f'{갈래}_*.json.gz'))):
        with gzip.open(경로, 'rt', encoding='utf-8') as f:
            for r in json.load(f):
                옛 = out.get(r['DOCID'])
                if not 옛 or r['_받은날'] >= 옛['_받은날']:
                    out[r['DOCID']] = r
    return out


def 끝난의안(r):
    return 날짜성한가(str(r.get('PLNMT_PROCESS_DE') or '')[:8]) or \
        날짜성한가(str(r.get('DELETE_DT') or '')[:8])


def 고르기(갈래, 목록, 받은, 실패, 오늘날):
    """받을 차례 — 새 건 먼저, 그다음 다시 볼 의안(받은 지 오래된 것부터)."""
    새 = [d for d in 목록 if d not in 받은 and 실패.get(d, 0) < 실패한도]
    다시 = []
    if 갈래 == '의안':
        기준 = time.strftime('%Y-%m-%d', time.localtime(
            time.mktime(time.strptime(오늘날, '%Y-%m-%d')) - 다시볼날 * 86400))
        다시 = sorted((r['_받은날'], d) for d, r in 받은.items()
                      if not 끝난의안(r) and r['_받은날'] <= 기준 and 실패.get(d, 0) < 실패한도)
        다시 = [d for _, d in 다시]
    return 새 + 다시


def 조각쓰기(갈래, 줄들, 오늘날):
    os.makedirs(상세곳, exist_ok=True)
    n = 0
    while os.path.exists(경로 := os.path.join(상세곳, f'{갈래}_{오늘날}_{n}.json.gz')):
        n += 1
    with gzip.GzipFile(경로, 'wb', mtime=0) as f:
        f.write(json.dumps(줄들, ensure_ascii=False).encode('utf-8'))


def 한갈래(갈래, 끝점, 날짜칸, 키, 상태, 예산, 시작날):
    목록 = 목록DOCID(갈래, 날짜칸, 시작날)
    받은 = 받은것(갈래)
    실패 = 상태.setdefault('상세실패', {}).setdefault(갈래, {})
    차례 = 고르기(갈래, 목록, 받은, 실패, 오늘())
    셈 = {'호출': 0, '받음': 0, '실패': 0}
    담을, 새로 = [], []
    까닭 = '받을 것 다 받음'
    for d in 차례:
        if 셈['호출'] >= 예산:
            까닭 = '예산 다 씀'
            break
        인자 = {'key': 키, 'type': 'json', 'docid': d}
        if 끝점 == 'bill.do':
            인자['displayType'] = 'detail'
        r, 오류 = 부르기(끝점, 인자)
        셈['호출'] += 1
        상태['날짜별호출'][오늘()] = 상태['날짜별호출'].get(오늘(), 0) + 1
        if 오류 == 'ERROR09':
            까닭 = '일별 트래픽 초과(ERROR09)'
            break
        if r is None or r.get('DOCID') != d:
            실패[d] = 실패.get(d, 0) + 1
            셈['실패'] += 1
            continue
        실패.pop(d, None)
        r = {k: v for k, v in r.items() if k not in ('SERVICE', 'RESULT_CODE', 'RESULT_MESSAGE')}
        r['_받은날'] = 오늘()
        담을.append(r)
        새로.append(r)
        셈['받음'] += 1
        if len(담을) >= 조각크기:
            조각쓰기(갈래, 담을, 오늘())
            담을 = []
            상태쓰기(상태)
    if 담을:
        조각쓰기(갈래, 담을, 오늘())
    남은 = max(0, len(차례) - 셈['받음'] - 셈['실패'])
    칸 = 상태.setdefault('상세', {}).setdefault(갈래, {})
    받은수 = len(받은.keys() | {r['DOCID'] for r in 새로})
    칸.update({'목록': len(목록), '받은곳': 받은수, '남은차례': 남은, '마지막수집': 오늘(), '멈춘까닭': 까닭})
    print(f'  {갈래}: {셈["호출"]}회 불러 {셈["받음"]:,}건 받음 · 실패 {셈["실패"]} — '
          f'목록 {len(목록):,}건 중 {칸["받은곳"]:,}건 받음, 남은 차례 {남은:,} ({까닭})')
    return 셈['호출'], 까닭


def selftest():
    받은 = {'A': {'_받은날': '2026-08-01'},                                   # 미처리 · 오래됨 → 다시
            'B': {'_받은날': '2026-08-01', 'PLNMT_PROCESS_DE': '20260801'},   # 처리됨 → 끝
            'C': {'_받은날': '2026-09-25'},                                   # 미처리 · 최근 → 아직
            'D': {'_받은날': '2026-08-01', 'DELETE_DT': '20260801000000'}}    # 철회 → 끝
    assert 고르기('의안', ['A', 'B', 'N1', 'N2', 'X'], 받은, {'X': 3}, '2026-10-01') == ['N1', 'N2', 'A']
    assert 고르기('정책정보', ['A', 'N1'], 받은, {}, '2026-10-01') == ['N1']
    assert not 끝난의안({'PLNMT_PROCESS_DE': '19700101'})
    print('selftest ok')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=하루한도)
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    키 = 키읽기()
    상태 = 상태읽기()
    쓴것 = 상태['날짜별호출'].get(오늘(), 0)
    예산 = min(args.limit, 하루한도 - 남길몫 - 쓴것)
    print(f'오늘 이미 {쓴것}회 불렀다 → 상세는 {max(0, 예산)}회까지 (예비 {남길몫}회 남김)')
    for 갈래, 끝점, 날짜칸 in 갈래들:
        if 예산 <= 0:
            break
        쓴, 까닭 = 한갈래(갈래, 끝점, 날짜칸, 키, 상태, 예산, 기본시작)
        예산 -= 쓴
        상태쓰기(상태)
        if 까닭.startswith('일별'):
            break
    상태쓰기(상태)


if __name__ == '__main__':
    main()
