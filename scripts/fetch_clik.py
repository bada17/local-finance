# 지방의정포털 CLIK 수집기 — 243개 지방의회의 회의록·의안·의원·지방정책정보.
#
#   python scripts/fetch_clik.py                    네 갈래를 이어받는다 (기본 900회)
#   python scripts/fetch_clik.py --갈래 회의록      한 갈래만
#   python scripts/fetch_clik.py --limit 200        이번에 200회만 부른다
#   python scripts/fetch_clik.py --기간 20100101 20260630   기간을 바꾼다(기본 20220701~오늘)
#   python scripts/fetch_clik.py --다시             처음부터 (받아 둔 것을 지운다)
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
#
# **갈래마다 기간을 자르는 방법이 다르다.**
# - **의안**만 서버가 걸러 준다(`itncStartDt`·`itncEndDt`). 과거순으로 훑으면 위치가 안 흔들린다.
# - **회의록·정책정보**는 거르개가 없다. **최신순으로 내려가며** 기간 밖은 버리고,
#   기간 시작보다 오래된 것이 나오면 거기서 멈춘다.
#   ⭐ **매번 앞머리 5쪽(500건)을 다시 훑는다**(`앞머리쪽수`). 두 가지를 한꺼번에 푼다 —
#   ① 새로 올라온 회의록. 이어받기 위치만 보면 이미 앞을 지나쳐서 **영영 못 본다.**
#   ② 표류. 수집 중에 새 글이 끼어들면 쪽이 밀려 빠뜨리는 것이 생긴다.
#   이미 받은 것은 DOCID 로 걸러지니 헛일이 아니다.
# - **의원**은 날짜 칸이 아예 없어 기간으로 못 자른다. 전수 28,538건을 그냥 받는다(이미 끝났다).
#
# ⚠️ 키는 `CLIK_KEY` — `.env` 나 저장소 Secrets 에서 온다(`scripts/keys.py`).
#    공개 저장소라 값은 절대 여기 적지 않는다.

import argparse
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


def 오늘날짜():
    return time.strftime('%Y%m%d')


# ⭐ **끝날은 「오늘」이다**(2026-09-22 사용자 — "9회분도 자동으로 들어오게 만들어줘").
#    제9회로 뽑힌 제10대 의회(2026-07-01~)는 **지금도 계속 쌓이는 중**이라 끝을 못 박는다.
#    처음엔 20260630 에서 잘랐다가 그날 저녁에 풀었다.
def 기본끝():
    return 오늘날짜()


# 최신순으로 훑는 갈래는 **매번 앞머리를 다시 본다.**
# 안 그러면 이어받기 위치가 이미 앞을 지나쳐 있어서, 새로 올라온 회의록이 영영 안 들어온다.
# 표류(수집 중에 새 글이 끼어들어 쪽이 밀리는 것)도 이걸로 같이 메운다.
앞머리쪽수 = 5

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
    return time.strftime('%Y-%m-%d')


def 부르기(끝점, 인자, 되풀이=3):
    """실패하면 2초·4초 쉬고 세 번까지. 돌아오는 것은 (본문, 오류코드)."""
    url = f'{BASE}/{끝점}?' + urllib.parse.urlencode(인자)
    마지막 = None
    for n in range(되풀이):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                본문 = r.read().decode('utf-8', 'replace')
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
    return None, 마지막


def 조각쓰기(갈래, 번호, 줄들):
    os.makedirs(받는곳, exist_ok=True)
    경로 = os.path.join(받는곳, f'{갈래}_{번호:05d}.json.gz')
    with gzip.open(경로, 'wt', encoding='utf-8') as f:
        json.dump(줄들, f, ensure_ascii=False)
    return 경로


def 조각읽기(갈래, 번호):
    경로 = os.path.join(받는곳, f'{갈래}_{번호:05d}.json.gz')
    if os.path.exists(경로):
        with gzip.open(경로, 'rt', encoding='utf-8') as f:
            return json.load(f)
    return []


def 받은DOCID(갈래):
    본 = set()
    for 경로 in sorted(glob.glob(os.path.join(받는곳, f'{갈래}_*.json.gz'))):
        with gzip.open(경로, 'rt', encoding='utf-8') as f:
            for 줄 in json.load(f):
                if 줄.get('DOCID'):
                    본.add(줄['DOCID'])
    return 본


def 한갈래받기(갈래, 키, 상태, 남은예산, 시작날=기본시작, 끝날=None):
    끝날 = 끝날 or 기본끝()
    끝점, 방식, 날짜칸 = 갈래이름[갈래]
    정렬 = {'API거르개': 'ITNC_DE/ASC', '최신순훑기': 'MTG_DE/DESC',
            '전수': None}[방식]
    if 갈래 == '정책정보':
        정렬 = None        # 정렬 인자가 아예 없다. 원래 최신순 고정이다.

    칸 = 상태['갈래'].setdefault(갈래, {'다음시작': 0, '건수': 0, '전체': None})
    본것 = 받은DOCID(갈래)
    번호 = len(본것) // 조각크기          # 마지막 조각은 덜 찼을 수 있다
    담을것 = 조각읽기(갈래, 번호)

    셈 = {'호출': 0, '새로': 0, '버림': 0}

    def 한쪽받기(자리):
        """한 번 불러서 담는다. 돌려주는 것은 (더 갈까, 멈춘 까닭)."""
        nonlocal 번호, 담을것
        인자 = {'key': 키, 'type': 'json', 'startCount': 자리,
                'listCount': 한번에, 'searchType': 'ALL', 'searchKeyword': ''}
        if 끝점 != 'policyinfoList.do':
            인자['displayType'] = 'list'
        if 정렬:
            인자['sort'] = 정렬
        if 방식 == 'API거르개':
            인자['itncStartDt'] = 시작날
            인자['itncEndDt'] = 끝날

        d, 오류 = 부르기(끝점, 인자)
        셈['호출'] += 1
        상태['날짜별호출'][오늘()] = 상태['날짜별호출'].get(오늘(), 0) + 1

        if 오류 == 'ERROR09':
            return False, '일별 트래픽 초과(ERROR09)'
        if d is None:
            return False, f'오류 — {오류}'

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
                if v < 시작날:
                    return False, f'{시작날} 보다 오래된 자료가 나왔다 — 기간 끝'
            docid = 줄.get('DOCID')
            if docid and docid in 본것:
                continue
            if docid:
                본것.add(docid)
            담을것.append(줄)
            셈['새로'] += 1
            if len(담을것) >= 조각크기:
                조각쓰기(갈래, 번호, 담을것)
                번호 += 1
                담을것 = []
        return True, None

    멈춘까닭 = '예산 다 씀'

    # ── ① 앞머리 훑기 ────────────────────────────────────────────────────────
    # 최신순으로 내려가는 갈래는 이어받기 위치가 **이미 앞을 지나쳐 있다.**
    # 그대로 두면 새로 올라온 회의록이 영영 안 들어온다. 그래서 깊이 파기 전에
    # 맨 앞 몇 쪽을 다시 본다. 이미 받은 것은 DOCID 로 걸러지니 헛일이 아니다.
    # 수집 중에 새 글이 끼어들어 쪽이 밀리는 표류도 이걸로 같이 메운다.
    앞머리한것 = 0
    if 방식 == '최신순훑기' and 칸['다음시작'] > 0:
        for i in range(앞머리쪽수):
            if 셈['호출'] >= 남은예산:
                break
            더갈까, 까닭 = 한쪽받기(i * 한번에)
            앞머리한것 += 1
            if not 더갈까:
                # 「기간 끝」은 앞머리에서는 멈출 이유가 아니다(앞머리가 짧아서 그런 것).
                if 까닭 and not 까닭.endswith('기간 끝'):
                    멈춘까닭 = 까닭
                break

    # ── ② 이어받기 위치부터 깊이 파기 ────────────────────────────────────────
    시작 = 칸['다음시작']
    if not 멈춘까닭.startswith(('일별', '오류')):
        while 셈['호출'] < 남은예산:
            더갈까, 까닭 = 한쪽받기(시작)
            시작 += 한번에
            칸['다음시작'] = 시작
            if not 더갈까:
                멈춘까닭 = 까닭
                break
            if 칸['전체'] and 시작 >= 칸['전체']:
                멈춘까닭 = '끝까지 받음'
                break

    if 담을것:
        조각쓰기(갈래, 번호, 담을것)
    칸['다음시작'] = 시작
    칸['건수'] = len(본것)
    칸['마지막수집'] = 오늘()
    칸['멈춘까닭'] = 멈춘까닭
    칸['기간'] = f'{시작날}~{끝날}' if 방식 != '전수' else '(날짜 칸이 없어 전수)'
    전체 = f'{칸["전체"]:,}' if isinstance(칸['전체'], int) else '?'
    버린말 = f' · 기간 밖 {셈["버림"]:,}건 버림' if 셈['버림'] else ''
    앞말 = f' (앞머리 {앞머리한것}쪽 포함)' if 앞머리한것 else ''
    print(f'  {갈래}: {셈["호출"]}회 불러{앞말} {셈["새로"]:,}건 새로 받음{버린말} — '
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--갈래', choices=[이름 for 이름, *_ in 갈래목록])
    ap.add_argument('--limit', type=int, default=기본예산,
                    help='이번 실행에서 부를 최대 횟수 (기본 900)')
    ap.add_argument('--다시', action='store_true')
    ap.add_argument('--의회목록', action='store_true')
    ap.add_argument('--기간', nargs=2, metavar=('시작', '끝'),
                    default=None,
                    help='YYYYMMDD 둘. 기본은 20220701 부터 오늘까지')
    args = ap.parse_args()
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
        쓴것, 까닭 = 한갈래받기(갈래, 키, 상태, min(몫, 남음), 시작날, 끝날)
        남음 -= 쓴것
        상태쓰기(상태)
        if 까닭.startswith('일별 트래픽'):
            print('일별 한도에 걸렸다. 내일 이어서 받는다.')
            끝났다 = True
            break

    # 한 바퀴 돌고도 예산이 남으면(끝난 갈래가 있어서) 남은 것으로 한 바퀴 더 돈다.
    while not 끝났다 and 남음 > 0:
        돈것 = 0
        아직 = [g for g in 대상 if not str(상태['갈래'].get(g, {}).get('멈춘까닭', ''))
                .startswith('끝까지')]
        if not 아직:
            break
        for i, 갈래 in enumerate(아직):
            if 남음 <= 0:
                break
            몫 = max(1, 남음 // (len(아직) - i))
            쓴것, 까닭 = 한갈래받기(갈래, 키, 상태, min(몫, 남음), 시작날, 끝날)
            남음 -= 쓴것
            돈것 += 쓴것
            상태쓰기(상태)
            if 까닭.startswith('일별 트래픽'):
                print('일별 한도에 걸렸다. 내일 이어서 받는다.')
                끝났다 = True
                break
        if 돈것 == 0:
            break

    상태쓰기(상태)
    print(f'상태 — {상태파일}')


if __name__ == '__main__':
    main()
