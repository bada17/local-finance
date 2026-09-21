# 지방재정365 OpenAPI 수집기
#
#   python scripts/fetch_lofin.py HCDIB fyr=2026
#   python scripts/fetch_lofin.py QWGJK fyr=2026 exe_ymd=202608 laf_cd=1111000
#
# 인증키는 .env 의 LOFIN_KEY 에서 읽는다. 키가 없어도 돌아가지만 한 쪽에 5행만
# 오므로 호출 수가 200배로 뛴다. 243행짜리 연 단위 자료는 키 없이도 할 만하고,
# QWGJK 전국(46만 행)은 키가 있어야 한다.
#
# 결과는 data/raw/<코드>__<인자>.json 에 행 목록만 담아 저장한다.

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
HUB = 'https://www.lofin365.go.kr/lf/hub/'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')


def load_key():
    # 깃허브 액션에서는 Secrets 가 환경변수로 들어온다. 내 PC 에서는 .env 를 읽는다
    if os.environ.get('LOFIN_KEY'):
        return os.environ['LOFIN_KEY'].strip()
    path = os.path.join(ROOT, '.env')
    if not os.path.exists(path):
        return ''
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if line.startswith('LOFIN_KEY='):
            return line.split('=', 1)[1].strip()
    return ''


def call(code, params, tries=3):
    """한 쪽을 받아 (행 목록, 전체 건수) 로 돌려준다."""
    url = HUB + code + '?' + urllib.parse.urlencode(params)
    last = None
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                body = json.loads(r.read().decode('utf-8'))
        except Exception as e:
            last = e
            time.sleep(2 * (n + 1))
            continue
        # 오류는 {"RESULT":[{"CODE":"ERROR-xxx", ...}]} 꼴로 온다
        if 'RESULT' in body:
            raise SystemExit('오류 ' + json.dumps(body, ensure_ascii=False))
        blocks = body[code]
        total = blocks[0]['head'][0]['list_total_count']
        rows = blocks[1]['row'] if len(blocks) > 1 else []
        return rows, total
    raise SystemExit('세 번 다 실패: ' + repr(last))


def fetch(code, args, key=''):
    params = dict(args)
    params['Type'] = 'json'
    params['pSize'] = 1000 if key else 5
    if key:
        params['Key'] = key

    out = []
    page = 1
    total = None
    while True:
        params['pIndex'] = page
        rows, total = call(code, params)
        if not rows:
            break
        out.extend(rows)
        if page == 1:
            calls = -(-total // len(rows))
            print(f'  전체 {total:,}행 · 한 쪽 {len(rows)}행 · {calls:,}번 호출')
        if len(out) >= total:
            break
        page += 1
        if page % 20 == 0:
            print(f'  … {len(out):,}/{total:,}')
        time.sleep(0.1)
    return out, total


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__ or '쓰는 법: fetch_lofin.py <코드> <인자=값> ...')

    code = sys.argv[1]
    args = {}
    for a in sys.argv[2:]:
        k, _, v = a.partition('=')
        args[k] = v

    key = load_key()
    print(f'{code} {args} · 인증키 {"있음" if key else "없음(한 쪽 5행)"}')

    started = time.time()
    rows, total = fetch(code, args, key)

    tag = '_'.join(f'{k}-{v}' for k, v in sorted(args.items()))
    name = f'{code}__{tag}.json' if tag else f'{code}.json'
    path = os.path.join(ROOT, 'data', 'raw', name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    size = os.path.getsize(path) / 1024
    print(f'  받음 {len(rows):,}/{total:,}행 · {time.time() - started:.0f}초')
    print(f'  저장 data/raw/{name} ({size:,.0f} KB)')
    if len(rows) != total:
        print('  ⚠ 건수가 안 맞는다. 다시 받을 것')


if __name__ == '__main__':
    main()
