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
import sys
import urllib.request

import fetch_clik as clik

# (낱말, 의회 코드) — 의회 코드는 data/clik/의회목록.json 의 rasmblyId. 늘리려면 줄만 더한다.
지켜볼것 = [
    ('노들섬', '002001'),   # 서울특별시의회
]

모음파일 = os.path.join(clik.받는곳, '알림_모음.json')   # {의회코드:낱말: [{갈래, 날짜, 글, DOCID}]} 새것이 위
링크 = 'https://clik.nanet.go.kr/potal/search/searchView.do?DOCID='
갈래 = [  # 이름 · 끝점 · 정렬 · 날짜 칸 · 줄 → 한 줄 글
    ('회의록', 'minutes.do', 'MTG_DE/DESC', 'MTG_DE',
     lambda r: f"{r.get('MTG_DE', '')} {r.get('MTGNM', '')} 제{r.get('RASMBLY_SESN', '')}회 {r.get('MINTS_ODR', '')}차"),
    ('의안', 'bill.do', 'ITNC_DE/DESC', 'ITNC_DE',
     lambda r: f"{r.get('ITNC_DE', '')} {r.get('BI_SJ', '')} ({r.get('CL_STD_NM') or '처리 전'})"),
]


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
    args = ap.parse_args()

    키 = clik.키읽기()
    상태 = clik.상태읽기()
    모음 = json.load(open(모음파일, encoding='utf-8')) if os.path.exists(모음파일) else {}
    의회 = {c['rasmblyId']: c['의회명'] for c in
            json.load(open(os.path.join(clik.받는곳, '의회목록.json'), encoding='utf-8'))}
    글들 = []

    for 낱말, 의회코드 in 지켜볼것:
        열쇠 = f'{의회코드}:{낱말}'
        처음 = 열쇠 not in 모음
        쌓인 = 모음.setdefault(열쇠, [])
        본 = {x['DOCID'] for x in 쌓인}
        새줄 = []
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
                    break
                줄들 = [x.get('ROW', x) for x in (d.get('LIST') or [])]
                for r in 줄들:
                    if r.get('DOCID') and r['DOCID'] not in 본:
                        본.add(r['DOCID'])
                        쌓인.append({'갈래': 이름, '날짜': r.get(날짜칸, ''), '글': 한줄(r), 'DOCID': r['DOCID']})
                        새줄.append(f"[{이름}] <a href=\"{링크}{r['DOCID']}\">{html.escape(한줄(r))}</a>")
                쪽 += 100
                if not 줄들 or 쪽 >= int(d.get('TOTAL_COUNT') or 0):
                    break
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
        elif 새줄:
            글들.append(f"{머리} — 새로 {len(새줄)}건\n" + '\n'.join(새줄))
        print(f'  {낱말}({의회코드}): 새로 {len(새줄)}건{" (처음 — 모음만 채움)" if 처음 else ""}')

    # 열쇠가 없으면 모음에 적지 않는다 — 적으면 열쇠를 넣은 뒤에도 그 사이 것이 영영 안 온다.
    if args.dry or not (os.environ.get('TELEGRAM_TOKEN') and os.environ.get('TELEGRAM_CHAT_ID')):
        print('\n\n'.join(글들) or '(보낼 것 없음)')
        return
    for 글 in 글들:
        보내기(글)
    clik.상태쓰기(상태)
    json.dump(모음, open(모음파일, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
