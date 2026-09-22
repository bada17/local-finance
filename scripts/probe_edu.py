# 지방교육재정알리미 집행내역을 눌러 본다 — **받는 쪽 이름**이 여기 있다.
#
#   python scripts/probe_edu.py             2024년치를 본다
#   python scripts/probe_edu.py 2023        그 해 것
#   python scripts/probe_edu.py 2024 B10    그 해, 그 교육청 것(B10 = 서울)
#
# 왜 — 계약도 보조금도 대개 「준 쪽」만 보인다. 이 자료에는 **보조사업자**가 이름으로 나온다.
#      (결산통합공시 > 재정운영 > 지방보조금(민간이전), 17개 시·도교육청, 연 1회)
#
# ⚠️ 서비스명은 `opclClsgExecList` 다. 메타에 적힌 `dsId`(VW_CLSG04090101)로 부르면 HTML 이 온다.
#    서비스명을 잘못 적으면 **오류가 아니라 홈페이지 HTML** 이 돌아온다 — 이름부터 의심할 것.
# ⚠️ `openapi.eduinfo.go.kr` 은 **HTTPS 가 안 열린다.** http 로 부른다.
#    HTTPS 가 필요하면 `https://eduinfo.go.kr/portal/openApi.do` 를 쓰는데, 이쪽은
#    JSON 을 **문자열로 한 번 더 싸서** 준다(두 번 풀어야 한다).
# ⚠️ 한 번에 1,000건까지다(336 오류).
# ⚠️ 키는 `.env` 의 `EDU_ALIMI_KEY` — **저장소에 적지 말 것.**

import json
import os
import sys
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 'http://openapi.eduinfo.go.kr/openApi.do'
서비스 = 'opclClsgExecList'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'


def 키읽기():
    p = os.path.join(ROOT, '.env')
    for 줄 in open(p, encoding='utf-8'):
        if 줄.startswith('EDU_ALIMI_KEY='):
            값 = 줄.split('=', 1)[1].strip()
            if 값:
                return 값
    raise SystemExit('.env 에 EDU_ALIMI_KEY 가 비어 있다')


def 부르기(키, 해='', 교육청='', 쪽=1, 개수=100):
    q = {'requestType': 서비스, 'key': 키, 'type': 'json',
         'pIndex': 쪽, 'pSize': min(개수, 1000)}
    if 해:
        q['FSCL_Y'] = 해
    if 교육청:
        q['SD_EDU_OFFC_DIV'] = 교육청
    req = urllib.request.Request(BASE + '?' + urllib.parse.urlencode(q),
                                 headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        본문 = r.read().decode('utf-8', errors='replace')
    본문 = 본문.replace(키, '<키>')          # 키는 어떤 일이 있어도 찍지 않는다
    if 본문.lstrip().startswith('<'):
        raise SystemExit('HTML 이 왔다 — 서비스명이 틀렸을 때 이렇게 된다.\n  ' + 본문[:160])
    return json.loads(본문)


def main():
    해 = sys.argv[1] if len(sys.argv) > 1 else '2024'
    교육청 = sys.argv[2] if len(sys.argv) > 2 else ''
    키 = 키읽기()

    d = 부르기(키, 해, 교육청)
    말 = (d.get('RESULT') or {}).get('MESSAGE', '?')
    rows = d.get('RESULT_LIST') or []
    print(f'■ {해}년 집행내역{" · " + 교육청 if 교육청 else ""} — {말}')
    print(f'   전체 {d.get("TOTAL_CNT")}건 · 받은 것 {len(rows)}\n')
    if not rows:
        return

    print(f'   칸 {len(rows[0])}개 — {", ".join(rows[0])}\n')
    # 「총계」 줄은 교육청별 합이라 받는 쪽 이름이 없다. 갈라서 센다
    총계 = [r for r in rows if not (r.get('AID_BIZR') or '').strip()]
    이름있음 = [r for r in rows if (r.get('AID_BIZR') or '').strip()]
    print(f'   받는 쪽 이름이 있는 줄 {len(이름있음)} · 「총계」처럼 이름 없는 줄 {len(총계)}\n')

    for r in 이름있음[:10]:
        준액 = r.get('AID_AMT') or 0
        정산 = r.get('FINAL_STTL_AMT') or 0
        남 = 준액 - 정산
        꼬리 = f' (남은 것 {남:,})' if 남 else ''
        print(f'   {r.get("SD_EDU_OFFC_DIV_NM", ""):<8} {str(r.get("AID_BIZR"))[:22]:<24} '
              f'{준액:>14,}{꼬리}')
        print(f'   {"":<8} └ {str(r.get("AID_BIZ_NM"))[:52]}')


if __name__ == '__main__':
    main()
