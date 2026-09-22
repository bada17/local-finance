# 나라장터(조달청) 계약정보를 눌러 본다 — **사업자등록번호**가 여기 있다.
#
#   python scripts/probe_g2b.py                하루치를 불러 칸과 내용을 본다
#   python scripts/probe_g2b.py 20260902        그날 것
#
# 왜 — 지방재정365 계약현황(`WCEGCF`)에는 **업체명만** 있고 사업자번호가 없다(출력 13칸 전부 확인).
#      그래서 「(주)○○」와 「주식회사 ○○」가 갈라진다. 번호가 있어야 제대로 묶인다.
#
# ⚠️ 날짜 인자는 `inqryBgnDt`/`inqryEndDt` 이고 **12자리(YYYYMMDDHHMM)** 다.
#    `inqryBgnDate`(8자리)로 부르면 `08 필수값 입력 에러`, 12자리를 안 채우면 `06 DATE Format 에러`.
# ⚠️ data.go.kr 은 API 마다 활용신청을 따로 해야 한다. 계약정보만 신청해 뒀다.
# ⚠️ 키는 `.env` 의 `DATA_GO_KR_KEY` — **저장소에 적지 말 것.**

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
BASE = 'https://apis.data.go.kr/1230000/ao/CntrctInfoService'
# 물품·용역·공사·외자 네 갈래로 나뉜다
길 = {
    '물품': 'getCntrctInfoListThng',
    '용역': 'getCntrctInfoListServc',
    '공사': 'getCntrctInfoListCnstwk',
}
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'

# corpList 한 칸의 차례 — `^` 로 붙어 온다. 맨 끝이 사업자등록번호다.
업체칸 = ['차례', '구분', '단독·공동', '업체명', '대표자', '국가', '지분율',
        '상호', '(빈칸)', '사업자등록번호']


def 키읽기():
    p = os.path.join(ROOT, '.env')
    for 줄 in open(p, encoding='utf-8'):
        if 줄.startswith('DATA_GO_KR_KEY='):
            값 = 줄.split('=', 1)[1].strip()
            if 값:
                return 값
    raise SystemExit('.env 에 DATA_GO_KR_KEY 가 비어 있다')


def 부르기(갈래, 날, 키, 쪽=1, 개수=50):
    q = {
        'serviceKey': 키, 'pageNo': 쪽, 'numOfRows': 개수, 'type': 'json',
        'inqryDiv': '1',                      # 1 = 계약체결일자로 찾기
        'inqryBgnDt': 날 + '0000', 'inqryEndDt': 날 + '2359',
    }
    url = f'{BASE}/{길[갈래]}?' + urllib.parse.urlencode(q, safe='%')
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        본문 = r.read().decode('utf-8', errors='replace')
    본문 = 본문.replace(키, '<키>')          # 키는 어떤 일이 있어도 찍지 않는다
    try:
        return json.loads(본문), ''
    except json.JSONDecodeError:
        return None, 본문[:300]


def 업체들(줄):
    """corpList 를 쪼개 [(업체명, 대표자, 사업자등록번호), ...] 로 돌려준다."""
    덩이 = str(줄.get('corpList') or '').strip().lstrip('[').rstrip(']')
    나온 = []
    for 조각 in 덩이.split(']|['):
        칸 = 조각.split('^')
        if len(칸) < 10:
            continue
        나온.append((칸[3].strip(), 칸[4].strip(), 칸[9].strip()))
    return 나온


def main():
    날 = sys.argv[1] if len(sys.argv) > 1 else '20260902'
    키 = 키읽기()
    print(f'■ {날} 계약체결분\n')
    통 = []
    for 갈래 in 길:
        d, 날것 = 부르기(갈래, 날, 키)
        if d is None:
            print(f'[{갈래}] JSON 이 아니다 — {날것}')
            continue
        틀린 = d.get('nkoneps.com.response.ResponseError') or d.get('OpenAPI_ServiceResponse')
        if 틀린:
            print(f'[{갈래}] 거절당했다 — {json.dumps(틀린, ensure_ascii=False)[:200]}')
            continue
        몸 = (d.get('response') or {}).get('body') or {}
        머리 = (d.get('response') or {}).get('header') or {}
        rows = 몸.get('items') or []
        if isinstance(rows, dict):
            rows = rows.get('item') or []
        if isinstance(rows, dict):
            rows = [rows]

        번호붙은 = [줄 for 줄 in rows if any(b for _, _, b in 업체들(줄))]
        print(f'[{갈래}] {머리.get("resultMsg", "?")} · 전체 {몸.get("totalCount", "?")}건 '
              f'· 받은 것 {len(rows)} · 사업자번호 붙은 것 {len(번호붙은)}')
        통.append((갈래, 몸.get('totalCount'), len(rows), len(번호붙은)))
        for 줄 in rows[:3]:
            이름 = str(줄.get('cntrctNm', ''))[:34]
            기관 = 줄.get('cntrctInsttNm', '')
            print(f'      · {기관} — {이름}')
            for 업, 대표, 번호 in 업체들(줄):
                print(f'          {번호 or "(번호 없음)":<12} {업[:24]:<26} 대표 {대표}')
        print()

    if 통:
        print('── 간추림')
        for 갈래, 전체, 받은, 붙은 in 통:
            몫 = f'{붙은 / 받은 * 100:.0f}%' if 받은 else '—'
            print(f'   {갈래}  전체 {전체}건 · 표본 {받은}건 중 번호 붙은 것 {붙은} ({몫})')


if __name__ == '__main__':
    main()
