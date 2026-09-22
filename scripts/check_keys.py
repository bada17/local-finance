# 인증키가 다 들어와 있나, 실제로 열리나 본다.
#
#   python scripts/check_keys.py           있나 없나만 본다 (호출 0회)
#   python scripts/check_keys.py --호출    진짜로 한 번씩 불러 본다 (키마다 1회)
#
# 왜 — 「점검표의 있음」과 「쓸 수 있음」이 다르다. 그리고 **`.env` 에 있는 것과
#      저장소 Secrets 에 있는 것도 다르다.** 봇은 Secrets 만 본다.
#      2026-09-22 에 일곱 스크립트가 `.env` 만 읽고 있어서, Secrets 에 키를 넣어도
#      봇에서는 못 읽는 상태였다. 그걸 다시 겪지 않으려고 만든다.
#
# ⚠️ **키 값은 절대 찍지 않는다.** 길이와 있나 없나만 찍는다. 공개 저장소다.
# ⚠️ `--호출` 은 진짜 트래픽을 쓴다. CLIK 은 하루 1,000회 한도가 있으니 남발하지 말 것.

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
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')

# 키 · 무엇에 쓰나 · 이 키로 도는 수집기
쓰임 = {
    'LOFIN_KEY': ('지방재정365 146종 — 지표·세출·세입·계약',
                  'fetch_indicators · fetch_series · fetch_revenue · collect_daily · '
                  'backfill_contracts · build_ongoing'),
    'DATA_GO_KR_KEY': ('나라장터 계약정보(사업자번호) · 클린아이 · 목록조회',
                       'fetch_bizno · fetch_cleaneye · fetch_datagokr_all · scan_datagokr'),
    'EDU_ALIMI_KEY': ('지방교육재정알리미 — 보조사업자 이름이 나오는 드문 자료',
                      'probe_edu · (수집기는 아직 없다)'),
    'CLIK_KEY': ('지방의정포털 — 회의록·의안·의원·정책정보',
                 'fetch_clik · probe_clik'),
    'OPENFISCAL_KEY': ('열린재정 (기재부) — 중앙정부 총량. 후순위',
                       '(아직 안 쓴다)'),
}


def 한번불러보기(이름, 키):
    """키마다 제일 가벼운 호출을 한 번. (됐나, 한마디)."""
    try:
        if 이름 == 'LOFIN_KEY':
            url = ('https://www.lofin365.go.kr/lf/hub/DADBC?' +
                   urllib.parse.urlencode({'Key': 키, 'Type': 'json',
                                           'pIndex': 1, 'pSize': 1}))
        elif 이름 == 'DATA_GO_KR_KEY':
            url = ('https://apis.data.go.kr/1230000/ao/CntrctInfoService/'
                   'getCntrctInfoListThng?' +
                   urllib.parse.urlencode({'serviceKey': 키, 'pageNo': 1,
                                           'numOfRows': 1, 'type': 'json',
                                           'inqryDiv': '1',
                                           'inqryBgnDt': '202601020000',
                                           'inqryEndDt': '202601022359'},
                                          safe='%'))
        elif 이름 == 'EDU_ALIMI_KEY':
            url = ('http://openapi.eduinfo.go.kr/openApi.do?' +
                   urllib.parse.urlencode({'requestType': 'opclClsgExecList',
                                           'key': 키, 'type': 'json',
                                           'pIndex': 1, 'pSize': 1}))
        elif 이름 == 'CLIK_KEY':
            url = ('https://clik.nanet.go.kr/openapi/assemblyinfo.do?' +
                   urllib.parse.urlencode({'key': 키, 'type': 'json',
                                           'displayType': 'list',
                                           'startCount': 0, 'listCount': 1,
                                           'searchType': 'ALL',
                                           'searchKeyword': ''}))
        else:
            return None, '부를 데를 안 정했다'

        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=40) as r:
            본문 = r.read().decode('utf-8', 'replace')
        본문 = 본문.replace(키, '<키>')      # 무슨 일이 있어도 키는 안 찍는다

        if 이름 == 'CLIK_KEY':
            d = json.loads(본문)
            d = d[0] if isinstance(d, list) and d else d
            코드 = d.get('RESULT_CODE')
            if 코드 == 'SUCCESS':
                return True, f'의원 {d.get("TOTAL_COUNT", 0):,}건'
            return False, f'{코드} {d.get("RESULT_MESSAGE", "")}'
        if '<키>' in 본문 or 'SERVICE_KEY' in 본문 or 'SERVICE ERROR' in 본문:
            return False, '키를 거부했다'
        if 본문.lstrip().startswith('<'):
            return False, 'JSON 이 아니라 HTML/XML 이 왔다 (활용신청 확인)'
        json.loads(본문)
        return True, '응답 옴'
    except Exception as e:
        return False, f'{type(e).__name__}: {str(e)[:60]}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--호출', action='store_true',
                    help='진짜로 한 번씩 불러 본다 (키마다 1회, 트래픽을 쓴다)')
    args = ap.parse_args()

    env파일 = os.path.exists(os.path.join(ROOT, '.env'))
    print(f'.env 파일 — {"있다" if env파일 else "없다 (봇이면 정상)"}')
    print()
    print(f'{"키":<17}{"내 PC":<9}{"환경변수":<10}{"쓰임"}')
    print('-' * 78)

    없는것 = []
    for 이름, (무엇, 누가) in 쓰임.items():
        환경 = bool((os.environ.get(이름) or '').strip())
        값 = keys.키읽기(이름, 필수=False)
        표시 = f'✔ {len(값)}자' if 값 else '✗ 없음'
        if not 값:
            없는것.append(이름)
        print(f'{이름:<17}{표시:<9}{"✔" if 환경 else "-":<10}{무엇}')
        print(f'{"":<36}{누가}')

    if args.호출:
        print()
        print('진짜로 불러 본다 (키마다 1회)')
        for 이름 in 쓰임:
            값 = keys.키읽기(이름, 필수=False)
            if not 값:
                print(f'  {이름:<17} — 건너뜀 (키가 없다)')
                continue
            됐나, 한마디 = 한번불러보기(이름, 값)
            표 = '✔' if 됐나 else ('—' if 됐나 is None else '✗')
            print(f'  {이름:<17} {표} {한마디}')

    print()
    if 없는것:
        print(f'⚠️ 비어 있는 키 {len(없는것)}개 — {", ".join(없는것)}')
    else:
        print('✔ 아는 키가 다 들어와 있다')
    print()
    print('키는 **두 곳**에 넣는다:')
    print('  ① 내 PC — 저장소 맨 위 .env  (.env.example 을 베껴 쓸 것. 깃에 안 올라간다)')
    print('  ② 봇    — github.com/bada17/local-finance')
    print('            → Settings → Secrets and variables → Actions → New repository secret')
    print('  ⚠️ 이름을 똑같이 쓸 것. 봇은 .env 를 못 보고 Secrets 만 본다.')


if __name__ == '__main__':
    main()
