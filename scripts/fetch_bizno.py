# 나라장터 계약에서 **「업체명 → 사업자등록번호」 사전**을 만든다.
#
#   python scripts/fetch_bizno.py                   계약 원본 첫 달부터 지난달까지 빈 달 + 이번 달은 하루치씩(data/bizno/일/)
#   python scripts/fetch_bizno.py 202609            그 달
#   python scripts/fetch_bizno.py 202401 202609     그 달부터 그 달까지
#   python scripts/fetch_bizno.py 202609 --다시     다시 받는다
#   python scripts/fetch_bizno.py --분 50            50분이 지나면 받던 갈래를 버리고 멈춘다(인자 없이 부르면 기본 50)
#   python scripts/fetch_bizno.py 202401 202508 --사유만   사전은 두고 수의계약 사유만(data/수의계약/) 받는다
#   python scripts/fetch_bizno.py --사유끔          사유 파일이 없어도 받은 달로 친다(봇이 R2 에서 못 내려받은 날)
#   python scripts/fetch_bizno.py 202501 202512 --사유만 --차수채움   수의계약 파일에 「차수」 칸이 없는 달만 다시 받는다(suui-refetch.yml)
#
# ⭐ **지자체 수의계약 줄은 사유까지 따로 담는다**(2026-10-16) → `data/수의계약/{달}.json.gz`, 이번 달은 `일/`.
#    나라장터 계약에는 `baseLawNm`(근거 조항)·`baseDtls`(사유 — 「추정가격 2천만원 이하 물품 또는 용역」 등)이 온다.
#    **저장소엔 안 올린다 — R2(local-finance-raw, 수의계약/)에 쌓는다.** 봇이 내려받고→받고→올린다(daily.yml).
#    ⚠️ 2024년치는 `사유` 칸이 거의 비고(2024-01: 5만 줄 중 64줄) `법` 칸만 찼다 — 조항으로 갈래를 알 수 있다.
#    지방재정365 계약현황(WCEGCF)엔 없다. 「왜 이 업체」 같은 글은 아니고 법이 정한 갈래 수준이다.
#    ⚠️ 거르는 검색(`…PPSSrch`, 기관분류 02·계약방법 4)은 쓰지 않는다 — **체결일 칸이 빈 계약이 절반쯤인데
#       날짜 검색에 안 걸린다**(2025-09-02 공사 918건 0건 잡힘). 그래서 전부 받아 여기서 고른다.
#    ⚠️ 등록일 기준이라 같은 계약(`계약` 칸)이 변경 등록으로 또 올 수 있다 — 셀 때 겹침을 거를 것.
#
# ⭐ **시간 한도를 스스로 지킨다**(2026-09-30). 빈 달이 27개면 한 달 12분씩 5시간이 넘는다 —
#    봇 작업 제한(6시간)에 걸려 뒤의 「올리기」까지 잘렸다. 달 파일은 한 달이 끝날 때마다 쓰므로
#    한도에서 멈춰도 받은 달은 남는다. 나머지는 다음 날 봇이 잇는다.
# ⭐ **한 달이 갈래(물품·용역·공사)마다 조각으로 저장된다**(2026-10-12). 2025년부터 한 달이
#    440쪽 × 8초 ≈ 60분이라 봇 단계 제한(60분)에 매번 잘려 **18달이 한 달도 못 찼다.**
#    이제 갈래 하나(길어야 용역 270쪽 ≈ 37분)가 끝날 때마다 `data/bizno/조각/{달}_{갈래}.part.gz` 에 쓰고,
#    마감은 **쪽마다** 본다 — 넘으면 받던 갈래만 버리고 멈춘다. 셋이 다 차면 달 파일로 합치고 조각은 지운다.
#    ⚠️ 조각은 `.part.gz` 다 — build_contracts_summary.py 가 `**/*.json.gz` 를 훑으므로 두 번 세지 않게.
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
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import keys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
수의곳 = os.path.join(ROOT, 'data', '수의계약')    # ⚠️ data/bizno/ 밖 — 거기 *.json.gz 는 사전으로 읽힌다
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
            # 429 는 잠깐 막는 것으로 보인다(2026-10-16: 막힌 사이 다른 갈래는 59쪽을 받았다) — 1·2·3분 쉰다
            time.sleep(60 * (n + 1) if getattr(e, 'code', None) == 429 else 3 * (n + 1))
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


# 수의계약 파일은 {'칸': 수의칸, '줄': [[…], …]} — 칸 이름을 줄마다 안 적고 기관·날 차례로 세워
# 25% 작다(하루 0.28→0.21MB, 2025-09-02 로 잼). 34달이면 그래도 150MB 안팎이다.
수의칸 = ['계약', '기관', '곳', '날', '갈래', '금액', '총액', '법', '사유', '업체', '건', '원계약', '차수']
# ⭐ 원계약·차수(2026-10-26) — 상세 주소의 ctrtNo·ctrtChgOrd. 같은 계약을 고쳐 다시 올리면 계약(untyCntrctNo)은 새로 붙고 이 둘은 이어진다.
#    10-23 공사 수의 하루치: 차수 00 이 줄 63%·금액 41%, 01 이상(고친 것)이 금액 59% — 원계약마다 마지막 차수만 세야 금액이 맞는다.
#    확정계약번호(dcsnCntrctNo) 끝 두 자리도 차수지만 그 칸은 절반이 빈다. 2026-10-26 전에 받은 파일엔 두 칸이 없다.


def 원(값):
    return round(float(값 or 0))      # 「170.5」 같은 소수 금액이 섞여 온다(2024-01)


def 수의줄(r, 갈래):
    """지자체 수의계약이면 사유까지 추린 한 줄, 아니면 None. 담당자 이름·전화는 안 담는다(저장소가 공개)."""
    if r.get('cntrctInsttJrsdctnDivNm') != '지방자치단체' or '수의' not in str(r.get('cntrctCnclsMthdNm') or ''):
        return None
    return [r.get('untyCntrctNo'), r.get('cntrctInsttCd'), r.get('cntrctInsttNm'),
            r.get('cntrctCnclsDate') or r.get('cntrctDate'),          # 체결일이 빈 줄이 절반쯤 — 계약일로
            갈래, 원(r.get('thtmCntrctAmt')), 원(r.get('totCntrctAmt')),
            r.get('baseLawNm'), r.get('baseDtls'), [번호 for _, _, 번호 in 업체들(r)], r.get('cntrctNm'),
            *원계약차수(r.get('cntrctDtlInfoUrl'))]


def 원계약차수(주소):
    m = re.search(r'ctrtNo=([^&]+)&ctrtChgOrd=(\d+)', 주소 or '')
    return [m.group(1), int(m.group(2))] if m else [None, None]


def 차수있나(경로):
    return os.path.exists(경로) and '차수' in 줄읽기(경로)['칸']


def 수의쓰기(경로, 줄):
    os.makedirs(os.path.dirname(경로), exist_ok=True)
    표 = {'칸': 수의칸, '줄': sorted(줄, key=lambda x: (x[1] or '', x[3] or ''))}
    with gzip.GzipFile(경로, 'wb', mtime=0) as f:
        f.write(json.dumps(표, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))


def 줄읽기(경로):
    with gzip.open(경로, 'rb') as f:
        return json.loads(f.read())


class 시간끝(Exception):
    pass


def 한달(키, 달, 낼곳, 마감=None, 사유만=False, 갈래들=길, 차수채움=False):
    끝날 = calendar.monthrange(int(달[:4]), int(달[4:]))[1]
    사전, 수의 = {}, []
    조각들 = []
    for 갈래 in 갈래들:
        조각 = os.path.join(낼곳, '조각', f'{달}_{갈래}.part.gz')
        수의조각 = os.path.join(수의곳, '조각', f'{달}_{갈래}.part.gz')   # 저장소 밖(R2) — data/bizno/조각 은 봇이 커밋한다
        조각들 += [조각, 수의조각]
        if (차수있나(수의조각) if 차수채움 else os.path.exists(수의조각)) and (사유만 or os.path.exists(조각)):
            한쪽수의 = 줄읽기(수의조각)['줄']
            한쪽사전 = {} if 사유만 else {(r['이름'], r['번호']): r for r in 줄읽기(조각)}
            print(f'  {달} {갈래} — 조각 있음')
        else:
            시작 = time.time()
            한쪽수의 = []
            # ⭐ 하루씩 묻는다 — 한 달로 물으면 서버가 쪽마다 한 달치를 다시 세어 999줄에 12~26초(뒤쪽일수록 느림),
            #    하루로 물으면 1~2.5초(2026-10-19 잼). 하루씩 센 합 = 한 달로 센 수(202502 공사 106,128). 부르는 횟수는 1할쯤 는다.
            #    날짜 넷을 한꺼번에 부른다 — 하루 한도는 부른 수로 세니 한도는 더 빨리 안 찬다. 합치는 건 날짜 차례대로.
            한쪽사전, 줄수 = {}, 0
            def 하루(날):
                사전, 수의 = {}, []
                n = 갈래받기(키, 갈래, f'{달}{날:02d}0000', f'{달}{날:02d}2359', 마감, 사전, 수의)[1]
                return n, 사전, 수의
            일꾼 = ThreadPoolExecutor(4)
            try:
                for n, 날사전, 날수의 in 일꾼.map(하루, range(1, 끝날 + 1)):
                    줄수 += n
                    한쪽수의 += 날수의
                    for 열쇠, r in 날사전.items():
                        if 열쇠 in 한쪽사전:
                            한쪽사전[열쇠]['건수'] += r['건수']
                        else:
                            한쪽사전[열쇠] = r
            finally:
                일꾼.shutdown(cancel_futures=True)   # 한 날이 막히면(한도·마감) 남은 날은 부르지 않고 멈춘다
            if not 사유만:
                파일쓰기(조각, 한쪽사전)
            수의쓰기(수의조각, 한쪽수의)
            print(f'  {달} {갈래} — 계약 {줄수:,}줄 · 지자체 수의 {len(한쪽수의):,} · {time.time() - 시작:.0f}초', flush=True)
        수의 += 한쪽수의
        for 열쇠, r in 한쪽사전.items():
            if 열쇠 in 사전:
                사전[열쇠]['건수'] += r['건수']
            else:
                사전[열쇠] = dict(r)
    return 사전, 수의, 조각들


def 파일쓰기(경로, 사전):
    표 = sorted(사전.values(), key=lambda r: -r['건수'])
    os.makedirs(os.path.dirname(경로), exist_ok=True)
    # mtime=0 — gzip 머리에 시각이 박히면 내용이 같아도 새 파일이 되어 저장소 역사에 쌓인다
    with gzip.GzipFile(경로, 'wb', mtime=0) as f:
        f.write(json.dumps(표, ensure_ascii=False).encode('utf-8'))
    return 표


def 갈래받기(키, 갈래, 처음, 끝, 마감=None, 사전=None, 수의=None):
    사전 = {} if 사전 is None else 사전
    수의 = [] if 수의 is None else 수의
    줄수 = 0
    쪽 = 1
    while True:
        if 마감 and time.time() > 마감:
            raise 시간끝(f'{갈래} {쪽}쪽')
        줄, 전체 = 부르기(갈래, 키, 처음, 끝, 쪽)
        if not 줄:
            break
        줄수 += len(줄)
        for r in 줄:
            if (한 := 수의줄(r, 갈래)):
                수의.append(한)
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


def 기간받기(키, 처음, 끝):
    사전, 수의 = {}, []
    줄수 = 0
    for 갈래 in 길:
        _, n = 갈래받기(키, 갈래, 처음, 끝, 사전=사전, 수의=수의)
        줄수 += n
    return 사전, 수의, 줄수


def 이번달하루치(키, 낼곳, 이번달, 사유끔=False):
    # ── 이번 달은 **하루치씩, 한 번만** 받는다(인자 없이 부를 때) ──
    # ⭐ 「늘 새로 받는다」와 「저장소가 안 붓는다」를 같이 지키는 길 — 계약 원본과 같은 모양이다.
    #    날짜 파일은 **새로 만들기만 하고 덮어쓰지 않는다.** 그날 뒤늦게 붙은 계약은
    #    다음 달에 받는 달 파일이 메운다. build_contracts_summary.py 가 둘 다 읽는다.
    하루 = 이번달 + '01'
    어제 = time.strftime('%Y%m%d', time.localtime(time.time() - 86400))
    while 하루 <= 어제 and 하루[:6] == 이번달:
        경로 = os.path.join(낼곳, '일', f'{하루}.json.gz')
        수의경로 = os.path.join(수의곳, '일', f'{하루}.json.gz')
        if not (os.path.exists(경로) and (사유끔 or os.path.exists(수의경로))):
            사전, 수의, 줄수 = 기간받기(키, f'{하루}0000', f'{하루}2359')
            if not os.path.exists(경로):           # 사전 날짜 파일은 덮어쓰지 않는다(위 ⭐)
                파일쓰기(경로, 사전)
            수의쓰기(수의경로, 수의)
            print(f'{하루} — 계약 {줄수:,}줄 · 업체 {len(사전):,}가지 · 지자체 수의 {len(수의):,} (하루치)')
        하루 = time.strftime('%Y%m%d', time.localtime(
            time.mktime(time.strptime(하루, '%Y%m%d')) + 86400 + 3600))


def main():
    이번달 = time.strftime('%Y%m')
    달들 = [a for a in sys.argv[1:] if a.isdigit() and len(a) == 6]
    다시 = '--다시' in sys.argv
    사유만 = '--사유만' in sys.argv
    사유끔 = '--사유끔' in sys.argv       # 봇이 R2 에서 못 내려받은 날 — 사유가 없어도 「있다」고 친다
    차수채움 = '--차수채움' in sys.argv   # 수의계약 파일에 차수 칸이 없으면 받은 달로 안 친다 — 조각도 차수 칸이 있어야 잇는다(며칠에 걸쳐 이어 받게)
    # 「--갈래 물품,공사」 — 한 갈래가 하루 한도에 막혔을 때 다른 갈래만 먼저 받는다. 조각만 남기고 달 파일은 안 쓴다(세 갈래가 다 차야 쓴다)
    갈래들 = sys.argv[sys.argv.index('--갈래') + 1].split(',') if '--갈래' in sys.argv else list(길)
    분 = float(sys.argv[sys.argv.index('--분') + 1]) if '--분' in sys.argv else (None if 달들 else 50)
    마감 = time.time() + 분 * 60 if 분 else None

    낼곳 = os.path.join(ROOT, 'data', 'bizno')
    os.makedirs(낼곳, exist_ok=True)

    if 달들:
        처음달, 끝달 = 달들[0], (달들[1] if len(달들) > 1 else 달들[0])
    else:
        # ⭐ 인자를 안 줘도 돌아야 한다 — 날마다 도는 봇이 달을 못 준다.
        #    **계약 원본의 첫 달부터** 이번 달까지 훑는다. 받아 둔 끝난 달은 아래에서 건너뛰므로
        #    빈 달만 메워진다(2026-09-29 — 마지막 달부터만 이으면 가운데 빈 달이 영영 안 찼다).
        # ⚠️ **나라장터는 하루 호출 한도가 있다** — 2026-09-29 에 여덟 갈래로 한꺼번에 받다가
        #    한 시간 만에 전부 `429 Too Many Requests`(용역)로 막혔다. 한 갈래로 날마다 조금씩 메운다.
        #    막히면 그 달은 저장이 안 되고 다음 날 그 달부터 다시 받는다.
        계약들 = sorted(os.path.basename(x)[:6]
                      for x in glob.glob(os.path.join(ROOT, 'data', 'contracts', '????????.json.gz')))
        # ⚠️ **달 파일은 지난달까지만.** 이번 달 파일을 날마다 다시 받아 덮어쓰면 저장소 역사에
        #    날마다 1.5MB 씩 쌓인다(한 해 500MB). 이번 달은 아래에서 **하루치 파일**로 받는다.
        해, 월 = int(이번달[:4]), int(이번달[4:])
        끝달 = f'{해 - 1}12' if 월 == 1 else f'{해}{월 - 1:02d}'
        처음달 = 계약들[0] if 계약들 else 끝달
        if 처음달 > 끝달:
            처음달 = 끝달
        print(f'달을 안 줬다 — {처음달} 부터 {끝달} 까지 이어 받는다')
    키 = 키읽기()
    if not 달들:
        이번달하루치(키, 낼곳, 이번달, 사유끔)      # 싸고(하루 몇 회) 급한 것부터

    차례 = []
    달 = 처음달
    while 달 <= 끝달:
        차례.append(달)
        해, 월 = int(달[:4]), int(달[4:])
        해, 월 = (해 + 1, 1) if 월 == 12 else (해, 월 + 1)
        달 = f'{해}{월:02d}'
    경로 = lambda 달: os.path.join(낼곳, f'{달}.json.gz')
    수의경로 = lambda 달: os.path.join(수의곳, f'{달}.json.gz')
    # 사전이 빈 달부터 — 수의계약만 빈 지난 달은 이 PC 가 `--사유만` 으로 메운다(2026-10-16)
    for 달 in sorted(차례, key=lambda 달: (os.path.exists(경로(달)), 달)):
        if 마감 and time.time() > 마감:
            print(f'{분:.0f}분이 지났다 — {달} 부터는 다음에 받는다')
            break
        # ⭐ 끝난 달만 건너뛴다. 이번 달은 계약이 계속 붙으니 늘 다시 받는다.
        if ((사유끔 or (차수있나(수의경로(달)) if 차수채움 else os.path.exists(수의경로(달)))) and (사유만 or os.path.exists(경로(달)))
                and not 다시 and 달 < 이번달):
            print(f'{달} — 이미 있다 (끝난 달이라 건너뛴다)')
            continue
        if 다시:
            for x in glob.glob(os.path.join(낼곳, '조각', f'{달}_*.part.gz')) + glob.glob(os.path.join(수의곳, '조각', f'{달}_*.part.gz')):
                os.remove(x)
        try:
            사전, 수의, 조각들 = 한달(키, 달, 낼곳, 마감, 사유만, 갈래들, 차수채움)
        except 시간끝 as e:
            print(f'{분:.0f}분이 지났다 — {e} 에서 멈춘다. 받은 갈래는 조각으로 남았다', flush=True)
            break
        if len(갈래들) < len(길):
            continue
        수의쓰기(수의경로(달), 수의)
        if not 사유만:
            표 = 파일쓰기(경로(달), 사전)
            번호있 = sum(1 for r in 표 if r['번호'])
            print(f'{달} — 업체 {len(표):,}가지 (번호 붙은 것 {번호있:,})', flush=True)
        print(f'{달} — 지자체 수의계약 {len(수의):,}줄', flush=True)
        for x in 조각들:
            if os.path.exists(x):
                os.remove(x)


if __name__ == '__main__':
    main()
