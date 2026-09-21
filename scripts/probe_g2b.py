# 나라장터(조달청) 계약정보를 눌러 본다 — **사업자등록번호**가 여기 있다.
#
#   python scripts/probe_g2b.py                하루치를 불러 칸과 내용을 본다
#   python scripts/probe_g2b.py 20260902        그날 것
#
# 왜 — 지방재정365 계약현황(`WCEGCF`)에는 **업체명만** 있고 사업자번호가 없다(출력 13칸 전부 확인).
#      그래서 「(주)○○」와 「주식회사 ○○」가 갈라진다. 번호가 있어야 제대로 묶인다.
#
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


def 키읽기():
    p = os.path.join(ROOT, '.env')
    for 줄 in open(p, encoding='utf-8'):
        if 줄.startswith('DATA_GO_KR_KEY='):
            return 줄.split('=', 1)[1].strip()
    raise SystemExit('.env 에 DATA_GO_KR_KEY 가 없다')


def 부르기(갈래, 날, 키, 쪽=1, 개수=50):
    q = {
        'serviceKey': 키, 'pageNo': 쪽, 'numOfRows': 개수, 'type': 'json',
        'inqryDiv': '1',                      # 1 = 계약체결일자로 찾기
        'inqryBgnDate': 날, 'inqryEndDate': 날,
    }
    url = f'{BASE}/{길[갈래]}?' + urllib.parse.urlencode(q, safe='%')
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        본문 = r.read().decode('utf-8', errors='replace')
    try:
        return json.loads(본문), ''
    except json.JSONDecodeError:
        return None, 본문[:300]


def main():
    날 = sys.argv[1] if len(sys.argv) > 1 else '20260902'
    키 = 키읽기()
    for 갈래 in 길:
        d, 날것 = 부르기(갈래, 날, 키)
        if d is None:
            print(f'[{갈래}] JSON 이 아니다 — {날것}')
            continue
        몸 = (d.get('response') or {}).get('body') or {}
        머리 = (d.get('response') or {}).get('header') or {}
        rows = 몸.get('items') or []
        if isinstance(rows, dict):
            rows = rows.get('item') or []
        print(f'[{갈래}] {머리.get("resultMsg", "?")} · 전체 {몸.get("totalCount", "?")}건 · 받은 것 {len(rows)}')
        if not rows:
            continue
        r = rows[0]
        print(f'   칸 {len(r)}개')
        번호칸 = [k for k in r if 'bizno' in k.lower() or 'corp' in k.lower() or 'cntrctr' in k.lower()]
        print(f'   업체·번호로 보이는 칸: {번호칸}')
        for k in list(r)[:40]:
            print(f'      {k:<28} {str(r[k])[:44]}')
        break


if __name__ == '__main__':
    main()
