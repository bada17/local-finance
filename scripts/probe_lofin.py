# 지방재정365 146종을 하나씩 눌러 보고, 되는지·몇 행 오는지 적는다.
#
#   python scripts/probe_lofin.py
#
# 필수인자가 뭔지는 spec_lofin.py 가 받아 둔 공식 명세(req 칸)에서 읽는다.
# 값은 인자 이름을 보고 채운다 — fyr 은 그 서비스의 보유연도 끝 해, 날짜 인자는
# 그 해 12월 31일, laf_cd 는 서울 종로구. 그래도 안 되면 한 해씩 뒤로 물러난다.
#
# 한 쪽(인증키 없으면 5행 고정)만 받으면 되는지 보기에 충분하다.
#
# data/lofin365_146.json 에 다음 칸을 덧붙인다.
#   stat  : 열림 / 자료없음 / 없음 / 미해결
#   args  : 통한 인자 조합
#   total : 그 조합에서의 전체 건수

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HUB = 'https://www.lofin365.go.kr/lf/hub/'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')


def call(code, args, tries=2):
    p = dict(args)
    p['Type'] = 'json'
    p['pIndex'] = 1
    p['pSize'] = 5
    url = HUB + code + '?' + urllib.parse.urlencode(p)
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                body = json.loads(r.read().decode('utf-8'))
            break
        except Exception:
            if n == tries - 1:
                return 'NET-ERR', [], 0
            time.sleep(2 * (n + 1))
    if 'RESULT' in body:
        x = body['RESULT']
        x = x[0] if isinstance(x, list) else x
        return x.get('CODE', '?'), [], 0
    blocks = body.get(code)
    if not blocks:
        return 'NO-BODY', [], 0
    head = blocks[0]['head']
    total = head[0]['list_total_count']
    info = head[1]['RESULT']['CODE']
    rows = blocks[1]['row'] if len(blocks) > 1 else []
    return (None if info == 'INFO-000' else info), rows, total


def fill(param_id, year):
    """인자 이름을 보고 값을 정한다."""
    if param_id == 'fyr':
        return year
    if param_id.endswith('_cd'):
        return '1111000'          # 서울 종로구
    if param_id.endswith('ymd'):
        return year + '1231'
    if param_id.endswith('ym'):
        return year + '12'
    return year


def years_of(r):
    """보유연도 끝 해부터 거꾸로 네 해."""
    found = re.findall(r'(\d{4})', r.get('years') or '')
    last = int(found[-1]) if found else 2025
    return [str(last - i) for i in range(4)]


def probe(r):
    need = [q['id'] for q in r.get('req', []) if q['need'] == '필수']
    empty = None
    for year in years_of(r):
        args = {p: fill(p, year) for p in need}
        err, rows, total = call(r['code'], args)
        if err is None and rows:
            return {'stat': '열림', 'args': args, 'total': total,
                    'out': sorted(rows[0]), 'sample': rows[0]}
        if err is None:
            empty = {'stat': '자료없음', 'args': args, 'total': total, 'out': [], 'sample': None}
        elif err == 'ERROR-310':
            return {'stat': '없음', 'args': args, 'total': 0, 'out': [], 'sample': None}
        if not need:
            break
        time.sleep(0.1)
    return empty or {'stat': '미해결', 'args': None, 'total': 0, 'out': [], 'sample': None}


def main():
    path = os.path.join(ROOT, 'data', 'lofin365_146.json')
    rows = json.load(open(path, encoding='utf-8'))

    for n, r in enumerate(rows, 1):
        r.update(probe(r))
        extra = f"{r['total']:>9,}행" if r['total'] else ''
        print(f"{n:3}/{len(rows)} {r['code']:8} {r['stat']:5} {extra:>11}  {r['name'][:26]}")
        time.sleep(0.1)

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    print()
    tally = {}
    for r in rows:
        tally[r['stat']] = tally.get(r['stat'], 0) + 1
    for k, v in sorted(tally.items(), key=lambda x: -x[1]):
        print(f'  {k} {v}')


if __name__ == '__main__':
    main()
