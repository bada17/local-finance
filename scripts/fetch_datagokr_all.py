# 공공데이터포털 목록을 **통째로** 받아 둔다. 거르는 것은 우리 손으로 한다.
#
#   python scripts/fetch_datagokr_all.py           오픈API 17,035건
#   python scripts/fetch_datagokr_all.py --파일     파일데이터 211,981건도 (무겁다)
#   python scripts/fetch_datagokr_all.py --다시     새로 받는다
#
# 왜 — 낱말로 찾으면 **제목에 그 말이 든 것만** 걸린다. 「민간위탁」을 안 떠올리면
#      민간위탁 자료는 없는 것이 된다. 목록을 다 쥐고 있어야 **「없다」고 말할 수 있다.**
#
# ⚠️ 키는 `.env` 의 `DATA_GO_KR_KEY`. 목록조회서비스(15077093) 활용신청이 돼 있어야 한다.
# ⚠️ 한 줄에 44칸이 온다(끝점·요청인자·출력칸 이름까지). **대화창에 쏟지 말고 세어서 말할 것.**

import gzip
import json
import os
import sys
import time
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 'https://api.odcloud.kr/api/15077093/v1'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')


def 키읽기():
    for 줄 in open(os.path.join(ROOT, '.env'), encoding='utf-8'):
        if 줄.startswith('DATA_GO_KR_KEY='):
            값 = 줄.split('=', 1)[1].strip()
            if 값:
                return 값
    raise SystemExit('.env 에 DATA_GO_KR_KEY 가 비어 있다')


def 부르기(길, q, 되풀이=4):
    url = f'{BASE}/{길}?' + urllib.parse.urlencode(q)
    끝 = None
    for n in range(되풀이):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            끝 = e
            time.sleep(3 * (n + 1))
    raise SystemExit(f'네 번 다 실패({길}): {끝!r}')


def 통째로(길, 키, 이름):
    담 = []
    쪽 = 1
    전체 = None
    시작 = time.time()
    while True:
        d = 부르기(길, {'page': 쪽, 'perPage': 1000, 'serviceKey': 키})
        줄 = d.get('data') or []
        if 전체 is None:
            전체 = d.get('totalCount', 0)
            print(f'  {이름} 전체 {전체:,}건 · 1,000씩 {-(-전체 // 1000)}번')
        담.extend(줄)
        if not 줄 or len(담) >= 전체:
            break
        쪽 += 1
        if 쪽 % 20 == 0:
            print(f'    … {len(담):,}/{전체:,} · {time.time() - 시작:.0f}초')
        time.sleep(0.15)
    return 담, 전체


def main():
    다시 = '--다시' in sys.argv
    파일도 = '--파일' in sys.argv
    키 = 키읽기()
    낼곳 = os.path.join(ROOT, 'data')

    할것 = [('open-data-list', '오픈API', 'datagokr_api_list.json.gz')]
    if 파일도:
        할것.append(('file-data-list', '파일데이터', 'datagokr_file_list.json.gz'))

    for 길, 이름, 파일 in 할것:
        경로 = os.path.join(낼곳, 파일)
        if os.path.exists(경로) and not 다시:
            print(f'{이름} — 이미 있다: data/{파일} (다시 받으려면 --다시)')
            continue
        담, 전체 = 통째로(길, 키, 이름)
        with gzip.open(경로, 'wt', encoding='utf-8') as f:
            json.dump(담, f, ensure_ascii=False)
        기관 = {r.get('org_nm') for r in 담}
        자료 = {r.get('list_id') for r in 담}
        크기 = os.path.getsize(경로) / 1024 / 1024
        print(f'  받음 {len(담):,}/{전체:,} · 자료 {len(자료):,}종 · 기관 {len(기관):,}곳')
        print(f'  저장 data/{파일} ({크기:,.1f} MB)')
        if len(담) != 전체:
            print('  ⚠ 건수가 안 맞는다. 다시 받을 것')


if __name__ == '__main__':
    main()
