# 열린재정(기획재정부·한국재정정보원) OpenAPI 를 받는다 — data/openfiscal_198.json 목록 가운데 부를 수 있는 것 전부
#   (2026-11-02 사용자 「열린재정 연결 지금은 하나도 안 되어 있는데」 — 키는 깃허브 Secrets OPENFISCAL_KEY 에 9/22 부터 있었다)
#
#   python scripts/fetch_openfiscal.py              부를 수 있는 것 전부(목록의 stat 「바로조회」·「인자필요」 87종)
#   python scripts/fetch_openfiscal.py OPFI167 ...  그것만
#
# ⚠️ 키가 없으면 한 쪽에 5줄로 잘린다 — 그래서 봇(openfiscal.yml)이 Secrets 키로 돈다. 서비스마다 하루 1,000번.
# ⚠️ 응답이 JSON 을 한 번 더 문자열로 싼 꼴로 온다(「"{\"OPFI167\":…}"」) — 두 번 푼다.
# ⚠️ 「없음」 107종은 그 이름으로 등록된 서비스가 없다(ERROR-310, 2026-09-21, 11-02 dsId 로도 다시 봄) — 키 문제가 아니라 안 부른다.
# 회계연도(ACNT_YR)가 꼭 있어야 하는 47종은 2007 년부터 올해까지 해마다 부른다(「…추이」도 해를 받아 그해 줄만 준다).
# 전부 중앙정부 총량이다 — 자치단체로 안 쪼개진다(지방교부세·국고보조 총량처럼 견줄 거리로 쓴다).
# 결과: data/openfiscal/<코드>.json.gz {만든날, 이름, 분류, 설명, 칸, 줄}

import gzip, json, os, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import date

import keys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'openfiscal')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'   # WAF 가 curl 을 막는다
쪽 = 1000


def 받기(코드, q):
    return urllib.request.urlopen(urllib.request.Request(
        f'https://openapi.openfiscaldata.go.kr/{코드}?{q}', headers={'User-Agent': UA}), timeout=120).read()


def 부르기(코드, 키, 인자, 몇째):
    q = urllib.parse.urlencode({'Key': 키, 'Type': 'json', 'pIndex': 몇째, 'pSize': 쪽, **인자})
    for n in range(4):
        try:
            s = json.loads(받기(코드, q).decode('utf-8'))
            try:
                s = json.loads(s) if isinstance(s, str) else s
            except json.JSONDecodeError:
                # 큰 쪽에서 JSON 이 깨져 오는 것이 있다(VW_OPFI372·376·377·383 「Expecting ','」, 2026-11-02) — 같은 것을 XML 로 받는다.
                #   ponytail: XML 은 숫자도 글자로 온다 — 쓸 때 숫자로 바꿀 것
                t = ET.fromstring(받기(코드, q.replace('Type=json', 'Type=xml')))
                return int(t.findtext('head/list_total_count') or 0), [{c.tag: c.text for c in r} for r in t.findall('row')], \
                    t.findtext('head/RESULT/CODE') or t.findtext('RESULT/CODE') or '?'
            if 코드 not in s:      # {"RESULT": {"CODE": "INFO-200", …}} — 그 해 자료 없음
                return 0, [], (s.get('RESULT') or {}).get('CODE', '?')
            머리, 몸 = s[코드][0]['head'], s[코드][1]['row']
            return 머리[0]['list_total_count'], 몸, 머리[1]['RESULT']['CODE']
        except Exception as e:
            끝 = e
            time.sleep(5 * (n + 1))
    raise RuntimeError(f'{코드} {인자} 네 번 다 실패: {끝!r}')


def 다받기(코드, 키, 인자):
    줄, 몇째 = [], 1
    while True:
        총, 몸, _ = 부르기(코드, 키, 인자, 몇째)
        줄 += 몸
        if not 몸 or len(줄) >= 총:
            return 줄
        몇째 += 1
        time.sleep(0.3)


def main():
    키 = keys.키읽기('OPENFISCAL_KEY')
    목록 = json.load(open(os.path.join(ROOT, 'data', 'openfiscal_198.json'), encoding='utf-8'))
    목록 = [x for x in 목록 if x.get('stat') in ('바로조회', '인자필요') and (not sys.argv[1:] or x['code'] in sys.argv[1:])]
    os.makedirs(OUT, exist_ok=True)
    틀림 = []
    for x in 목록:
        필수 = [r['id'] for r in x.get('req', []) if '필수' in (r.get('type') or '')]
        if 필수 not in ([], ['ACNT_YR']):
            print(f'{x["code"]} 건너뜀 — 필수 인자 {필수}', flush=True)
            continue
        # 서비스 이름은 대개 code(OPFI167)로 되지만 dsId(VW_OPFI169)로만 답하는 것이 있다 — 지방정부부채추이·중앙정부결산·국유재산 등 22종(2026-11-02).
        #   code 로 「서비스 없음(ERROR-310)」이면 dsId 로 부른다. 「없음」 107종은 dsId 로도 310 이다
        이름 = x['code']
        try:
            if x.get('dsId') and x['dsId'] != 이름 and 부르기(이름, 키, {}, 1)[2] == 'ERROR-310':
                이름 = x['dsId']
            줄 = [] if 필수 else 다받기(이름, 키, {})
            if not 줄:   # 목록엔 필수 인자가 없어도 회계연도를 줘야 답하는 것이 있다(OPFI165 16대분야별 재원배분, 2026-11-02)
                줄 = [r for 해 in range(2007, date.today().year + 1) for r in 다받기(이름, 키, {'ACNT_YR': 해})]
        except RuntimeError as e:
            틀림.append(str(e))
            print(f'⚠️ {e}', flush=True)
            continue
        if not 줄:   # 9월엔 되던 것이 ERROR-310(서비스 없음)으로 바뀐 것이 있다(OPFI169 지방정부부채추이 등, 11-02) — 빈 파일은 안 남긴다
            틀림.append(f'{x["code"]} {x["odtNm"]} 0줄')
            print(f'⚠️ {x["code"]} {x["odtNm"]} 0줄', flush=True)
            continue
        with gzip.open(os.path.join(OUT, f'{x["code"]}.json.gz'), 'wt', encoding='utf-8') as f:
            json.dump({'만든날': date.today().isoformat(), '이름': x['odtNm'], '분류': x.get('cls'), '설명': x.get('epl'),
                       '칸': {r['id']: r['nm'] for r in x.get('out', [])}, '줄': 줄}, f, ensure_ascii=False)
        print(f'{x["code"]} {x["odtNm"]} {len(줄):,}줄', flush=True)
    print(f'끝 — {len(목록) - len(틀림)}/{len(목록)}종', flush=True)
    if 틀림 and len(틀림) == len(목록):
        sys.exit(1)


if __name__ == '__main__':
    main()
