# CLIK 낱말 알림 — 정해 둔 의회·낱말로 새 회의록·의안이 올라오면 텔레그램으로 보낸다(내부용).
#
#   python scripts/watch_clik.py          새것만 보낸다 (텔레그램 열쇠가 없으면 --dry 와 같다)
#   python scripts/watch_clik.py --dry    안 보내고 안 적는다
#
# 왜 — 2026-10-06 사용자: "노들섬 관련 서울시의회 내용 받아보는게 있어야해".
#      CLIK 검색(searchKeyword)은 회의록 **본문까지** 뒤진다. 제목에 없어도 걸린다.
#
# 날마다 **끝 쪽까지** 다 받아 모음 파일(알림_모음.json)에 쌓는다 — 2026-10-08 사용자: "노들섬은 과거 논의를
# 모으는 형태여야 함(4~5년 전부터 나왔음)". 노들섬은 100건씩 7~8회. 상태.json 날짜별 호출에 같이 센다 —
# 그래서 봇에서는 **상세 받기보다 먼저** 돌린다(상세가 남은 한도를 다 쓴다).
# 처음 도는 낱말은 모음만 채우고 해마다 몇 건인지만 알린다(수백 통이 쏟아지지 않게).
#
# 텔레그램 열쇠는 TELEGRAM_TOKEN · TELEGRAM_CHAT_ID (저장소 Secrets). 공개 저장소라 값은 어디에도 안 적는다.

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

import fetch_clik as clik

# (낱말, 의회 코드, 모으기 시작, 텔레그램 시작) — 의회 코드는 data/clik/의회목록.json 의 rasmblyId. 늘리려면 줄만 더한다.
지켜볼것 = [
    # 서울특별시의회 · 2026-10-08 사용자: "18년도부터" 모으고, 텔레그램은 "올해 7월부터" 것만(전체는 정리만)
    ('노들섬', '002001', '20180101', '20260701'),
]

# ⭐ 서울시의회는 CLIK 에 2026-06-24 뒤 회의록이 없다(2026-10-12 확인 — 다른 의회는 7~9월치가 들어와 있다).
#    그래서 시의회 회의록 누리집(ms.smc.seoul.kr)의 회의록 검색을 같이 본다. CLIK 의 마지막 날짜 뒤만 보탠다.
#    본문 검색이고 서버가 그려 주는 표라 크롬이 필요 없다. 한 쪽 20줄, 번호 큰 것(새것)부터.
누리집 = {'002001': 'https://ms.smc.seoul.kr'}

모음파일 = os.path.join(clik.받는곳, '알림_모음.json')   # {의회코드:낱말: [{갈래, 날짜, 글, DOCID}]} 새것이 위


def 링크(이름, DOCID):
    """⚠️ collection 이 없으면 CLIK 이 「알 수 없는 오류」를 낸다(2026-10-08 확인)."""
    return (f'https://clik.nanet.go.kr/potal/search/searchView.do?DOCID={DOCID}'
            f"&collection={'minutes' if 이름 == '회의록' else 'bill'}")


갈래 = [  # 이름 · 끝점 · 정렬 · 날짜 칸 · 줄 → 한 줄 글
    ('회의록', 'minutes.do', 'MTG_DE/DESC', 'MTG_DE',
     lambda r: f"{r.get('MTG_DE', '')} {r.get('MTGNM', '')} 제{r.get('RASMBLY_SESN', '')}회 {r.get('MINTS_ODR', '')}차"),
    ('의안', 'bill.do', 'ITNC_DE/DESC', 'ITNC_DE',
     lambda r: f"{r.get('ITNC_DE', '')} {r.get('BI_SJ', '')} ({r.get('CL_STD_NM') or '처리 전'})"),
]


def 시의회누리집(뿌리, 낱말, 부터):
    """서울시의회 회의록 검색 → [{갈래, 날짜, 글, DOCID, 주소}]. 부터(YYYYMMDD) 앞 글만 나오는 쪽에서 멈춘다."""
    줄, 본키 = [], set()
    for 쪽 in range(1, 31):
        url = (f'{뿌리}/kr/assembly/recordLocation.do?sTh=0&keyword={urllib.parse.quote(낱말)}&pageNum={쪽}')
        for n in range(3):
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                본문 = urllib.request.urlopen(req, timeout=40).read().decode('utf-8', 'replace')
                break
            except Exception as e:
                if n == 2:
                    raise
                time.sleep(20 * (n + 1))
        몸 = 본문[본문.find('<tbody'):본문.find('</tbody>')]
        # ⚠️ 이 누리집은 pageNum 을 무시한다 — 몇 쪽이든 같은 첫 20줄(2026-10-14). 예전엔 같은 쪽을 30번 불러 봇(해외)에서
        #    한 번은 꼭 끊겼다(10-12 뒤 노들섬 멈춤). 새 글이 없는 쪽이면 멈춘다
        키들 = set(re.findall(r"recordView\.do\?key=([0-9a-f]+)", 몸))
        if not 키들 - 본키:
            break
        본키 |= 키들
        이쪽 = []
        for tr in re.findall(r'<tr>.*?</tr>', 몸, re.S):
            칸 = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)
            m = re.search(r"href='(/record/recordView\.do\?key=([0-9a-f]+)[^']*)'", tr)
            if len(칸) < 6 or not m:
                continue
            글자 = [re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', c))).strip() for c in 칸]
            날짜 = re.sub(r'\D', '', 글자[5])[:8]
            회, 차, 회의 = re.sub(r'\D', '', 글자[2]), re.sub(r'\D', '', 글자[3]), 글자[4]
            이쪽.append(날짜)
            if 날짜 >= 부터:
                줄.append({'갈래': '회의록', '날짜': 날짜, '글': f'{날짜} {회의} 제{회}회 {차}차',
                           'DOCID': 'SMC' + m.group(2)[:32], '주소': 뿌리 + m.group(1).split('&')[0]})
        if not 이쪽 or max(이쪽) < 부터:
            break
    return 줄


def 보내는날():
    """알림이 나가는 날 — 아침 보고(action-daily runtime.workday)와 같게 주말·공휴일(대체공휴일 포함)은 안 보낸다
    (2026-10-08 사용자). 그날 걸린 것은 다음 평일에 몰아서 간다.
    ponytail: 공휴일은 `holidays` 패키지 표 — 늦게 정해진 임시공휴일은 모를 수 있다."""
    import datetime as dt
    import holidays
    d = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)).date()
    return d.weekday() < 5 and d not in holidays.KR(years=d.year)


def 보내기(글):
    token, chat = os.environ['TELEGRAM_TOKEN'].strip(), os.environ['TELEGRAM_CHAT_ID'].strip()
    통들 = ['']   # 한 통 4,096자 한도 — 줄 단위로 끊는다(글자 수로 자르면 <a> 가 반으로 갈려 통째로 튕긴다)
    for 줄 in 글.split('\n'):
        if 통들[-1] and len(통들[-1]) + len(줄) > 3900:
            통들.append('')
        통들[-1] += 줄 + '\n'
    for 통 in 통들:
        req = urllib.request.Request(
            f'https://api.telegram.org/bot{token}/sendMessage',
            data=json.dumps({'chat_id': chat, 'text': 통, 'parse_mode': 'HTML',
                             'disable_web_page_preview': True}).encode(),
            headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=30).read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--다시보내기', action='store_true', help='텔레그램 시작일 뒤의 것을 전부 다시 보낸다')
    ap.add_argument('--마지막시도', action='store_true',
                    help='낮 재시도(assembly.yml) — 아침에 이미 됐으면 그냥 끝, 아니면 보고 못 해도 「못 봤음」을 보낸다')
    args = ap.parse_args()

    키 = clik.키읽기()
    상태 = clik.상태읽기()
    모음 = json.load(open(모음파일, encoding='utf-8')) if os.path.exists(모음파일) else {}
    의회 = {c['rasmblyId']: c['의회명'] for c in
            json.load(open(os.path.join(clik.받는곳, '의회목록.json'), encoding='utf-8'))}
    글들 = []
    오늘이미 = 모음.get('_마지막성공') == clik.오늘()   # 손으로 또 돌려도 「없음」을 두 번 보내지 않게
    if args.마지막시도 and 오늘이미:
        print('오늘 아침에 이미 됐다 — 낮 재시도 안 함')
        return
    하나라도못받음 = False

    for 낱말, 의회코드, 부터, 알림부터 in 지켜볼것:
        열쇠 = f'{의회코드}:{낱말}'
        처음 = 열쇠 not in 모음
        쌓인 = 모음.setdefault(열쇠, [])
        쌓인[:] = [x for x in 쌓인 if x['날짜'] >= 부터]
        본 = {x['DOCID'] for x in 쌓인}
        새줄, 못받음 = [], ''
        누리집글 = {x['글'] for x in 쌓인 if x['DOCID'].startswith('SMC')}
        for 이름, 끝점, 정렬, 날짜칸, 한줄 in 갈래:
            쪽 = 0
            while True:   # 끝 쪽까지
                d, 오류 = clik.부르기(끝점, {'key': 키, 'type': 'json', 'displayType': 'list',
                                          'startCount': 쪽, 'listCount': 100, 'sort': 정렬,
                                          'searchType': 'ALL', 'searchKeyword': 낱말,
                                          'rasmblyId': 의회코드})
                상태['날짜별호출'][clik.오늘()] = 상태['날짜별호출'].get(clik.오늘(), 0) + 1
                if d is None or 오류:
                    print(f'  {낱말} {이름}: 못 받음 — {오류}')
                    못받음 = '하루 호출 한도를 다 써서' if 오류 == 'ERROR09' else 'CLIK 이 응답하지 않아'
                    하나라도못받음 = True
                    break
                줄들 = [x.get('ROW', x) for x in (d.get('LIST') or [])]
                for r in 줄들:
                    if r.get('DOCID') and r['DOCID'] not in 본 and r.get(날짜칸, '') >= 부터:
                        본.add(r['DOCID'])
                        쌓인.append({'갈래': 이름, '날짜': r.get(날짜칸, ''), '글': 한줄(r), 'DOCID': r['DOCID']})
                        if r.get(날짜칸, '') >= 알림부터 and 한줄(r) not in 누리집글:   # 누리집에서 먼저 받은 회의는 또 안 보낸다
                            새줄.append(f"[{이름}] <a href=\"{링크(이름, r['DOCID'])}\">{html.escape(한줄(r))}</a>")
                쪽 += 100
                if not 줄들 or 쪽 >= int(d.get('TOTAL_COUNT') or 0):
                    break
        if 의회코드 in 누리집:   # CLIK 이 아직 안 받은 날짜만 — CLIK 회의록의 마지막 날부터
            clik끝 = max((x['날짜'] for x in 쌓인 if x['갈래'] == '회의록' and not x['DOCID'].startswith('SMC')), default=부터)
            try:
                있는글 = {x['글'] for x in 쌓인}
                for x in 시의회누리집(누리집[의회코드], 낱말, clik끝):
                    if x['DOCID'] in 본 or x['글'] in 있는글:
                        continue
                    본.add(x['DOCID']); 있는글.add(x['글']); 쌓인.append(x)
                    if x['날짜'] >= 알림부터:
                        새줄.append(f"[회의록·시의회] <a href=\"{x['주소']}\">{html.escape(x['글'])}</a>")
            except Exception as e:
                print(f'  {낱말} 시의회 누리집: 못 받음 — {e!r}'[:200])
                못받음 = 못받음 or '서울시의회 회의록 누리집이 응답하지 않아'
                하나라도못받음 = True
        쌓인.sort(key=lambda x: x['날짜'], reverse=True)
        머리 = f"🔔 <b>{html.escape(의회.get(의회코드, 의회코드))} · {html.escape(낱말)}</b>"
        if 처음:
            해 = {}
            for x in 쌓인:
                y = 해.setdefault(x['날짜'][:4], {})
                y[x['갈래']] = y.get(x['갈래'], 0) + 1
            글들.append(f"{머리}\n지난 것 {len(쌓인)}건을 모았다(저장소 data/clik/알림_모음.json). "
                       f"이제부터 새로 올라오는 것만 보낸다.\n"
                       + '\n'.join(f"{y}  " + ' · '.join(f'{k} {v}' for k, v in 해[y].items())
                                   for y in sorted(해, reverse=True)[:6]))
        elif args.다시보내기:   # 텔레그램 시작일 뒤의 것 전부(없어도 「0건」 한 통)
            줄 = [f"[{x['갈래']}] <a href=\"{x.get('주소') or 링크(x['갈래'], x['DOCID'])}\">{html.escape(x['글'])}</a>"
                 for x in 쌓인 if x['날짜'] >= 알림부터]
            글들.append(f"{머리} — {알림부터[:4]}-{알림부터[4:6]} 이후 {len(줄)}건 "
                       f"(모은 것 {len(쌓인)}건 중, 마지막 회의 {max((x['날짜'] for x in 쌓인), default='-')})\n"
                       + '\n'.join(줄))
        elif 새줄:
            글들.append(f"{머리} — 새로 {len(새줄)}건\n" + '\n'.join(새줄))
        elif 못받음:
            글들.append(f"{머리} — ⚠️ 오늘은 {못받음} 못 봤습니다. 내일 다시 봅니다.")
        elif not 오늘이미:   # 2026-10-08 사용자: 새것이 없으면 없다고 보낸다(하루 한 번)
            글들.append(f"{머리} — 오늘 새로 걸린 것 없음")
        print(f'  {낱말}({의회코드}): 새로 {len(새줄)}건{" (처음 — 모음만 채움)" if 처음 else ""}')

    # 열쇠가 없으면 모음에 적지 않는다 — 적으면 열쇠를 넣은 뒤에도 그 사이 것이 영영 안 온다.
    if args.dry or not (os.environ.get('TELEGRAM_TOKEN') and os.environ.get('TELEGRAM_CHAT_ID')):
        print('\n\n'.join(글들) or '(보낼 것 없음)')
        return
    if not args.다시보내기 and not 보내는날():
        clik.상태쓰기(상태)   # 모음은 안 적는다 — 적으면 다음 평일에 「새것」으로 안 잡힌다
        print('쉬는 날 — 안 보낸다(다음 평일에 몰아서)')
        return
    if 하나라도못받음 and not (args.마지막시도 or args.다시보내기):
        clik.상태쓰기(상태)   # 호출 수만 적고, 모음은 안 적는다(적으면 그 사이 새것이 안 간다) — 낮에 다시
        print('낮에 다시 본다 — 지금은 보내지 않는다')
        return
    if not 하나라도못받음:
        모음['_마지막성공'] = clik.오늘()
    for 글 in 글들:
        보내기(글)
    if args.다시보내기:   # 보내기만 — 파일을 고쳐 두면 assembly.yml 의 올리기(pull --rebase)가 막힌다
        return
    clik.상태쓰기(상태)
    json.dump(모음, open(모음파일, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
