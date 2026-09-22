# 공공데이터포털을 **전수로 훑어** 지방재정과 닿는 자료를 찾는다.
#
#   python scripts/scan_datagokr.py             낱말 한 벌을 훑는다
#   python scripts/scan_datagokr.py 감사 청렴    그 낱말만
#   python scripts/scan_datagokr.py --다시      이미 만든 표를 버리고 새로
#
# 왜 — 검색 **화면**을 긁으면 낱말마다 첫 10건밖에 못 본다. 그래서 「없다」고 말할 수가 없다.
#      목록조회 API 는 오픈API 17,035건 · 파일데이터 211,981건을 **다** 준다.
#      ⭐ **「우리가 안 본 자료」를 눈대중이 아니라 숫자로 말하기 위한 표다.**
#
# ⚠️ 키는 `.env` 의 `DATA_GO_KR_KEY`. 목록조회서비스(15077093)에 활용신청이 돼 있어야 한다
#    (2026-09-22 승인). 안 돼 있으면 `-3 등록되지 않은 서비스` 가 온다.
# ⚠️ 제목만 본다(`cond[title::LIKE]`). 제목에 안 든 말은 못 잡는다 — **이 표의 한계다.**
#
# 결과 : data/datagokr_scan.json

import json
import os
import sys
import time
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 'https://api.odcloud.kr/api/15077093/v1'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')

낱말들 = ['지방재정', '지방보조금', '보조금', '지방세', '세외수입', '교부세',
       '세입', '세출', '예산', '결산', '기금', '지방채', '채무', '공유재산',
       '계약', '수의계약', '입찰', '낙찰', '지방공기업', '출자출연',
       '감사', '청렴', '투자심사', '주민참여예산', '정보공개', '업무추진비',
       '지방의회', '재정공시', '중기지방재정', '원가회계']

# 이미 쥐고 있거나 이미 아는 것 — 새로 찾은 것과 가르기 위해
아는것 = {
    '15129427': '나라장터 계약정보(받음)',
    '15056798': '클린아이 경영정보(받음)', '15058242': '클린아이 주요경영분석지표(받음)',
    '15057730': '클린아이 경영성과(받음)', '15061217': '지방공기업 시도코드',
    '15097584': '국고보조금 정보', '15077093': '목록조회서비스(이 표를 만든 것)',
    '15138713': '지방재정365 지방보조금', '15138714': '지방재정365 지방보조금(2020)',
    '15138715': '지방재정365 지방보조금(2021~)', '15058377': '지방재정365 지방보조금비율',
    '15138708': '지방재정365 예산서', '15058182': '지방재정365 세입세출현황',
}


def 부르기(길, q, 되풀이=3):
    url = f'{BASE}/{길}?' + urllib.parse.urlencode(q, safe=':[]')
    끝 = None
    for n in range(되풀이):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            끝 = e
            time.sleep(2 * (n + 1))
    raise SystemExit(f'세 번 다 실패({길}): {끝!r}')


def 훑기(길, 키, 낱말):
    담 = []
    쪽 = 1
    while True:
        d = 부르기(길, {'page': 쪽, 'perPage': 1000, 'serviceKey': 키,
                     'cond[title::LIKE]': 낱말})
        줄 = d.get('data') or []
        담.extend(줄)
        맞 = d.get('matchCount', 0)
        if not 줄 or len(담) >= 맞:
            break
        쪽 += 1
        time.sleep(0.2)
    return 담


def main():
    다시 = '--다시' in sys.argv
    고른낱말 = [a for a in sys.argv[1:] if not a.startswith('--')] or 낱말들
    길이름 = os.path.join(ROOT, 'data', 'datagokr_scan.json')
    if os.path.exists(길이름) and not 다시:
        raise SystemExit('이미 있다: data/datagokr_scan.json (다시 만들려면 --다시)')

    키 = ''
    for 줄 in open(os.path.join(ROOT, '.env'), encoding='utf-8'):
        if 줄.startswith('DATA_GO_KR_KEY='):
            키 = 줄.split('=', 1)[1].strip()
    if not 키:
        raise SystemExit('.env 에 DATA_GO_KR_KEY 가 비어 있다')

    모음 = {}
    셈 = []
    시작 = time.time()
    for 낱 in 고른낱말:
        본 = 0
        for 갈래, 길 in [('API', 'open-data-list'), ('파일', 'file-data-list')]:
            for r in 훑기(길, 키, 낱):
                열쇠 = (갈래, str(r.get('list_id')), str(r.get('operation_seq') or ''))
                if 열쇠 in 모음:
                    모음[열쇠]['낱말'].append(낱)
                    continue
                모음[열쇠] = {
                    '갈래': 갈래, 'list_id': str(r.get('list_id')),
                    '이름': r.get('list_title') or r.get('title') or '',
                    '기관': r.get('org_nm') or '', '분류': r.get('new_category_nm') or '',
                    '끝점': r.get('end_point_url') or '', '고침': r.get('updated_at') or '',
                    '인자': r.get('request_param_nm') or '',
                    '낱말': [낱],
                }
                본 += 1
        셈.append((낱, 본))
        print(f'  {낱:<10} 새로 {본:>5}건 · 누적 {len(모음):,}')
        time.sleep(0.1)

    표 = sorted(모음.values(), key=lambda r: (r['갈래'], r['기관'], r['이름']))
    with open(길이름, 'w', encoding='utf-8') as f:
        json.dump(표, f, ensure_ascii=False, indent=1)

    api = [r for r in 표 if r['갈래'] == 'API']
    새것 = [r for r in api if r['list_id'] not in 아는것]
    기관 = {}
    for r in api:
        기관[r['기관']] = 기관.get(r['기관'], 0) + 1
    print(f'\n  모두 {len(표):,}건 (API {len(api):,} · 파일 {len(표) - len(api):,})')
    print(f'  이 가운데 우리가 아는 것 {len(api) - len(새것)}건 · '
          f'**API 인데 한 번도 안 본 것 {len(새것):,}건**')
    print(f'  저장 data/datagokr_scan.json '
          f'({os.path.getsize(길이름) / 1024:,.0f} KB · {time.time() - 시작:.0f}초)')
    print('\n  API 를 많이 내놓은 기관 10')
    for 이름, n in sorted(기관.items(), key=lambda t: -t[1])[:10]:
        print(f'     {n:>5}건  {이름[:40]}')


if __name__ == '__main__':
    main()
