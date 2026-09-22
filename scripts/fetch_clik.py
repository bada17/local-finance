# 지방의정포털 CLIK 수집기 — 243개 지방의회의 회의록·의안·의원·지방정책정보.
#
#   python scripts/fetch_clik.py                    네 갈래를 이어받는다 (기본 900회)
#   python scripts/fetch_clik.py --갈래 회의록      한 갈래만
#   python scripts/fetch_clik.py --limit 200        이번에 200회만 부른다
#   python scripts/fetch_clik.py --다시             처음부터 (받아 둔 것을 지운다)
#   python scripts/fetch_clik.py --의회목록         243곳 코드표만 다시 굽는다 (호출 0회)
#
# 왜 — 숫자 옆에 "그때 누가 무슨 말을 했나"를 붙일 수 있는 유일한 자료다.
#      계약·보조금은 얼마 썼는지만 말하고, 회의록은 왜 그렇게 썼는지를 말한다.
#
# ⚠️ **하루 1,000회 · 한 번에 100건이 박혀 있다.** 이게 이 갈래의 전부를 규정한다.
#    목록 전수가 217만 건(2026-09-22 실측)이라 100건씩 나눠도 21,661회 —
#    하루 한도를 다 써도 **22일**이 걸린다. 그래서 이어받기가 선택이 아니라 필수다.
#    상태 파일에 **날짜별 호출 수**를 적어 두고, 같은 날 다시 돌려도 한도를 안 넘게 한다.
#
# ⚠️ **상세(displayType=detail)는 전수로 못 받는다.** 한 건에 한 번이라 217만 회 =
#    2,166일이다. 상세는 사용자가 고른 범위만 따로 받는다(이 수집기는 목록만 받는다).
#
# ⚠️ **회의록에는 날짜 거르개가 없다.** 의안만 itncStartDt/itncEndDt 를 받는다.
#    그래서 회의록·의원·정책정보는 통째로 훑는 수밖에 없다.
#
# ⚠️ **정렬을 과거순으로 고정한다.** 최신순으로 훑으면 수집하는 사이에 새 자료가
#    앞에 끼어들어 쪽이 밀리고, 같은 것을 두 번 받거나 빠뜨린다. 과거순이면 새 자료가
#    맨 뒤에 붙으므로 이어받기 위치가 안 흔들린다.
#    ⚠️ 다만 **정책정보는 정렬 인자가 아예 없다**(등록일 내림차순 고정) — 표류한다.
#    DOCID 로 걸러 내지만 빠뜨린 것이 생길 수 있어, 다 받은 뒤 한 번 더 훑어야 한다.
#
# ⚠️ 키는 `.env` 의 `CLIK_KEY`. 공개 저장소라 값은 절대 여기 적지 않는다.

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

# 이름 · 끝점 · 정렬인자 · 날짜칸
갈래목록 = [
    ('회의록', 'minutes.do', 'MTG_DE/ASC', 'MTG_DE'),
    ('의안', 'bill.do', 'ITNC_DE/ASC', 'ITNC_DE'),
    ('의원', 'assemblyinfo.do', None, None),
    ('정책정보', 'policyinfoList.do', None, 'CDATE'),
]
갈래이름 = {이름: (끝점, 정렬, 날짜) for 이름, 끝점, 정렬, 날짜 in 갈래목록}


def 키읽기():
    경로 = os.path.join(ROOT, '.env')
    if os.path.exists(경로):
        for 줄 in open(경로, encoding='utf-8'):
            if 줄.startswith('CLIK_KEY='):
                값 = 줄.split('=', 1)[1].strip()
                if 값:
                    return 값
    값 = os.environ.get('CLIK_KEY', '').strip()
    if 값:
        return 값
    raise SystemExit('.env 에 CLIK_KEY 가 비어 있다 (깃허브 Secrets 에도 같은 이름으로 넣을 것)')


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


def 한갈래받기(갈래, 키, 상태, 남은예산):
    끝점, 정렬, _ = 갈래이름[갈래]
    칸 = 상태['갈래'].setdefault(갈래, {'다음시작': 0, '건수': 0, '전체': None})
    시작 = 칸['다음시작']
    본것 = 받은DOCID(갈래)
    칸['건수'] = len(본것)

    # 마지막 조각은 덜 찼을 수 있으니 이어서 채운다
    번호 = len(본것) // 조각크기
    담을것 = 조각읽기(갈래, 번호)

    # ⚠️ 다 받은 갈래도 **건너뛰지 않는다.** 과거순으로 훑고 있어서, 새로 올라온 자료는
    #    맨 뒤에 붙는다 — 끝 위치에서 한 번 더 부르는 그 호출이 새 자료를 집어오는 장치다.
    #    (정책정보만은 최신순 고정이라 새 자료가 앞에 붙는다. 그쪽은 다 받은 뒤 한 번 더 훑어야 한다.)
    쓴호출 = 0
    새로받음 = 0
    멈춘까닭 = '예산 다 씀'
    while 쓴호출 < 남은예산:
        인자 = {'key': 키, 'type': 'json', 'startCount': 시작,
                'listCount': 한번에, 'searchType': 'ALL', 'searchKeyword': ''}
        if 끝점 != 'policyinfoList.do':
            인자['displayType'] = 'list'
        if 정렬:
            인자['sort'] = 정렬

        d, 오류 = 부르기(끝점, 인자)
        쓴호출 += 1
        상태['날짜별호출'][오늘()] = 상태['날짜별호출'].get(오늘(), 0) + 1

        if 오류 == 'ERROR09':
            멈춘까닭 = '일별 트래픽 초과(ERROR09)'
            break
        if d is None:
            멈춘까닭 = f'오류 — {오류}'
            break

        칸['전체'] = d.get('TOTAL_COUNT')
        줄들 = [r.get('ROW', r) for r in (d.get('LIST') or [])]
        if not 줄들:
            멈춘까닭 = '끝까지 받음'
            시작 += 한번에
            break

        for 줄 in 줄들:
            docid = 줄.get('DOCID')
            if docid and docid in 본것:
                continue
            if docid:
                본것.add(docid)
            담을것.append(줄)
            새로받음 += 1
            if len(담을것) >= 조각크기:
                조각쓰기(갈래, 번호, 담을것)
                번호 += 1
                담을것 = []

        시작 += 한번에
        칸['다음시작'] = 시작
        칸['건수'] = len(본것)

        if 칸['전체'] and 시작 >= 칸['전체']:
            멈춘까닭 = '끝까지 받음'
            break

    if 담을것:
        조각쓰기(갈래, 번호, 담을것)
    칸['다음시작'] = 시작
    칸['건수'] = len(본것)
    칸['마지막수집'] = 오늘()
    칸['멈춘까닭'] = 멈춘까닭
    전체 = f'{칸["전체"]:,}' if isinstance(칸['전체'], int) else '?'
    print(f'  {갈래}: {쓴호출}회 불러 {새로받음:,}건 새로 받음 — '
          f'모두 {칸["건수"]:,} / {전체}건 ({멈춘까닭})')
    return 쓴호출, 멈춘까닭


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
    args = ap.parse_args()

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

    대상 = [args.갈래] if args.갈래 else [이름 for 이름, *_ in 갈래목록]
    몫 = max(1, 예산 // len(대상))
    남음 = 예산
    for 갈래 in 대상:
        if 남음 <= 0:
            break
        쓴것, 까닭 = 한갈래받기(갈래, 키, 상태, min(몫, 남음))
        남음 -= 쓴것
        상태쓰기(상태)
        if 까닭.startswith('일별 트래픽'):
            print('일별 한도에 걸렸다. 내일 이어서 받는다.')
            break

    상태쓰기(상태)
    print(f'상태 — {상태파일}')


if __name__ == '__main__':
    main()
