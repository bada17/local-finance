# 지방의정포털 CLIK 수집기 — 243개 지방의회의 회의록·의안·의원·지방정책정보.
#
#   python scripts/fetch_clik.py                    네 갈래를 이어받는다 (기본 900회)
#   python scripts/fetch_clik.py --갈래 회의록      한 갈래만
#   python scripts/fetch_clik.py --limit 200        이번에 200회만 부른다
#   python scripts/fetch_clik.py --기간 20100101 20260630   기간을 바꾼다(기본 20220701~오늘)
#   python scripts/fetch_clik.py --다시 --깊이 900  처음부터 (받아 둔 것을 지운다)
#   python scripts/fetch_clik.py --selftest         가짜 CLIK 으로 시험한다(호출 0회)
#   python scripts/fetch_clik.py --의회목록         243곳 코드표만 다시 굽는다 (호출 0회)
#
# 왜 — 숫자 옆에 "그때 누가 무슨 말을 했나"를 붙일 수 있는 유일한 자료다.
#      계약·보조금은 얼마 썼는지만 말하고, 회의록은 왜 그렇게 썼는지를 말한다.
#
# ⚠️ **하루 1,000회 · 한 번에 100건이 박혀 있다.** 이게 이 갈래의 전부를 규정한다.
#    상태 파일에 **날짜별 호출 수**를 적어 두고, 같은 날 다시 돌려도 한도를 안 넘게 한다.
#
# ⭐ **그래서 기간을 자른다 — 2022-07-01 부터 오늘까지.**
#    시작은 **제8회 지방선거 임기 시작**이고, 끝은 **못 박지 않는다** — 제9회로 뽑힌
#    제10대 의회 자료가 지금도 쌓이는 중이라서다. 목록 전수는 217만 건이라 22일이
#    걸리는데, 이 기간만이면 약 35만 건 = **4일**이다.
#    (2026-09-22 실측 — 의안 177,787 · 회의록 약 133,000 · 정책정보 약 37,000.)
#    더 옛 자료가 필요해지면 `--기간` 으로 넓히면 된다. 코드에 해를 박아 두지 않았다.
#
# ⚠️ **상세(displayType=detail)는 전수로 못 받는다.** 한 건에 한 번이라 34만 회 = 340일이다.
#    상세는 사용자가 고른 범위만 따로 받는다(이 수집기는 목록만 받는다).
#    → 정책정보·의안 상세는 `fetch_clik_detail.py` 가 남은 한도로 받는다(2026-10-01). 회의록 상세는 2026-07-01 뒤 것만, 맨 먼저(2026-11-03).
#
# **갈래마다 기간을 자르는 방법이 다르다.**
# ⭐⭐ 2026-11-04 사용자 「데이터가 빠지지 않는 것이 중요해」 — **「어디까지 받았나」 위치만 믿으면 빠진다.**
#    의회는 자료를 늦게 올리고, 늦게 올린 것은 이미 지나간 자리에 끼어든다. 봇은 「실패 없음·끝까지 받음」인데
#    의안 7,194건 · 회의록 약 2,400건(7/16 뒤) · 정책정보 8~9월 자리 98% 가 비어 있었다(CLIK 에 직접 물어 맞춤).
# - **의안**만 서버가 걸러 준다(`itncStartDt`·`itncEndDt`). 기간 → 해 → 달로 건수를 견주고 **모자란 달만 다시 받는다.**
#   위치를 안 쓰니 끊겨도 다음에 스스로 메운다. 변한 게 없으면 1회.
# - **회의록·정책정보**는 거르개가 없다. **최신순으로 내려가며** 기간 밖은 버리고,
#   ① 날마다 최근 `앞머리날수` 치를 처음부터 다시 본다(늦게 올라온 것 · 수집 중 쪽이 밀려 빠진 것).
#   ② 그보다 옛 자리는 날마다 `깊이쪽수` 씩 내려가고, 기간 시작에 닿으면 처음부터 다시 — 옛 자리에 끼어든 것도 언젠가 본다.
#   이미 받은 것은 DOCID 로 걸러지니 헛일이 아니다.
# - **의원**은 날짜 칸이 아예 없어 기간으로 못 자른다. 전체 건수가 우리보다 많을 때만 처음부터 다시 받는다.
# - 하루 두 번 돌아도(지킴이·손) 오늘 끝낸 갈래는 다시 안 부른다 — 상세 몫을 안 먹게.
#
# ⚠️ 키는 `CLIK_KEY` — `.env` 나 저장소 Secrets 에서 온다(`scripts/keys.py`).
#    공개 저장소라 값은 절대 여기 적지 않는다.

import argparse
import calendar
import collections
import datetime
import glob
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import keys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
받는곳 = os.path.join(ROOT, 'data', 'clik')
상태파일 = os.path.join(받는곳, '상태.json')
BASE = 'https://clik.nanet.go.kr/openapi'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')

한번에 = 100        # 명세상 최대
하루한도 = 1000     # 명세상 최대
기본예산 = 900      # 손으로 확인해 볼 몫을 남겨 둔다
조각크기 = 10000    # 한 파일에 담을 건수

# ⭐ **제8회 지방선거 임기만 받는다**(2026-09-22 사용자 — "8회까지의 자료만 일단 필요해").
#    제8회 지방선거는 2022-06-01, 임기는 **2022-07-01 ~ 2026-06-30**.
#    ⭐ 처음엔 2026-06-30 에서 잘랐다가 **그날 저녁에 풀었다** — 제9회(제10대 의회)
#       자료도 계속 따라 들어와야 한다는 사용자 지시.
#    ⚠️ **대수(`RASMBLY_NUMPR`)로 거르면 안 된다** — 대수를 의회마다 따로 센다.
#       서울시의회는 12대인데 1991년에 생긴 기초의회는 9대다. **날짜로만 거른다.**
기본시작 = '20220701'


# ⚠️ **한국 시간으로 센다**(2026-10-01). 봇은 UTC 에서 도는데 한도는 한국 날짜로 끊긴다 —
#    UTC 로 적으면 새벽 5시(KST) 봇이 「어제」 칸에 적어, 그날 낮에 손으로 쓴 몫과 섞인다.
#    내부 표본 수집기(probe_clik_topic.py)도 한국 시간이다.
def _kst(fmt):
    return time.strftime(fmt, time.gmtime(time.time() + 9 * 3600))


def 오늘날짜():
    return _kst('%Y%m%d')


# ⭐ **끝날은 「오늘」이다**(2026-09-22 사용자 — "9회분도 자동으로 들어오게 만들어줘").
#    제9회로 뽑힌 제10대 의회(2026-07-01~)는 **지금도 계속 쌓이는 중**이라 끝을 못 박는다.
#    처음엔 20260630 에서 잘랐다가 그날 저녁에 풀었다.
def 기본끝():
    return 오늘날짜()


# 최신순으로 훑는 갈래는 **날마다 최근 이만큼을 다시 본다**(지금 회의록 약 100회 · 정책정보 약 12회).
# ⚠️ 처음엔 「최신 500건」이었는데 회의 날짜로 3주치뿐이라, 회의 뒤 몇 주 지나 올라오는 회의록을 놓쳤다(2026-11-04).
앞머리날수 = 150
# 그보다 옛 자리는 날마다 이 쪽수씩 — 회의록 약 37일, 정책정보 약 10일에 한 바퀴. 처음부터 다 받을 때는 --깊이 900.
깊이쪽수 = 40

# 이름 · 끝점 · 방식 · 날짜칸
#   방식 'API거르개' — 서버가 날짜로 걸러 준다(의안만 가능). 과거순으로 훑는다.
#   방식 '최신순훑기' — 거르개가 없다. 최신순으로 내려가며 기간 밖은 버리고,
#                      기간 시작보다 오래된 것이 나오면 멈춘다.
#   방식 '전수'       — 날짜 칸이 아예 없다(의원). 기간으로 못 자른다.
갈래목록 = [
    ('회의록', 'minutes.do', '최신순훑기', 'MTG_DE'),
    ('의안', 'bill.do', 'API거르개', 'ITNC_DE'),
    ('의원', 'assemblyinfo.do', '전수', None),
    ('정책정보', 'policyinfoList.do', '최신순훑기', 'CDATE'),
]
갈래이름 = {이름: (끝점, 방식, 날짜) for 이름, 끝점, 방식, 날짜 in 갈래목록}


def 날짜성한가(값):
    """빈 값 대신 쓰는 것이 0 · 18000101 · 19000101 · 19700101 넷이다. 다 거른다."""
    v = str(값 or '')
    if len(v) != 8 or not v.isdigit():
        return False
    if v in ('18000101', '19000101', '19700101'):
        return False
    return '1950' <= v[:4] <= '2100' and v[4:6] != '00' and v[6:8] != '00'


def 키읽기():
    # 환경변수 먼저, 그다음 .env — 깃허브 액션에서는 Secrets 가 환경변수로 온다
    return keys.키읽기('CLIK_KEY')


def 상태읽기():
    if os.path.exists(상태파일):
        return json.load(open(상태파일, encoding='utf-8'))
    return {'갈래': {}, '날짜별호출': {}}


def 상태쓰기(상태):
    os.makedirs(받는곳, exist_ok=True)
    json.dump(상태, open(상태파일, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)


def 오늘():
    return _kst('%Y-%m-%d')


연속무응답 = 0


def 부르기(끝점, 인자, 되풀이=3):
    """실패하면 2초·4초 쉬고 세 번까지. 돌아오는 것은 (본문, 오류코드).
    ⚠️ 서버가 아예 답을 안 하는 부름이 **이어서 둘이면** 그 뒤로는 부르지 않고 바로 '무응답' 을 돌려준다.
       2026-10-19 아침 CLIK 이 답을 안 하자 실패한 갈래를 하루 한도(900회)까지 다시 불러 —
       한 번에 3분씩 — 2시간 제한에 잘렸고, 뒤의 낱말 알림·올리기까지 못 돌았다."""
    global 연속무응답
    if 연속무응답 >= 2:
        return None, '무응답'
    url = f'{BASE}/{끝점}?' + urllib.parse.urlencode(인자)
    마지막, 답함 = None, False
    for n in range(되풀이):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                본문 = r.read().decode('utf-8', 'replace')
            답함, 연속무응답 = True, 0
            d = json.loads(본문)
            d = d[0] if isinstance(d, list) and d else d
            코드 = d.get('RESULT_CODE')
            if 코드 == 'SUCCESS':
                return d, None
            # ERROR09 = 일별 트래픽 초과. 되풀이해도 안 풀리니 바로 돌려보낸다.
            if 코드 == 'ERROR09':
                return d, 'ERROR09'
            마지막 = f"{코드} {d.get('RESULT_MESSAGE', '')}"
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
            마지막 = str(e)
        if n < 되풀이 - 1:
            time.sleep(2 * (n + 1))
    if not 답함:
        연속무응답 += 1
    return None, 마지막


def 조각쓰기(갈래, 번호, 줄들):
    os.makedirs(받는곳, exist_ok=True)
    경로 = os.path.join(받는곳, f'{갈래}_{번호:05d}.json.gz')
    # mtime=0 — gzip 머리에 시각이 박히면 내용이 같아도 날마다 새 파일이 되어 저장소 역사에 쌓인다
    with gzip.GzipFile(경로, 'wb', mtime=0) as f:
        f.write(json.dumps(줄들, ensure_ascii=False).encode('utf-8'))
    return 경로


def 받은DOCID(갈래):
    본 = set()
    for 경로 in sorted(glob.glob(os.path.join(받는곳, f'{갈래}_*.json.gz'))):
        with gzip.open(경로, 'rt', encoding='utf-8') as f:
            for 줄 in json.load(f):
                if 줄.get('DOCID'):
                    본.add(줄['DOCID'])
    return 본


def 달별건수(갈래, 날짜칸):
    셈 = collections.Counter()
    for 경로 in glob.glob(os.path.join(받는곳, f'{갈래}_*.json.gz')):
        with gzip.open(경로, 'rt', encoding='utf-8') as f:
            셈.update(str(줄.get(날짜칸) or '')[:6] for 줄 in json.load(f) if 줄.get('DOCID'))
    return 셈


def 끝난까닭(까닭):
    """오늘 이 갈래는 더 볼 것이 없다는 까닭인가 — 아니면(예산 다 씀·오류) 남은 예산으로 또 돈다."""
    return 까닭.startswith('끝까지') or 까닭.endswith(('기간 끝', '오늘 몫 끝'))


def 한갈래받기(갈래, 키, 상태, 남은예산, 시작날=기본시작, 끝날=None, 깊이=깊이쪽수):
    끝날 = 끝날 or 기본끝()
    끝점, 방식, 날짜칸 = 갈래이름[갈래]
    정렬 = {'API거르개': 'ITNC_DE/DESC', '최신순훑기': 'MTG_DE/DESC',  # 의안도 새것부터 — 새로 붙는 것을 먼저 만나 일찍 멈춘다
            '전수': None}[방식]
    if 갈래 == '정책정보':
        정렬 = None        # 정렬 인자가 아예 없다. 원래 최신순 고정이다.

    칸 = 상태['갈래'].setdefault(갈래, {'건수': 0, '전체': None})
    기간말 = f'{시작날}~{끝날}' if 방식 != '전수' else '(날짜 칸이 없어 전수)'
    if 칸.get('마지막수집') == 오늘() and 칸.get('기간') == 기간말 and 끝난까닭(칸.get('멈춘까닭', '')):
        print(f'  {갈래}: 오늘 이미 봤다 ({칸["멈춘까닭"]})')
        return 0, 칸['멈춘까닭']
    본것 = 받은DOCID(갈래)
    달별 = 달별건수(갈래, 날짜칸) if 방식 == 'API거르개' else None
    # ⭐ **덜 찬 마지막 조각을 다시 열지 않는다 — 늘 새 번호로 쓴다**(2026-09-29).
    #    목록을 다 받은 뒤로는 날마다 몇십 건씩만 붙는데, 그걸 마지막 조각(수백 KB)에 붙여 덮어쓰면
    #    옛 판이 날마다 저장소 역사에 쌓인다(갈래마다 한 해 100MB 안팎). 작은 새 파일은 거의 안 든다.
    번호 = len(glob.glob(os.path.join(받는곳, f'{갈래}_*.json.gz')))
    while os.path.exists(os.path.join(받는곳, f'{갈래}_{번호:05d}.json.gz')):
        번호 += 1
    담을것 = []

    셈 = {'호출': 0, '새로': 0, '버림': 0}

    def 부름(자리, 쪽=한번에, 거르개=None):
        """한 번 불러 장부에 적는다. 돌려주는 것은 (본문, 멈출 까닭)."""
        인자 = {'key': 키, 'type': 'json', 'startCount': 자리,
                'listCount': 쪽, 'searchType': 'ALL', 'searchKeyword': ''}
        if 끝점 != 'policyinfoList.do':
            인자['displayType'] = 'list'
        if 정렬:
            인자['sort'] = 정렬
        if 거르개:
            인자['itncStartDt'], 인자['itncEndDt'] = 거르개

        d, 오류 = 부르기(끝점, 인자)
        셈['호출'] += 1
        상태['날짜별호출'][오늘()] = 상태['날짜별호출'].get(오늘(), 0) + 1

        if 오류 == 'ERROR09':
            return None, '일별 트래픽 초과(ERROR09)'
        if 오류 == '무응답':
            return None, 'CLIK 무응답 — 내일 다시'
        if d is None:
            return None, f'오류 — {오류}'
        return d, None

    def 한쪽받기(자리, 멈출날=시작날, 거르개=None):
        """한 번 불러서 담는다. 돌려주는 것은 (더 갈까, 멈춘 까닭)."""
        nonlocal 번호, 담을것
        d, 까닭 = 부름(자리, 거르개=거르개)
        if d is None:
            return False, 까닭

        if not 거르개:
            칸['전체'] = d.get('TOTAL_COUNT')
        줄들 = [r.get('ROW', r) for r in (d.get('LIST') or [])]
        if not 줄들:
            return False, '끝까지 받음'

        for 줄 in 줄들:
            # 최신순으로 내려가는 갈래는 여기서 기간을 자른다.
            if 방식 == '최신순훑기':
                v = str(줄.get(날짜칸) or '')
                if not 날짜성한가(v) or v > 끝날:
                    셈['버림'] += 1
                    continue
                if v < 멈출날:
                    return False, f'{멈출날} 보다 오래된 자료가 나왔다 — 기간 끝'
            docid = 줄.get('DOCID')
            if docid and docid in 본것:
                continue
            if docid:
                본것.add(docid)
                if 달별 is not None:
                    달별[str(줄.get(날짜칸) or '')[:6]] += 1
            담을것.append(줄)
            셈['새로'] += 1
            if len(담을것) >= 조각크기:
                조각쓰기(갈래, 번호, 담을것)
                번호 += 1
                담을것 = []
        return True, None

    def 의안메우기():
        """기간 → 해 → 달로 건수를 견주어 CLIK 이 더 많은 달만 다시 받는다(새 달부터). 위치가 없어 끊겨도 다음에 스스로 메운다.
        ponytail: 건수만 견주므로 한 달에 지워진 것과 빠진 것이 같은 수면 못 본다 — 그런 일이 보이면 달마다 통째로 다시 받는 바퀴를 넣을 것."""
        def CLIK건수(시, 끝):
            d, 까닭 = 부름(0, 쪽=1, 거르개=(시, 끝))
            return (int(d.get('TOTAL_COUNT') or 0) if d else None), 까닭

        def 우리건수(시, 끝):
            return sum(n for 달, n in 달별.items() if 시[:6] <= 달 <= 끝[:6])

        칸['전체'], 까닭 = CLIK건수(시작날, 끝날)
        if 까닭:
            return 까닭
        if 칸['전체'] <= 우리건수(시작날, 끝날):
            return '끝까지 받음'
        for 해 in range(int(끝날[:4]), int(시작날[:4]) - 1, -1):
            if 셈['호출'] >= 남은예산:
                return '예산 다 씀'
            해시, 해끝 = max(시작날, f'{해}0101'), min(끝날, f'{해}1231')
            c, 까닭 = CLIK건수(해시, 해끝)
            if 까닭:
                return 까닭
            if c <= 우리건수(해시, 해끝):
                continue
            for 월 in range(12, 0, -1):
                달시 = max(해시, f'{해}{월:02d}01')
                달끝 = min(해끝, f'{해}{월:02d}{calendar.monthrange(해, 월)[1]}')
                if 달시 > 달끝:
                    continue
                if 셈['호출'] >= 남은예산:
                    return '예산 다 씀'
                c, 까닭 = CLIK건수(달시, 달끝)
                if 까닭:
                    return 까닭
                자리 = 0
                while 우리건수(달시, 달끝) < c:
                    if 셈['호출'] >= 남은예산:
                        return '예산 다 씀'
                    더갈까, 까닭 = 한쪽받기(자리, 거르개=(달시, 달끝))
                    자리 += 한번에
                    if not 더갈까:
                        if not 까닭.startswith('끝까지'):
                            return 까닭
                        print(f'  {갈래} {달시[:6]}: 끝까지 봤는데 {c - 우리건수(달시, 달끝):,}건 모자란다')
                        break
        return '끝까지 받음'

    def 최신순받기():
        # ── ① 최근 앞머리날수 치를 처음부터 다시 ───────────────────────────────
        경계 = max(시작날, (datetime.datetime.strptime(끝날, '%Y%m%d')
                          - datetime.timedelta(days=앞머리날수)).strftime('%Y%m%d'))
        자리 = 0
        while True:
            if 셈['호출'] >= 남은예산:
                return '예산 다 씀'
            더갈까, 까닭 = 한쪽받기(자리, 멈출날=경계)
            자리 += 한번에
            if not 더갈까:
                if 까닭.endswith('기간 끝'):   # 여기서는 앞머리 끝일 뿐이다
                    break
                return 까닭
        # ── ② 옛 자리는 날마다 깊이 쪽씩, 기간 시작에 닿으면 처음부터 다시 ──────
        시작 = max(칸.get('다음시작', 0), 자리 - 한번에)   # 경계가 걸린 쪽부터 — 그 쪽의 나머지를 ①이 버렸다
        칸['다음시작'] = 시작
        for _ in range(깊이):
            if 셈['호출'] >= 남은예산:
                return '예산 다 씀'
            더갈까, 까닭 = 한쪽받기(시작)
            if not 더갈까:
                if 끝난까닭(까닭):
                    칸['다음시작'] = 0
                return 까닭
            시작 += 한번에
            칸['다음시작'] = 시작
        return '오늘 몫 끝'

    def 전수받기():
        자리 = 0
        while 셈['호출'] < 남은예산:
            더갈까, 까닭 = 한쪽받기(자리)
            자리 += 한번에
            if not 더갈까:
                return 까닭
            if 칸['전체'] and len(본것) >= 칸['전체']:
                return '끝까지 받음'
        return '예산 다 씀'

    멈춘까닭 = {'API거르개': 의안메우기, '최신순훑기': 최신순받기, '전수': 전수받기}[방식]()

    if 담을것:
        조각쓰기(갈래, 번호, 담을것)
    if 방식 != '최신순훑기':
        칸.pop('다음시작', None)    # 옛 이어받기 위치 — 이제 안 쓴다
    칸['건수'] = len(본것)
    칸['마지막수집'] = 오늘()
    칸['멈춘까닭'] = 멈춘까닭
    칸['기간'] = 기간말
    전체 = f'{칸["전체"]:,}' if isinstance(칸['전체'], int) else '?'
    버린말 = f' · 기간 밖 {셈["버림"]:,}건 버림' if 셈['버림'] else ''
    print(f'  {갈래}: {셈["호출"]}회 불러 {셈["새로"]:,}건 새로 받음{버린말} — '
          f'모두 {칸["건수"]:,} / {전체}건 ({멈춘까닭})')
    return 셈['호출'], 멈춘까닭


# ⚠️ **코드표(243곳)는 「지금」 기준이라, 자료에 섞여 있는 옛 의회가 빠진다.**
#    2026-09-22 에 의원 28,538건을 전수로 받아 맞춰 보니 **코드가 248개** 나왔다.
#    코드표만으로 이으면 아래 다섯 곳이 조용히 사라진다 — 그래서 「없어진 곳」으로 적어 둔다.
없어진의회 = [
    ('061001', '전라남도의회', '065001 전남광주통합특별시의회로 통합'),
    ('062001', '광주광역시의회', '065001 전남광주통합특별시의회로 통합'),
    ('032006', '인천광역시 동구의회', '인천 중구와 통합'),
    ('032011', '인천광역시 중구의회', '인천 동구와 통합(코드가 바뀌었다)'),
    ('041900', '충청남도 서산군의회', '폐지 — 서산시로'),
]


def 의회목록굽기():
    """243곳 코드표 + 없어진 5곳. 명세 페이지에 박혀 있어 API 호출이 0회다."""
    import html
    import re
    url = 'https://clik.nanet.go.kr/potal/guide/resourceCenter.do'
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        h = r.read().decode('utf-8', 'replace')
    i = h.find('id="rasmblyIdDownDiv"')
    if i < 0:
        raise SystemExit('명세 페이지에서 의회 코드표를 못 찾았다 — 페이지가 바뀌었다')
    조각 = html.unescape(re.sub(r'(?s)<[^>]+>', chr(1), h[i:]))
    토막 = [t.strip() for t in 조각.split(chr(1)) if t.strip()]
    본것, 목록 = set(), []
    for 앞, 뒤 in zip(토막, 토막[1:]):
        if re.fullmatch(r'\d{6}', 뒤) and re.search(r'[가-힣]', 앞) \
                and not re.fullmatch(r'\d{6}', 앞):
            if 뒤 in 본것:
                continue
            본것.add(뒤)
            목록.append({'rasmblyId': 뒤, '의회명': 앞, '지역코드': 뒤[:3],
                         '지금있나': True})
    지금 = len(목록)
    for 코드, 이름, 까닭 in 없어진의회:
        if 코드 not in 본것:
            목록.append({'rasmblyId': 코드, '의회명': 이름, '지역코드': 코드[:3],
                         '지금있나': False, '까닭': 까닭})
    os.makedirs(받는곳, exist_ok=True)
    경로 = os.path.join(받는곳, '의회목록.json')
    json.dump(목록, open(경로, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'  의회 {지금}곳 + 없어진 {len(목록) - 지금}곳 — {경로}')
    return 목록


def selftest():
    """가짜 CLIK 으로 시험한다(호출 0회) — 늦게 올라와 이미 지나간 자리에 끼어든 자료가 들어오는가."""
    import tempfile
    g = globals()
    날 = ['2026-11-04']
    자료 = {'bill.do': [], 'minutes.do': [], 'assemblyinfo.do': [], 'policyinfoList.do': []}
    셈 = [0]

    def 가짜(끝점, 인자, 되풀이=3):
        셈[0] += 1
        줄 = 자료[끝점]
        if 'itncStartDt' in 인자:
            줄 = [r for r in 줄 if 인자['itncStartDt'] <= r['ITNC_DE'] <= 인자['itncEndDt']]
        if 인자.get('sort'):
            칸, 차례 = 인자['sort'].split('/')
            줄 = sorted(줄, key=lambda r: r[칸], reverse=차례 == 'DESC')
        자리 = 인자['startCount']
        return {'TOTAL_COUNT': len(줄), 'LIST': [{'ROW': r} for r in 줄[자리:자리 + 인자['listCount']]]}, None

    def 다음날():
        날[0] = (datetime.date.fromisoformat(날[0]) + datetime.timedelta(days=1)).isoformat()

    def 며칠전(n):
        return (datetime.date(2026, 11, 3) - datetime.timedelta(days=n)).strftime('%Y%m%d')

    with tempfile.TemporaryDirectory() as 곳:
        g.update(받는곳=곳, 상태파일=os.path.join(곳, '상태.json'), 부르기=가짜, 오늘=lambda: 날[0], 키읽기=lambda: '키')
        상태 = 상태읽기()

        def 돌리기(갈래, 예산=900):
            셈[0] = 0
            _, 까닭 = 한갈래받기(갈래, '키', 상태, 예산, 기본시작, 날[0].replace('-', ''))
            return 까닭, 받은DOCID(갈래)

        # ① 의안 — 옛 달에 늦게 올라온 것 · 이번 달 새것
        for 달 in ('202501', '202503', '202609', '202610'):
            자료['bill.do'] += [{'DOCID': f'B{달}{i}', 'ITNC_DE': f'{달}{i % 28 + 1:02d}'} for i in range(150)]
        assert len(돌리기('의안')[1]) == 600
        자료['bill.do'] += [{'DOCID': '늦은의안', 'ITNC_DE': '20250310'}, {'DOCID': '새의안', 'ITNC_DE': '20261104'}]
        다음날()
        assert {'늦은의안', '새의안'} <= 돌리기('의안')[1], '늦게 올라온 의안을 못 받았다'
        돌리기('의안')
        assert 셈[0] == 0, '같은 날 또 돌면 부르지 않아야 한다'
        다음날()
        assert 돌리기('의안')[0].startswith('끝까지') and 셈[0] == 1, '변한 게 없으면 1회여야 한다'
        자료['bill.do'] += [{'DOCID': f'늦은{i}', 'ITNC_DE': '20250115'} for i in range(300)]
        다음날()
        assert 돌리기('의안', 예산=3)[0] == '예산 다 씀' and 셈[0] == 3
        assert len(돌리기('의안')[1]) == 902, '예산이 모자랐으면 다음에 이어 받아야 한다'

        # ② 회의록 — 하루 10건 300일치 + 2023년치 + 기간 밖. 앞머리 500건 밖에 늦게 올라온 것
        자료['minutes.do'] += [{'DOCID': f'M{i}', 'MTG_DE': 며칠전(i // 10)} for i in range(3000)]
        자료['minutes.do'] += [{'DOCID': f'O{i}', 'MTG_DE': f'2023{i % 12 + 1:02d}15'} for i in range(2000)]
        자료['minutes.do'] += [{'DOCID': f'P{i}', 'MTG_DE': '20210115'} for i in range(500)]
        돌리기('회의록')
        다음날()
        for _ in range(3):      # 첫날 위치가 어디든 몇 날이면 한 바퀴를 끝낸다
            돌리기('회의록')
            다음날()
        assert len(받은DOCID('회의록')) == 5000
        자료['minutes.do'] += [{'DOCID': '늦은회의록', 'MTG_DE': 며칠전(60)}]
        assert '늦은회의록' in 돌리기('회의록')[1], '앞머리 밖에 늦게 올라온 회의록을 못 받았다'
        자료['minutes.do'] += [{'DOCID': '옛회의록', 'MTG_DE': '20230615'}]
        for _ in range(4):
            다음날()
            돌리기('회의록')
        assert '옛회의록' in 받은DOCID('회의록'), '옛 자리에 늦게 올라온 회의록을 한 바퀴 돌아도 못 받았다'

        # ③ 의원 — 다 받은 뒤 늘면 받는다, 안 늘면 1회
        자료['assemblyinfo.do'] += [{'DOCID': f'A{i}'} for i in range(250)]
        assert len(돌리기('의원')[1]) == 250
        자료['assemblyinfo.do'] += [{'DOCID': f'새A{i}'} for i in range(3)]
        다음날()
        assert len(돌리기('의원')[1]) == 253, '늘어난 의원을 못 받았다'
        다음날()
        돌리기('의원')
        assert 셈[0] == 1

        # ④ 네 갈래를 한 번에 — 예산을 남겨 두고 끝나야 한다(남은 예산으로 같은 쪽을 되풀이하면 상세 몫을 다 먹는다)
        다음날()
        open(os.path.join(곳, '의회목록.json'), 'w').close()
        상태쓰기(상태)
        셈[0] = 0
        sys.argv = ['fetch_clik.py', '--기간', 기본시작, 날[0].replace('-', '')]
        main()
        assert 셈[0] <= 70, f'변한 게 없는데 {셈[0]}회 불렀다'
    print('selftest ok')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--갈래', choices=[이름 for 이름, *_ in 갈래목록])
    ap.add_argument('--limit', type=int, default=기본예산,
                    help='이번 실행에서 부를 최대 횟수 (기본 900)')
    ap.add_argument('--다시', action='store_true')
    ap.add_argument('--깊이', type=int, default=깊이쪽수,
                    help=f'옛 자리를 이번에 몇 쪽 내려갈까 (기본 {깊이쪽수})')
    ap.add_argument('--의회목록', action='store_true')
    ap.add_argument('--기간', nargs=2, metavar=('시작', '끝'),
                    default=None,
                    help='YYYYMMDD 둘. 기본은 20220701 부터 오늘까지')
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    시작날, 끝날 = args.기간 or [기본시작, 기본끝()]

    if args.의회목록:
        의회목록굽기()
        return

    키 = 키읽기()
    상태 = 상태읽기()

    if args.다시:
        대상 = [args.갈래] if args.갈래 else [이름 for 이름, *_ in 갈래목록]
        for 갈래 in 대상:
            for 경로 in glob.glob(os.path.join(받는곳, f'{갈래}_*.json.gz')):
                os.remove(경로)
            상태['갈래'].pop(갈래, None)
        print(f'지웠다 — {", ".join(대상)}')

    오늘쓴것 = 상태['날짜별호출'].get(오늘(), 0)
    남은한도 = 하루한도 - 오늘쓴것
    예산 = min(args.limit, 남은한도)
    print(f'오늘 이미 {오늘쓴것}회 불렀다. 하루 한도까지 {남은한도}회 남음 → 이번엔 {예산}회까지.')
    if 예산 <= 0:
        print('오늘 몫을 다 썼다. 내일 다시 돌릴 것.')
        상태쓰기(상태)
        return

    if not os.path.exists(os.path.join(받는곳, '의회목록.json')):
        의회목록굽기()
    print(f'기간 — {시작날} ~ {끝날} (의원은 날짜 칸이 없어 전수)')

    대상 = [args.갈래] if args.갈래 else [이름 for 이름, *_ in 갈래목록]
    남음 = 예산
    # ⚠️ 몫을 한 번만 나누면 **남은 것이 버려진다.** 의원처럼 이미 끝난 갈래는 1회만 쓰는데
    #    몫은 그대로 잡혀 있어서다(네 갈래면 하루치의 4분의 1이 샌다 — 나흘이면 하루를 더 쓴다).
    #    그래서 **갈래를 넘어갈 때마다 남은 예산을 남은 갈래 수로 다시 나눈다.**
    끝났다 = False
    for i, 갈래 in enumerate(대상):
        if 남음 <= 0:
            break
        몫 = max(1, 남음 // (len(대상) - i))
        쓴것, 까닭 = 한갈래받기(갈래, 키, 상태, min(몫, 남음), 시작날, 끝날, args.깊이)
        남음 -= 쓴것
        상태쓰기(상태)
        if 까닭.startswith(('일별 트래픽', 'CLIK 무응답')):
            print(f'{까닭} — 내일 이어서 받는다.')
            끝났다 = True
            break

    # 한 바퀴 돌고도 예산이 남으면(끝난 갈래가 있어서) 남은 것으로 한 바퀴 더 돈다.
    while not 끝났다 and 남음 > 0:
        돈것 = 0
        # 「기간 끝」도 끝난 것이다 — 빼지 않으면 앞머리를 예산이 다할 때까지 되풀이한다
        # (2026-09-29 봇 로그: 회의록·정책정보가 같은 6회를 수십 번 불러 900회를 다 썼다).
        아직 = [g for g in 대상 if not 끝난까닭(str(상태['갈래'].get(g, {}).get('멈춘까닭', '')))]
        if not 아직:
            break
        for i, 갈래 in enumerate(아직):
            if 남음 <= 0:
                break
            몫 = max(1, 남음 // (len(아직) - i))
            쓴것, 까닭 = 한갈래받기(갈래, 키, 상태, min(몫, 남음), 시작날, 끝날, args.깊이)
            남음 -= 쓴것
            돈것 += 쓴것
            상태쓰기(상태)
            if 까닭.startswith(('일별 트래픽', 'CLIK 무응답')):
                print(f'{까닭} — 내일 이어서 받는다.')
                끝났다 = True
                break
        if 돈것 == 0:
            break

    상태쓰기(상태)
    print(f'상태 — {상태파일}')


if __name__ == '__main__':
    main()
