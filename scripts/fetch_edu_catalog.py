# 지방교육재정알리미 자료 목록을 훑어 **서비스명 표**를 만든다.
#
#   python scripts/fetch_edu_catalog.py           639종을 훑는다
#   python scripts/fetch_edu_catalog.py --다시    이미 만든 표를 버리고 새로
#
# 왜 — 알리미는 자료마다 부르는 영문 이름(`requestType`)이 따로다. 그 목록이
#      공개 화면에 없다(`dataSetList.do` 는 500, 목록 내려받기는 404).
#      ⭐ **자료 화면의 Open API 탭이 부르는 창구**에 그 이름이 들어 있다 —
#      `POST /portal/service/openInfColViewPopUp.do` 에 `infId`·`srvCd=A`.
#      한 번 부르면 서비스명·요청인자·출력칸이 같이 오므로 한 판에 끝난다.
#
# ⚠️ **메타의 `dsId`(`VW_...`)는 서비스명이 아니다.** 그 이름으로 부르면 오류가 아니라
#    홈페이지 HTML 이 온다. 반드시 `apiRes` 에서 꺼낸 `requestType` 을 쓸 것.
# ⚠️ 이 표를 만드는 데는 인증키가 필요 없다. 자료를 실제로 받을 때만 `EDU_ALIMI_KEY` 를 쓴다.
#
# 결과 : data/eduinfo_catalog.json — `scripts/probe_edu.py` 와 앞으로의 수집기가 여기서 이름을 찾는다.

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 'https://eduinfo.go.kr'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')


def 부르기(길, 몸, 되풀이=3):
    자료 = urllib.parse.urlencode(몸).encode('utf-8')
    끝 = None
    for n in range(되풀이):
        try:
            req = urllib.request.Request(
                BASE + 길, data=자료,
                headers={'User-Agent': UA,
                         'Content-Type': 'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode('utf-8', errors='replace')
        except Exception as e:
            끝 = e
            time.sleep(2 * (n + 1))
    raise SystemExit(f'세 번 다 실패({길}): {끝!r}')


def 자료목록():
    """원본시스템별 나무에서 (infId, 이름) 을 뽑는다."""
    본문 = 부르기('/portal/service/openInfScolOrgAll.do',
                {'searchCd': '3', 'searchWord': '', 'pIndex': 1, 'pSize': 50})
    나무 = json.loads(본문)['tsData']['data']
    칸 = re.findall(r'<li[^>]*id="([^"]+)"[^>]*title="([^"]*)"', 나무)
    나온 = []
    본것 = set()
    for i, t in 칸:
        if len(i) > 20 and i not in 본것:      # 분류 마디가 아니라 자료인 것만
            본것.add(i)
            나온.append((i, t.strip()))
    return 나온


def 한자료(infId):
    본문 = 부르기('/portal/service/openInfColViewPopUp.do',
                {'infId': infId, 'srvCd': 'A'})
    try:
        d = json.loads(본문)
    except json.JSONDecodeError:
        return None
    m = re.search(r'requestType=([A-Za-z0-9_]+)', 본문)
    칸 = lambda 열쇠: [c.get('colNm') for c in (d.get(열쇠) or [])
                     if isinstance(c, dict) and c.get('colNm')]
    첫 = (d.get('sampleUri') or [{}])[0]
    return {'infId': infId,
            'name': d.get('infNm') or 첫.get('infNm') or '',
            'service': m.group(1) if m else '',
            'dsId': next((c.get('dsId') for c in (d.get('printVal') or [])
                          if isinstance(c, dict) and c.get('dsId')), ''),
            'args': 칸('reqVar'),
            'cols': 칸('printVal')}


def main():
    다시 = '--다시' in sys.argv
    길 = os.path.join(ROOT, 'data', 'eduinfo_catalog.json')
    if os.path.exists(길) and not 다시:
        raise SystemExit(f'이미 있다: data/eduinfo_catalog.json (다시 만들려면 --다시)')

    목록 = 자료목록()
    print(f'■ 자료 {len(목록)}종 · 하나씩 서비스명을 꺼낸다')

    표 = []
    없음 = []
    시작 = time.time()
    for i, (infId, 이름) in enumerate(목록, 1):
        한 = 한자료(infId)
        if 한 is None:
            없음.append(이름)
        else:
            if not 한['name']:
                한['name'] = 이름
            if not 한['service']:
                없음.append(한['name'])
            표.append(한)
        if i % 50 == 0 or i == len(목록):
            print(f'  … {i}/{len(목록)} · {time.time() - 시작:.0f}초')
        time.sleep(0.12)

    표.sort(key=lambda r: r['name'])
    with open(길, 'w', encoding='utf-8') as f:
        json.dump(표, f, ensure_ascii=False, indent=1)

    열린것 = [r for r in 표 if r['service']]
    인자있 = [r for r in 열린것 if r['args']]
    print(f'\n  자료 {len(표)}종 · **API 가 있는 것 {len(열린것)}종**'
          f' · 고르는 인자가 있는 것 {len(인자있)}종')
    print(f'  저장 data/eduinfo_catalog.json '
          f'({os.path.getsize(길) / 1024:,.0f} KB · {time.time() - 시작:.0f}초)')
    if 없음:
        print(f'  ⚠ 서비스명을 못 꺼낸 것 {len(없음)}종 — {", ".join(없음[:6])}'
              f'{" …" if len(없음) > 6 else ""}')


if __name__ == '__main__':
    main()
