# 인증키를 한 군데서 읽는다 — **환경변수 먼저, 그다음 `.env`**.
#
#   from keys import 키읽기
#   키 = 키읽기('DATA_GO_KR_KEY')
#   키 = 키읽기('OPENFISCAL_KEY', 필수=False)   # 없으면 빈 문자열
#
# 왜 — 깃허브 액션에서는 Secrets 가 **환경변수**로 들어오고 `.env` 는 아예 없다.
#      스크립트마다 `.env` 만 읽게 짜 두면 **Secrets 에 키를 넣어도 봇이 못 읽는다.**
#      2026-09-22 에 세어 보니 일곱 군데가 그랬다 — 키가 있는데도 자동 수집이 안 되는 상태였다.
#      오류도 "키가 비어 있다"로만 나서 원인을 찾기 어렵다.
#
# ⚠️ **새 수집기를 짤 때 키를 직접 읽지 말고 이걸 부를 것.** 같은 함정이 또 생긴다.
# ⚠️ 키 값은 **어디에도 찍지 않는다.** 공개 저장소다.

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 이 저장소가 쓰는 키 전부. `.env.example` · README 「키」 칸과 같은 목록이어야 한다.
아는키 = {
    'LOFIN_KEY': '지방재정365 (행안부) — 이 키 하나로 146종',
    'DATA_GO_KR_KEY': 'data.go.kr 조달청 — 나라장터 4종 + 국고보조금',
    'EDU_ALIMI_KEY': '지방교육재정알리미 (교육부)',
    'CLIK_KEY': '지방의정포털 CLIK (국회도서관) — 하루 1,000회 한도',
    'OPENFISCAL_KEY': '열린재정 (기재부) — 후순위, 아직 안 쓴다',
}


def 키읽기(이름, 필수=True):
    값 = (os.environ.get(이름) or '').strip()
    if 값:
        return 값
    경로 = os.path.join(ROOT, '.env')
    if os.path.exists(경로):
        for 줄 in open(경로, encoding='utf-8'):
            if 줄.startswith(이름 + '='):
                값 = 줄.split('=', 1)[1].strip()
                if 값:
                    return 값
    if 필수:
        raise SystemExit(
            f'{이름} 가 비어 있다.\n'
            f'  내 PC 에서 돌릴 때 — 저장소 맨 위 .env 에 {이름}=값 을 넣는다\n'
            f'  봇이 돌릴 때     — 저장소 Settings > Secrets and variables > Actions 에 '
            f'{이름} 을 넣는다')
    return ''


load_key = 키읽기      # 영어 이름으로 부르던 자리가 있다


def 있나(이름):
    """값을 돌려주지 않고 있는지만 본다. 점검용."""
    return bool(키읽기(이름, 필수=False))
