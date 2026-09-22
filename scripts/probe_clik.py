# 지방의정포털 CLIK 키 확인 + 무엇이 얼마나 있나 세어 보기.
#
#   python scripts/probe_clik.py              네 갈래 규모와 최신 자료를 찍는다
#   python scripts/probe_clik.py --상세       상세 응답에 실제로 오는 칸을 전수로 찍는다
#
# ⚠️ 여기서 부르는 횟수도 **하루 1,000회에 같이 들어간다.** 기본 4회, --상세 면 7회다.
#    수집기(`fetch_clik.py`)는 하루 900회까지만 쓰도록 해 뒀으니 그 나머지 몫이다.
#
# ⚠️ **명세와 실제가 어긋나는 데가 있다**(2026-09-22 실측). --상세 로 확인할 것:
#    - 의원 목록은 명세에 `PPRTY` 인데 실제로는 `PPRTY_NM` 이 온다
#    - 의원 상세는 명세에 10칸인데 실제로는 15칸이 온다(생년월일·학력·경력·선거구 따위)
#    - 의원 상세 `OFFM_TLPHON`(사무실 전화) 칸에 **사진 경로**가 들어 있다
#    - 날짜가 없는 칸은 빈 값이 아니라 `19700101` 로 온다

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

import keys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 'https://clik.nanet.go.kr/openapi'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')

갈래 = [
    ('회의록', 'minutes.do', 'list'),
    ('의안', 'bill.do', 'list'),
    ('의원', 'assemblyinfo.do', 'list'),
    ('정책정보', 'policyinfoList.do', None),
]


def 키읽기():
    return keys.키읽기('CLIK_KEY')


def 부르기(끝점, 인자):
    url = f'{BASE}/{끝점}?' + urllib.parse.urlencode(인자)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode('utf-8', 'replace'))
    return d[0] if isinstance(d, list) and d else d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--상세', action='store_true')
    args = ap.parse_args()
    키 = 키읽기()

    첫줄 = {}
    print('갈래별 규모 (searchKeyword 없이 전수)')
    for 이름, 끝점, 보기 in 갈래:
        인자 = {'key': 키, 'type': 'json', 'startCount': 0, 'listCount': 1,
                'searchType': 'ALL', 'searchKeyword': ''}
        if 보기:
            인자['displayType'] = 보기
        d = 부르기(끝점, 인자)
        if d.get('RESULT_CODE') != 'SUCCESS':
            print(f'  {이름}: ✗ {d.get("RESULT_CODE")} {d.get("RESULT_MESSAGE")}')
            continue
        L = d.get('LIST') or []
        줄 = L[0].get('ROW', L[0]) if L else {}
        첫줄[이름] = 줄
        날짜 = 줄.get('MTG_DE') or 줄.get('ITNC_DE') or 줄.get('CDATE') or '-'
        곳 = 줄.get('RASMBLY_NM') or 줄.get('SITENM') or '-'
        print(f'  {이름}: {d["TOTAL_COUNT"]:,}건 · 맨 앞 {날짜} {곳}')
        print(f'      목록 칸 {len(줄)}개 — {", ".join(줄.keys())}')

    호출수 = len(갈래)
    if args.상세:
        print()
        print('상세 응답에 실제로 오는 칸 (명세와 어긋나는 데가 있다)')
        상세갈래 = [('회의록', 'minutes.do'), ('의안', 'bill.do'),
                    ('의원', 'assemblyinfo.do')]
        for 이름, 끝점 in 상세갈래:
            docid = (첫줄.get(이름) or {}).get('DOCID')
            if not docid:
                print(f'  {이름}: 목록에서 DOCID 를 못 받아 건너뜀')
                continue
            d = 부르기(끝점, {'key': 키, 'type': 'json',
                             'displayType': 'detail', 'docid': docid})
            호출수 += 1
            칸 = {k: v for k, v in d.items()
                  if k not in ('SERVICE', 'RESULT_CODE', 'RESULT_MESSAGE')}
            print(f'  {이름} ({docid}) — 칸 {len(칸)}개')
            for k, v in 칸.items():
                s = str(v).replace(chr(10), ' ')
                꼬리 = f'   …(총 {len(str(v)):,}자)' if len(str(v)) > 70 else ''
                print(f'      {k:18} {s[:70]}{꼬리}')

    print()
    print(f'이번에 {호출수}회 불렀다 (하루 한도 1,000회).')


if __name__ == '__main__':
    main()
