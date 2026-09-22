# 나라장터 계약에서 **「업체명 → 사업자등록번호」 사전**을 만든다.
#
#   python scripts/fetch_bizno.py                   받아 둔 마지막 달부터 이번 달까지
#   python scripts/fetch_bizno.py 202609            그 달
#   python scripts/fetch_bizno.py 202401 202609     그 달부터 그 달까지
#   python scripts/fetch_bizno.py 202609 --다시     다시 받는다
#
# ⭐ **끝난 해·달만 건너뛴다. 아직 안 끝난 것은 늘 다시 받는다.**
#    자료가 계속 붙는데 한 번 받고 끝내면 옛 숫자가 그대로 굳는다
#    (2026-09-22 사용자 — "모든 API는 업데이트되는 자료를 받아오는 형식으로 디자인되어야 함").
# 왜 — 지방재정365 계약현황(`WCEGCF`)에는 **업체명만** 있다. 그래서 「(주)○○」와
#      「주식회사 ○○」가 갈라진다. 나라장터에는 사업자번호가 있으니, 거기서 이름과 번호의
#      짝을 모아 **우리 계약 320만 건에 되붙인다.**
#      ⚠️ 나라장터는 **조달청을 거친 계약만**이다. 붙는 만큼만 붙고 나머지는 이름 그대로 둔다.
#
# ⚠️ **`numOfRows=1000` 을 주면 조용히 10건만 온다.** 오류도 안 난다. **999 가 끝이다.**
# ⚠️ 날짜 인자는 `inqryBgnDt`/`inqryEndDt` 이고 **12자리(YYYYMMDDHHMM)** 다.
#    `inqryBgnDate`(8자리)로 부르면 `08 필수값 입력 에러`.
# ⚠️ 원자료를 통째로 담지 않는다. **이름·번호·대표자만 추려** 담는다(원자료는 한 해 수백만 줄이다).
# ⚠️ 키는 `.env` 의 `DATA_GO_KR_KEY`.

import calendar
import gzip
import glob
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
BASE = 'https://apis.data.go.kr/1230000/ao/CntrctInfoService'
길 = {'물품': 'getCntrctInfoListThng',
     '용역': 'getCntrctInfoListServc',
     '공사': 'getCntrctInfoListCnstwk'}
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')
한쪽 = 999                                   # ⚠️ 1000 을 주면 10건만 온다


def 키읽기():
    # 환경변수 먼저, 그다음 .env — 깃허브 액션에서는 Secrets 가 환경변수로 온다
    return keys.키읽기('DATA_GO_KR_KEY')


def 부르기(갈래, 키, 처음, 끝, 쪽, 되풀이=4):
    q = {'serviceKey': 키, 'pageNo': 쪽, 'numOfRows': 한쪽, 'type': 'json',
         'inqryDiv': '1', 'inqryBgnDt': 처음, 'inqryEndDt': 끝}
    url = f'{BASE}/{길[갈래]}?' + urllib.parse.urlencode(q, safe='%')
    마지막 = None
    for n in range(되풀이):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                본문 = r.read().decode('utf-8', errors='replace')
            본문 = 본문.replace(키, '<키>')
            d = json.loads(본문)
        except Exception as e:
            마지막 = e
            time.sleep(3 * (n + 1))
            continue
        틀림 = d.get('nkoneps.com.response.ResponseError') or d.get('OpenAPI_ServiceResponse')
        if 틀림:
            raise SystemExit(f'{갈래} 거절 — {json.dumps(틀림, ensure_ascii=False)[:200]}')
        몸 = (d.get('response') or {}).get('body') or {}
        줄 = 몸.get('items') or []
        if isinstance(줄, dict):
            줄 = 줄.get('item') or []
        if isinstance(줄, dict):
            줄 = [줄]
        return 줄, int(몸.get('totalCount') or 0)
    raise SystemExit(f'네 번 다 실패({갈래}): {마지막!r}')


def 업체들(r):
    """corpList 를 쪼갠다 — `^` 로 붙고 맨 끝이 사업자번호, 공동수급이면 `]|[` 로 이어진다."""
    덩이 = str(r.get('corpList') or '').strip().lstrip('[').rstrip(']')
    for 조각 in 덩이.split(']|['):
        칸 = 조각.split('^')
        if len(칸) >= 10:
            이름, 대표, 번호 = 칸[3].strip(), 칸[4].strip(), 칸[9].strip()
            if 이름:
                yield 이름, 대표, 번호


def 한달(키, 달):
    처음 = f'{달}010000'
    끝날 = calendar.monthrange(int(달[:4]), int(달[4:]))[1]
    끝 = f'{달}{끝날:02d}2359'
    사전 = {}
    줄수 = 0
    for 갈래 in 길:
        쪽 = 1
        전체 = None
        while True:
            줄, 전체 = 부르기(갈래, 키, 처음, 끝, 쪽)
            if not 줄:
                break
            줄수 += len(줄)
            for r in 줄:
                for 이름, 대표, 번호 in 업체들(r):
                    열쇠 = (이름, 번호)
                    한 = 사전.get(열쇠)
                    if 한:
                        한['건수'] += 1
                    else:
                        사전[열쇠] = {'이름': 이름, '번호': 번호,
                                   '대표자': 대표, '건수': 1}
            if 쪽 * 한쪽 >= 전체:
                break
            쪽 += 1
            time.sleep(0.1)
    return 사전, 줄수


def main():
    이번달 = time.strftime('%Y%m')
    달들 = [a for a in sys.argv[1:] if a.isdigit() and len(a) == 6]
    다시 = '--다시' in sys.argv

    낼곳 = os.path.join(ROOT, 'data', 'bizno')
    os.makedirs(낼곳, exist_ok=True)

    if 달들:
        처음달, 끝달 = 달들[0], (달들[1] if len(달들) > 1 else 달들[0])
    else:
        # ⭐ 인자를 안 줘도 돌아야 한다 — 날마다 도는 봇이 달을 못 준다.
        #    받아 둔 마지막 달부터 이번 달까지 이어 받는다(마지막 달은 덜 찼을 수 있다).
        있는것 = sorted(os.path.basename(x)[:6]
                      for x in glob.glob(os.path.join(낼곳, '??????.json.gz')))
        처음달 = 있는것[-1] if 있는것 else 이번달
        끝달 = 이번달
        if 처음달 > 끝달:
            처음달 = 끝달
        print(f'달을 안 줬다 — {처음달} 부터 {끝달} 까지 이어 받는다')
    키 = 키읽기()

    달 = 처음달
    while 달 <= 끝달:
        경로 = os.path.join(낼곳, f'{달}.json.gz')
        # ⭐ 끝난 달만 건너뛴다. 이번 달은 계약이 계속 붙으니 늘 다시 받는다.
        if os.path.exists(경로) and not 다시 and 달 < 이번달:
            print(f'{달} — 이미 있다 (끝난 달이라 건너뛴다)')
        else:
            시작 = time.time()
            사전, 줄수 = 한달(키, 달)
            표 = sorted(사전.values(), key=lambda r: -r['건수'])
            with gzip.open(경로, 'wt', encoding='utf-8') as f:
                json.dump(표, f, ensure_ascii=False)
            번호있 = sum(1 for r in 표 if r['번호'])
            print(f'{달} — 계약 {줄수:,}줄 · 업체 {len(표):,}가지 '
                  f'(번호 붙은 것 {번호있:,}) · {time.time() - 시작:.0f}초')
        해, 월 = int(달[:4]), int(달[4:])
        해, 월 = (해 + 1, 1) if 월 == 12 else (해, 월 + 1)
        달 = f'{해}{월:02d}'


if __name__ == '__main__':
    main()
