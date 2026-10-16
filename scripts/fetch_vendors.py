# 나라장터 **조달업체 등록 내역** — 등록된 업체 전부의 「이름·사업자번호·소재 시군구」.
#
#   python scripts/fetch_vendors.py            빈 해 + 올해(늘 다시) → data/vendors/{해}.json.gz
#   python scripts/fetch_vendors.py 2024 --다시  그 해만 다시
#
# 왜 — fetch_bizno.py 의 사전은 **나라장터 계약에 나온 업체만** 안다. 지자체하고만 거래하는
#      동네 업체는 번호가 안 붙는다. 이 목록은 계약이 없어도 **등록만 한 업체까지** 다 있다.
#      (2026-10-16 사용자가 「조달청_나라장터 사용자정보 서비스」 활용신청.)
# ⚠️ 조회 기준은 **등록일**이고 **한 번에 1년까지**다 — 더 길면 `07 입력범위값 초과 에러`.
#    1990~2026 약 90만 곳, 999줄씩 950쪽쯤. 폐업·취소한 업체는 안 나온다고 안내돼 있다.
# ⚠️ 대표자·전화·상세주소는 담지 않는다 — 저장소가 공개다. 묶기에 필요한 칸만.
# ⛔ **「이름 → 번호」 사전에 섞지 않는다**(2026-10-16 잼, 2025년 계약). 그래서 data/bizno/ 밖에 둔다.
#    그냥 섞으면 같은 이름이 늘어 번호 붙는 금액이 36.4% → 32.8% 로 준다. 계약 사전에 없는 이름만 보태면
#    41.3% 로 늘지만 **틀린 짝이 많아 보인다** — 1억 미만 계약에서 업체가 계약한 지자체와 같은 시·도인 몫이
#    지금 붙는 것 73% · 새로 붙는 것 47%. 이름만 같은 다른 업체에 붙는 것으로 본다.
# ⭐ **쓰는 길은 사업자번호로 찾기다** — 나라장터 계약·수의계약(data/수의계약, R2)의 업체 번호는 98% 가
#    여기서 찾아진다(금액 88~90%). 업체 소재 시군구로 「동네 업체가 받은 몫」을 셀 수 있다.

import datetime
import gzip
import json
import os
import sys
import time
import urllib.parse
import urllib.request

import keys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'vendors')
URL = 'https://apis.data.go.kr/1230000/ao/UsrInfoService02/getPrcrmntCorpBasicInfo02'
첫해 = 1980
한쪽 = 999                                   # fetch_bizno 와 같다 — 1000 이면 10건만 온다


def 부르기(키, 해, 쪽, 되풀이=4):
    q = {'serviceKey': 키, 'pageNo': 쪽, 'numOfRows': 한쪽, 'type': 'json', 'inqryDiv': '1',
         'inqryBgnDt': f'{해}01010000', 'inqryEndDt': f'{해}12312359'}
    마지막 = None
    for n in range(되풀이):
        try:
            with urllib.request.urlopen(URL + '?' + urllib.parse.urlencode(q), timeout=120) as r:
                d = json.loads(r.read().decode('utf-8', errors='replace').replace(키, '<키>'))
        except Exception as e:
            마지막 = e
            time.sleep(3 * (n + 1))
            continue
        틀림 = d.get('nkoneps.com.response.ResponseError') or d.get('OpenAPI_ServiceResponse')
        if 틀림:      # 하루 한도(22)도 여기로 온다 — 받은 해는 남고 내일 잇는다
            raise SystemExit(f'{해}년 {쪽}쪽 거절 — {json.dumps(틀림, ensure_ascii=False)[:200]}')
        몸 = d['response']['body']
        줄 = 몸.get('items') or []
        return (줄 if isinstance(줄, list) else [줄]), int(몸.get('totalCount') or 0)
    raise SystemExit(f'네 번 다 실패({해}년 {쪽}쪽): {마지막!r}')


def 한해(키, 해):
    모음, 쪽, 전체 = [], 1, 1
    while len(모음) < 전체:
        줄, 전체 = 부르기(키, 해, 쪽)
        if not 줄:
            break
        모음 += [{'이름': r.get('corpNm', '').strip(), '번호': r.get('bizno', '').strip(),
                 '지역코드': r.get('rgnCd', ''), '지역': r.get('rgnNm', ''),
                 '업무': r.get('corpBsnsDivNm', ''), '본사': r.get('hdoffceDivNm', ''),
                 '등록일': (r.get('rgstDt') or '')[:10]} for r in 줄]
        쪽 += 1
    if len(모음) != 전체:
        print(f'  ⚠️ {해}년 {len(모음):,}줄 받음 / 전체 {전체:,}')
    return 모음


def main():
    키 = keys.키읽기('DATA_GO_KR_KEY')
    올해 = datetime.date.today().year
    인자 = [a for a in sys.argv[1:] if a.isdigit()]
    해들 = [int(a) for a in 인자] or range(첫해, 올해 + 1)
    os.makedirs(OUT, exist_ok=True)
    for 해 in 해들:
        f = os.path.join(OUT, f'{해}.json.gz')
        if os.path.exists(f) and 해 < 올해 and '--다시' not in sys.argv:
            continue
        줄 = 한해(키, 해)
        if not 줄 and 해 < 1990:
            continue                                # 빈 옛 해는 파일을 안 만든다
        with gzip.GzipFile(f, 'wb', mtime=0) as g:   # mtime=0 — 같은 내용이면 깃이 안 바뀐 걸로 본다
            g.write(json.dumps(줄, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        print(f'{해}  {len(줄):,}곳', flush=True)


if __name__ == '__main__':
    main()
