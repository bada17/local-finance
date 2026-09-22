# 클린아이(지방공기업 경영정보) 수집기 — 공기업·공단이 어떻게 굴러가나.
#
#   python scripts/fetch_cleaneye.py 2024            그 해
#   python scripts/fetch_cleaneye.py 2015 2024       그 해부터 그 해까지
#   python scripts/fetch_cleaneye.py 2024 --다시     이미 받아 둔 것을 지우고 새로
#
# 왜 — 자치단체 살림에서 공기업·공단은 회계가 따로라 예산·결산 자료에 잘 안 잡힌다.
#      부채와 당기순이익이 여기 있다.
#
# ⚠️ **끝점 번호와 길 이름이 엇갈린다.** 끝점은 `3` 인데 오퍼레이션은 `2` 다
#    (`openApiMngInfo3/openXmlMngInfo2`). 번호를 맞춰 부르면 `12 해당 오픈API 서비스가 없거나 폐기됨`.
# ⚠️ **`type` 이 필수다.** 빼면 `11 NOTEXISTPARAMETER_ERROR(type)` — 키 탓으로 헷갈리기 쉽다.
# ⚠️ 데이터포맷이 XML 이다. `type=json` 을 줘도 XML 이 온다.
# ⚠️ 키는 `.env` 의 `DATA_GO_KR_KEY` — API 마다 활용신청이 따로다(이 셋은 2026-09-22 승인).

import gzip
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import keys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 'https://apis.data.go.kr/B551982'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')

# 이름 · 끝점 · 길 — 번호가 엇갈리는 것을 그대로 적어 둔다
갈래 = [
    ('경영정보', 'openApiMngInfo3', 'openXmlMngInfo2'),
    ('경영성과', 'openApiMngResult3', 'openXmlMngResult2'),
    ('주요경영분석지표', 'openApiMajorMngIdx2', 'openXmlMajorMngIdx2'),
]


def 키읽기():
    # 환경변수 먼저, 그다음 .env — 깃허브 액션에서는 Secrets 가 환경변수로 온다
    return keys.키읽기('DATA_GO_KR_KEY')


def 부르기(끝점, 길, 키, 해, 쪽, 개수=1000, 되풀이=3):
    q = {'serviceKey': 키, 'pageNo': 쪽, 'numOfRows': 개수,
         'ac_year': 해, 'type': 'xml'}
    url = f'{BASE}/{끝점}/{길}?' + urllib.parse.urlencode(q)
    끝 = None
    for n in range(되풀이):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                본문 = r.read().decode('utf-8', errors='replace')
            break
        except Exception as e:
            끝 = e
            time.sleep(2 * (n + 1))
    else:
        raise SystemExit(f'세 번 다 실패({길}): {끝!r}')

    본문 = 본문.replace(키, '<키>')          # 키는 어떤 일이 있어도 남기지 않는다
    뿌리 = ET.fromstring(본문)
    # 머리 이름이 갈래마다 다르다(`openXmlMngInfo-header` 꼴) — 꼬리로 찾는다
    머리 = next((e for e in 뿌리 if e.tag.endswith('-header')), None)
    코드 = 머리.findtext('resultCode') if 머리 is not None else None
    if 코드 not in (None, '0', '00'):
        raise SystemExit(f'{길} 거절 — {코드} {머리.findtext("resultMsg")}')

    줄들 = [{e.tag: (e.text or '').strip() for e in it} for it in 뿌리.iter('item')]
    전체 = 뿌리.findtext('.//totalCount')
    return 줄들, int(전체) if 전체 else 0


def 한갈래(끝점, 길, 키, 해):
    담 = []
    쪽 = 1
    전체 = None
    while True:
        줄, 전체 = 부르기(끝점, 길, 키, 해, 쪽)
        담.extend(줄)
        if not 줄 or len(담) >= 전체:
            break
        쪽 += 1
        time.sleep(0.2)
    return 담, 전체


def main():
    해들 = [a for a in sys.argv[1:] if a.isdigit()]
    if not 해들:
        raise SystemExit('쓰는 법: fetch_cleaneye.py <연도> [끝연도] [--다시]')
    처음 = int(해들[0])
    끝해 = int(해들[1]) if len(해들) > 1 else 처음
    다시 = '--다시' in sys.argv
    키 = 키읽기()

    낼곳 = os.path.join(ROOT, 'data', 'cleaneye')
    os.makedirs(낼곳, exist_ok=True)

    for 해 in range(처음, 끝해 + 1):
        길이름 = os.path.join(낼곳, f'{해}.json.gz')
        if os.path.exists(길이름) and not 다시:
            print(f'{해} — 이미 있다 (다시 받으려면 --다시)')
            continue
        담 = {}
        셈 = []
        for 이름, 끝점, 길 in 갈래:
            줄, 전체 = 한갈래(끝점, 길, 키, 해)
            담[이름] = 줄
            셈.append(f'{이름} {len(줄):,}/{전체:,}')
            time.sleep(0.2)
        with gzip.open(길이름, 'wt', encoding='utf-8') as f:
            json.dump(담, f, ensure_ascii=False)
        기관 = {r.get('ENT_NAME') for 줄 in 담.values() for r in 줄}
        크기 = os.path.getsize(길이름) / 1024
        print(f'{해} — {" · ".join(셈)} · 기관 {len(기관)}곳 '
              f'· data/cleaneye/{해}.json.gz ({크기:,.0f} KB)')


if __name__ == '__main__':
    main()
