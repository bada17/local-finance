# 지방교육재정알리미 수집기 — 17개 시·도교육청의 예산·결산 전수.
#
#   python scripts/fetch_edu.py              622종을 다 받는다 (몇 분)
#   python scripts/fetch_edu.py --limit 50   50종만
#   python scripts/fetch_edu.py --갈래 결산   한 갈래만
#   python scripts/fetch_edu.py --다시       받아 둔 것을 지우고 새로
#
# 왜 — 17개 시·도교육청은 243개 자치단체와 **축이 다르다.** 따로 세워야 한다
#      (2026-09-22 사용자). 무엇이 있는지는 `docs/교육재정알리미_638종.xlsx` 를 볼 것.
#
# ⭐ **다 받는다.** 값이 거의 안 든다 — 622종 전부가 **12.5만 줄**이고 호출 700회쯤,
#    응답이 0.1초라 **몇 분이면 끝난다**(2026-09-22 실측). 골라 받을 이유가 없다.
#    ⚠️ 16종은 서비스명이 아예 없어 못 받는다(예산서·결산서 같은 문서류).
#
# ⚠️ **`pSize` 최대는 1000이다.** 5000을 주면 오류가 아니라 **0건**이 온다. 조용히 빈 값이다.
# ⚠️ **`FSCL_Y` 는 무시된다.** 아무 해를 줘도 **2014~2024년이 통째로** 온다.
#    처음에 「그 해까지 최근 4년」인 줄 알았는데 그건 `pSize` 를 작게 줘서 잘린 것이었다.
# ⚠️ **`openapi.eduinfo.go.kr` 은 HTTPS 가 안 열린다.** http 로 부른다.
#
# ── 엉키지 않게 담는 법 (2026-09-22 사용자 걱정) ─────────────────────────────
# **트리가 둘이다.** 중첩 JSON 으로 담으면 둘 중 하나만 남는다. 그래서
# **줄은 평평하게 담고, 트리는 줄마다 칸으로 박는다.** 그러면 언제든 트리로 다시 세운다.
#
#   ① 자료의 트리 — `dsId` 에 들어 있다. `VW_CLSG01020103` =
#      결산(CLSG) + 대분류01 + 중분류02 + 소분류01 + 순번03. 포털 화면의 나무와 같다.
#   ② 항목의 트리 — `ITEM_CD2` 가 **앞 빈칸으로 단을 나눈다.**
#      「세입결산액」(0칸) 밑에 「      이전수입」(6칸)이 붙는 식이다.
#
# ⚠️⚠️ **②를 놓치면 합계가 정확히 두 배가 된다.** 합계줄과 항목줄이 같은 칸에 있어서다.
# ⚠️ **들여쓰기 폭이 서비스마다 다르다** — 결산은 6칸, 예산은 8칸. 나눗셈으로 깊이를
#    계산하면 틀린다. **그 묶음 안에 나온 폭을 모아 순위를 매겨** 깊이를 정한다.
# ⚠️ **`strip()` 한 값만 담으면 영영 못 되돌린다.** 그래서 `항목원본` 을 빈칸째로 같이 남긴다.

import argparse
import glob
import gzip
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import keys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
받는곳 = os.path.join(ROOT, 'data', 'edu')
상태파일 = os.path.join(받는곳, '상태.json')
BASE = 'http://openapi.eduinfo.go.kr/openApi.do'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')

한번에 = 1000        # ⚠️ 이보다 크게 주면 0건이 온다


def 쪼갬(ds):
    m = re.match(r'VW_(CLSG|BUDG)(\d{2})(\d{2})(\d{2})(\d{2})', ds or '')
    return m.groups() if m else None


def 부르기(서비스, 쪽, 되풀이=3):
    키 = keys.키읽기('EDU_ALIMI_KEY')
    q = {'requestType': 서비스, 'key': 키, 'type': 'json',
         'pIndex': 쪽, 'pSize': 한번에}
    url = BASE + '?' + urllib.parse.urlencode(q)
    마지막 = None
    for n in range(되풀이):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                본문 = r.read().decode('utf-8', 'replace').replace(키, '<키>')
            return json.loads(본문), None
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
            마지막 = str(e)
            if n < 되풀이 - 1:
                time.sleep(2 * (n + 1))
    return None, 마지막


def 깊이매기기(줄들):
    """ITEM_CD2 앞 빈칸으로 단을 매긴다.

    ⚠️ 폭이 서비스마다 다르다(결산 6칸·예산 8칸). 그래서 나누지 않고
       **나온 폭을 모아 순위**로 깊이를 정한다. 상위항목도 여기서 붙인다.
    """
    폭들 = sorted({len(t) - len(t.lstrip()) for t in
                  (r.get('ITEM_CD2') or '' for r in 줄들)})
    단 = {w: i for i, w in enumerate(폭들)}
    위 = {}            # 깊이 → 그 깊이의 마지막 항목 이름
    매긴것 = []
    for r in 줄들:
        원본 = r.get('ITEM_CD2') or ''
        빈칸 = len(원본) - len(원본.lstrip())
        깊이 = 단.get(빈칸, 0)
        이름 = 원본.strip()
        위[깊이] = 이름
        for d in list(위):
            if d > 깊이:
                del 위[d]
        매긴것.append((이름, 원본, 깊이, 위.get(깊이 - 1, '') if 깊이 else ''))
    return 매긴것


# ⚠️⚠️ **칸 이름이 서비스마다 다르다.** 622종 가운데 **80%는** `YMQ·ITEM_CD1·ITEM_CD2·AMT`
#    넉 칸이지만, **나머지 20%(5만 줄)는 칸이 통째로 다르다** — 그리고 **그쪽이 더 값지다.**
#      집행내역   FSCL_Y · SD_EDU_OFFC_DIV_NM · AID_BIZ_NM · **AID_BIZR(보조사업자)** · AID_AMT
#      재정분석   FSCL_Y · INDCT · ARTC_NM · EDU_OFFC(값)
#      중기계획   FSCL_Y_P0~P4 (5개년 전망) · Y_SUM · Y_AVG_VARI
#      교부금 감액 REDCT_INCR_AMT_REAS(사유) · AMT
#    ⛔ **정해진 칸만 꺼내 담으면 이것들이 통째로 사라진다.** 2026-09-22 에 한 번 그렇게 담았다가
#       5만 줄이 빈 칸으로 들어간 것을 보고 고쳤다.
#    → **원본 줄을 통째로 남기고**, 공통 칸은 **여러 이름을 맞춰** 채운다.
연도칸 = ['YMQ', 'FSCL_Y']
지역칸 = ['ITEM_CD1', 'SD_EDU_OFFC_DIV_NM']
지역코드칸 = ['ITEM_CD1_SEQ', 'SD_EDU_OFFC_DIV']
항목칸 = ['ITEM_CD2', 'AID_BIZ_NM', 'ARTC_NM', 'PUB_ANUC_DETL_NM', 'INDCT']
금액칸 = ['AMT', 'AID_AMT', 'EDU_OFFC', 'Y_SUM']


def 골라(x, 후보):
    for k in 후보:
        v = x.get(k)
        if v not in (None, '', 'None'):
            return v, k
    return '', ''


def 한서비스(r):
    """한 서비스를 통째로 받아 평평한 줄로 돌려준다."""
    서비스 = r['service']
    g = 쪼갬(r.get('dsId'))
    갈래 = {'CLSG': '결산', 'BUDG': '예산'}.get(g[0], '그밖') if g else '그밖'
    묶음 = []
    쪽 = 1
    호출 = 0
    while True:
        d, 오류 = 부르기(서비스, 쪽)
        호출 += 1
        if d is None:
            return None, 호출, f'오류 — {오류}'
        L = d.get('RESULT_LIST') or []
        묶음.extend(L)
        전체 = int(d.get('TOTAL_CNT') or 0)
        if not L or len(묶음) >= 전체:
            break
        쪽 += 1

    # 깊이는 **묶음(서비스·지역·연도)마다 따로** 매긴다 — 들여쓰기 폭이 서비스마다 다르다.
    # ITEM_CD2 가 없는 모양은 계층이 아예 없으니 깊이 0 으로 둔다.
    칸별 = {}
    for x in 묶음:
        연, _ = 골라(x, 연도칸)
        지, _ = 골라(x, 지역칸)
        칸별.setdefault((지, 연), []).append(x)

    줄들 = []
    for (지역, 연도), 것들 in 칸별.items():
        계층있나 = any('ITEM_CD2' in x for x in 것들)
        매긴것 = 깊이매기기(것들) if 계층있나 else [
            (골라(x, 항목칸)[0],골라(x, 항목칸)[0], 0, '') for x in 것들]
        for x, (이름, 원본, 깊이, 상위) in zip(것들, 매긴것):
            지코드, _ = 골라(x, 지역코드칸)
            금액, 금액이름 = 골라(x, 금액칸)
            줄들.append({
                '갈래': 갈래,
                '대': g[1] if g else '', '중': g[2] if g else '',
                '소': g[3] if g else '', '순번': g[4] if g else '',
                'dsId': r.get('dsId') or '', '서비스': 서비스,
                '자료이름': r.get('name') or '',
                '회계연도': 연도, '지역': 지역, '지역코드': 지코드,
                '항목': 이름, '항목원본': 원본,
                '항목깊이': 깊이, '상위항목': 상위,
                '금액': 금액, '금액칸': 금액이름,
                # ⛔ 원본을 통째로 남긴다 — 위의 공통 칸으로는 못 담는 것이 많다
                #    (보조사업자·사유·5개년 전망 따위). 지우면 다시 받아야 한다.
                '원본': x,
            })
    return 줄들, 호출, None


def 상태읽기():
    if os.path.exists(상태파일):
        return json.load(open(상태파일, encoding='utf-8'))
    return {'서비스': {}, '마지막수집': None}


def 상태쓰기(상태):
    os.makedirs(받는곳, exist_ok=True)
    json.dump(상태, open(상태파일, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0, help='이번에 받을 서비스 수')
    ap.add_argument('--갈래', choices=['예산', '결산'])
    ap.add_argument('--다시', action='store_true')
    args = ap.parse_args()

    자료 = json.load(open(os.path.join(ROOT, 'data', 'eduinfo_catalog.json'),
                        encoding='utf-8'))
    받을것 = [r for r in 자료 if r.get('service')]
    if args.갈래:
        앞 = 'VW_BUDG' if args.갈래 == '예산' else 'VW_CLSG'
        받을것 = [r for r in 받을것 if (r.get('dsId') or '').startswith(앞)]
    if args.limit:
        받을것 = 받을것[:args.limit]

    os.makedirs(받는곳, exist_ok=True)
    if args.다시:
        for p in glob.glob(os.path.join(받는곳, '*.json.gz')):
            os.remove(p)
        상태 = {'서비스': {}, '마지막수집': None}
        print('지웠다')
    else:
        상태 = 상태읽기()

    # ⭐ 다 다시 받는다 — 값이 거의 안 들고, 해마다 자료가 는다.
    #    「파일이 있으면 건너뛴다」로 짜면 옛 숫자가 굳는다.
    담 = {}
    호출합 = 0
    실패 = []
    시작 = time.time()
    for i, r in enumerate(받을것, 1):
        줄들, 호출, 오류 = 한서비스(r)
        호출합 += 호출
        if 오류:
            실패.append((r['service'], 오류))
            continue
        g = 쪼갬(r.get('dsId'))
        열쇠 = f"{ {'CLSG':'결산','BUDG':'예산'}.get(g[0],'그밖') if g else '그밖' }_{g[1] if g else '00'}"
        담.setdefault(열쇠, []).extend(줄들)
        상태['서비스'][r['service']] = {'줄수': len(줄들), '자료이름': r.get('name')}
        if i % 50 == 0:
            print(f'  {i}/{len(받을것)}종 · {sum(len(v) for v in 담.values()):,}줄 '
                  f'· {time.time() - 시작:.0f}초')

    for 열쇠, 줄들 in sorted(담.items()):
        경로 = os.path.join(받는곳, f'{열쇠}.json.gz')
        with gzip.open(경로, 'wt', encoding='utf-8') as f:
            json.dump(줄들, f, ensure_ascii=False)
        print(f'  {열쇠}: {len(줄들):,}줄 · {os.path.getsize(경로)/1024:,.0f} KB')

    상태['마지막수집'] = time.strftime('%Y-%m-%d')
    상태['줄수합'] = sum(len(v) for v in 담.values())
    상태['호출'] = 호출합
    상태쓰기(상태)
    print(f'{len(받을것)}종 · {호출합}회 불러 {상태["줄수합"]:,}줄 '
          f'· {time.time() - 시작:.0f}초')
    if 실패:
        print(f'⚠️ 못 받은 것 {len(실패)}개:', ', '.join(s for s, _ in 실패[:8]))


if __name__ == '__main__':
    main()
