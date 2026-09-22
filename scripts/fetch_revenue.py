# 지방재정365에서 **세입 쪽 자료를 통째로** 받는다 — 돈이 어디서 들어오나.
#
#   python scripts/fetch_revenue.py             세입 관련 43종을 해마다 다 받는다
#   python scripts/fetch_revenue.py IIBBH ARBGT 그 코드만
#   python scripts/fetch_revenue.py --다시      이미 받아 둔 것도 다시
#
# 왜 — 지금까지 본 것은 **쓰는 쪽(세출·계약·보조금)**에 쏠려 있었다. 43종 가운데 4종만 쓰고 있었다.
#      ⭐ 감시 눈으로 보면 여기에 센 것이 있다 —
#        `ABDBC` 체납 누계액 · `CHABG` 지방세 지출현황(비과세·감면으로 **깎아 준 돈**)
#        `LLBSR` 지방교부세 **감액**현황(법령위반으로 감사에 적발돼 깎인 것)
#        `LLBSI` 교부세 인센티브 · `GNLAR/GNLAE` 자체노력 반영현황
#
# ⚠️ 키는 `.env` 의 `LOFIN_KEY`. 키가 없으면 한 쪽에 5행만 와서 못 쓴다.
# ⚠️ 해마다 따로 부른다. 자료마다 **있는 해가 다르다**(목록의 `years` 를 그대로 따른다).
# ⚠️ `SIHHC 세입현황` 은 `txrv_ymd`(기준일)까지 있어야 한다 — 없으면 빈손으로 온다.
#
# 결과 : data/revenue/<코드>.json.gz  (한 파일에 그 자료의 모든 해)

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
HUB = 'https://www.lofin365.go.kr/lf/hub/'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')
낱말 = ['세입', '지방세', '세외수입', '징수', '체납', '교부세']


def 키읽기():
    for 줄 in open(os.path.join(ROOT, '.env'), encoding='utf-8'):
        if 줄.startswith('LOFIN_KEY='):
            값 = 줄.split('=', 1)[1].strip()
            if 값:
                return 값
    raise SystemExit('.env 에 LOFIN_KEY 가 비어 있다')


def 목록():
    p = os.path.join(ROOT, 'data', 'lofin365_146.json')
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def 해범위(r):
    해 = str(r.get('years') or '')
    if '~' not in 해:
        return []
    처음, 끝 = 해.split('~')[0].strip(), 해.split('~')[1].strip()
    if not (처음.isdigit() and 끝.isdigit()):
        return []
    return list(range(int(처음), int(끝) + 1))


def 부르기(코드, 인자, 되풀이=3):
    q = dict(인자)
    q.update({'Type': 'json', 'pSize': 1000})
    마지막 = None
    for n in range(되풀이):
        try:
            url = HUB + 코드 + '?' + urllib.parse.urlencode(q)
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                본문 = json.loads(r.read().decode('utf-8'))
        except Exception as e:
            마지막 = e
            time.sleep(2 * (n + 1))
            continue
        if 'RESULT' in 본문:                    # 오류는 이 꼴로 온다
            return None, json.dumps(본문, ensure_ascii=False)[:120]
        덩이 = 본문.get(코드) or []
        머리 = 덩이[0]['head'] if 덩이 else []
        전체 = 0
        for h in 머리:
            if 'list_total_count' in h:
                전체 = h['list_total_count']
        줄 = 덩이[1]['row'] if len(덩이) > 1 else []
        return (줄, 전체), ''
    return None, repr(마지막)[:120]


# ⚠️ `fyr` 만으로는 안 되는 자료 — 해마다 덧붙일 인자를 여기 적는다.
#    `SIHHC 세입현황` 은 기준일(`txrv_ymd`)이 필수다. 없으면 `ERROR-300 필수 값 누락`.
덧인자 = {
    'SIHHC': lambda 해: {'txrv_ymd': f'{해}1231'},
}


def 한코드(코드, 해들, 키):
    담 = []
    빈해 = []
    탈 = []
    for 해 in 해들:
        쪽 = 1
        받 = 0
        전체 = None
        더 = 덧인자[코드](해) if 코드 in 덧인자 else {}
        while True:
            나온, 틀림 = 부르기(코드, {'Key': 키, 'fyr': 해, 'pIndex': 쪽, **더})
            if 나온 is None:
                탈.append(f'{해}:{틀림[:40]}')
                break
            줄, 전체 = 나온
            if not 줄:
                break
            for r in 줄:
                r['_해'] = 해
            담.extend(줄)
            받 += len(줄)
            if 받 >= (전체 or 0):
                break
            쪽 += 1
            time.sleep(0.1)
        if 받 == 0:
            빈해.append(str(해))
        time.sleep(0.1)
    return 담, 빈해, 탈


def main():
    다시 = '--다시' in sys.argv
    고른 = [a for a in sys.argv[1:] if not a.startswith('--')]
    키 = 키읽기()
    자료 = 목록()
    쓸것 = [r for r in 자료
           if any(n in json.dumps(r, ensure_ascii=False) for n in 낱말)]
    if 고른:
        쓸것 = [r for r in 쓸것 if r['code'] in 고른]
    낼곳 = os.path.join(ROOT, 'data', 'revenue')
    os.makedirs(낼곳, exist_ok=True)
    print(f'■ 세입 관련 {len(쓸것)}종\n')

    모두 = 0
    시작 = time.time()
    for i, r in enumerate(쓸것, 1):
        코드 = r['code']
        경로 = os.path.join(낼곳, f'{코드}.json.gz')
        if os.path.exists(경로) and not 다시:
            print(f'[{i:>2}/{len(쓸것)}] {코드} — 이미 있다')
            continue
        해들 = 해범위(r)
        담, 빈해, 탈 = 한코드(코드, 해들, 키)
        with gzip.open(경로, 'wt', encoding='utf-8') as f:
            json.dump(담, f, ensure_ascii=False)
        모두 += len(담)
        꼬리 = ''
        if 빈해:
            꼬리 += f' · 빈 해 {len(빈해)}개'
        if 탈:
            꼬리 += f' · ⚠ 탈 {len(탈)}건 {탈[0][:40]}'
        print(f'[{i:>2}/{len(쓸것)}] {코드:<8} {str(r.get("name"))[:26]:<28} '
              f'{len(담):>7,}줄 · {len(해들)}해{꼬리}')

    print(f'\n  모두 {모두:,}줄 · {time.time() - 시작:.0f}초 · data/revenue/')


if __name__ == '__main__':
    main()
