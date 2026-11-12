# e나라도움(bojo.go.kr) 보조사업 「사업경로」 수집기 — 국고보조금이 정부 > 시·도 > 시·군·구 > 단체로 어떻게 내려갔나(원문)
#
#   python scripts/fetch_bojo_paths.py 2024                  그 해 전 부처
#   python scripts/fetch_bojo_paths.py 2024 해양수산부        그 부처만
#
# 2026-11-12 사용자가 bojo 「보조사업정보」 팝업 링크를 줘서 찾은 호출(열쇠·CSRF 없음, bojo.do 쿠키만):
#   내역사업 목록  POST /ca/retrieveSearchListDtlbzAjax.do   bsnsyear·dtlbzCurPage·dtlbzPerPage → dtlbzList(ddtlzCnt 하위 수·pssrpCnt 공모 수)
#   내역사업 상세  POST /ca/retrieveDtlbzDetailAjax.do        bsnsyear·viewDtlbzId
#   하위 보조사업  POST /ca/retrieveDdtlbzPopListAjax.do      bsnsyear·dtlbzId·popDdtlbzCurPage·popDdtlbzPerPage → ddtlbzPopList
#   보조사업 상세  POST /ca/retrieveDdtlbzDetailAjax.do       bsnsyear·viewDdtlbzId → ddtlbzVO(dlvplNmPath 사업경로·govsuby 국비 천원…)
#   보조금정보     POST /fa/retrieveAbzmDetailCstsList7.do    fsyr·ddtlbzId·dlvplId → DATA(교부·집행, 천원) — 담아만 둔다(집행 분석은 사용자가 말할 때)
# 공시 여부 = 이미 받은 정보공시 목록(data/national_grants/<해>.json.gz)에 같은 보조사업 ID 가 있나 — 추가 호출 없음.
# ⚠️ 담당자 이름·전화·메일은 담지 않는다. 받은 곳 이름이 있어 결과는 data/raw/(저장소 밖)에 둔다.
# 결과: data/raw/bojo_paths_<해>[_<부처>].json.gz {만든날, 해, 부처, 내역사업: [...], 보조사업: [...]}

import gzip, http.cookiejar, json, os, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = 'https://www.bojo.go.kr'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
뺄칸 = {'telno', 'userNm', 'chargerNm', 'email', 'rprsntvNm', 'userCstmzdSearchVO', 'searchVO', 'faxNo', 'chrgDeptNm'}
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
op.addheaders = [('User-Agent', UA), ('X-Requested-With', 'XMLHttpRequest')]


def 부르기(길, **인자):
    for n in range(4):
        try:
            return json.loads(op.open(B + 길, urllib.parse.urlencode(인자).encode(), timeout=60).read())
        except Exception as e:
            끝 = e
            time.sleep(3 * (n + 1))
    raise RuntimeError(f'{길} {인자} 네 번 실패: {끝!r}')


깨끗 = lambda d: {k: v for k, v in d.items() if k not in 뺄칸 and v not in (None, '')}


def 개인보충(해, 부처들, 보조):
    """하위 목록 호출엔 개인(김** 등) 보조사업자가 안 나온다(해수부 2024: 바탕화면 목록에만 168줄) —
    data.go.kr 「기획예산처_국고보조금 정보」 보조사업현황(T_OPD_ASBS_IFPBNT, 목록과 같은 자료)에서 수집에 없는 줄을 더한다(경로·ID 없음)."""
    import html, re
    from keys import 키읽기
    키 = 키읽기('DATA_GO_KR_KEY', False)
    if not 키:
        print('⚠️ DATA_GO_KR_KEY 없음 — 개인 보충 건너뜀', flush=True)
        return []
    n = lambda s: re.sub(r'\s', '', html.unescape(str(s or '')))
    있음 = {(n(y['상세'].get('ddtlbzNm')), n(y['상세'].get('dlvplNm'))) for y in 보조}
    더 = []
    for 부처 in 부처들:
        for 쪽 in range(1, 1000):
            q = urllib.parse.urlencode({'serviceKey': 키, 'pageNo': 쪽, 'numOfRows': 1000, 'resultType': 'json', 'bsnsyear': 해, 'jrsd_nm': 부처})
            for t in range(4):
                try:
                    b = json.loads(urllib.request.urlopen(urllib.request.Request(
                        f'https://apis.data.go.kr/1051000/MoefOpenAPI/T_OPD_ASBS_IFPBNT?{q}', headers={'User-Agent': UA}), timeout=120).read())['response']['body']
                    break
                except Exception as e:
                    b = None; time.sleep(5 * (t + 1))
            it = ((b or {}).get('items') or {}).get('item') or []
            it = it if isinstance(it, list) else [it]
            # ⚠️ API 는 개인 실명을 그대로 준다(bojo 화면은 「이**」로 가림) — 한글 2~4자 이름은 성만 남긴다
            가림 = lambda s: (s[0] + '**') if re.fullmatch(r'[가-힣]{2,4}', str(s or '').strip()) else s
            더 += [{'목록에만': True, '상세': {'ddtlbzNm': x.get('DDTLBZ_NM'), 'dlvplNm': 가림(x.get('EXC_INSTT_NM')), 'jrsdNm': 부처,
                     'govsuby': x.get('GOVSUBY'), 'locgovAlotm': x.get('LOCGOV_ALOTM'), 'salm': x.get('SALM'), 'etcAlotm': x.get('ETC_ALOTM')}}
                   for x in it if (n(x.get('DDTLBZ_NM')), n(x.get('EXC_INSTT_NM'))) not in 있음]
            if not b or 쪽 * 1000 >= int(b.get('totalCount') or 0):
                break
    print(f'목록에만 있는 줄(개인 등) {len(더):,}개 더함', flush=True)
    return 더


def main():
    해, 부처 = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)
    op.open(B + '/bojo.do', timeout=60).read()   # 쿠키
    내역 = []
    for 쪽 in range(1, 10_000):
        L = 부르기('/ca/retrieveSearchListDtlbzAjax.do', bsnsyear=해, dtlbzCurPage=쪽, dtlbzPerPage=100).get('dtlbzList') or []
        내역 += [깨끗(x) for x in L if not 부처 or x.get('jrsdNm') == 부처]
        if not L or 쪽 * 100 >= int(L[0]['dtlbzTotCnt']):
            break
    print(f'내역사업 {len(내역):,}개', flush=True)

    def 내역상세(x):
        d = 부르기('/ca/retrieveDtlbzDetailAjax.do', bsnsyear=해, viewDtlbzId=x['dtlbzId'])
        x['상세'] = 깨끗(d.get('dtlbzVO') or {})
        if not int(x.get('ddtlzCnt') or 0):
            return []
        줄 = []
        for 쪽 in range(1, 10_000):
            L = 부르기('/ca/retrieveDdtlbzPopListAjax.do', bsnsyear=해, dtlbzId=x['dtlbzId'], popDdtlbzCurPage=쪽, popDdtlbzPerPage=100).get('ddtlbzPopList') or []
            줄 += [깨끗(y) for y in L]
            if not L or 쪽 * 100 >= int(L[0]['ddtlbzTotCnt']):
                return 줄

    with ThreadPoolExecutor(6) as ex:
        보조 = [y for 줄 in ex.map(내역상세, 내역) for y in 줄]
    print(f'보조사업 {len(보조):,}개', flush=True)

    def 보조상세(y):
        try:
            r = 부르기('/ca/retrieveDdtlbzDetailAjax.do', bsnsyear=해, viewDdtlbzId=y['ddtlbzId'])
            y['상세'] = 깨끗(r.get('ddtlbzVO') or {})
            if r.get('pssrpDetlList'):   # 공모 상세 — 공모사업별 정리에 쓴다(사용자 11-12)
                y['공모'] = [깨끗(p) for p in r['pssrpDetlList']]
            y['보조금정보'] = [깨끗(r) for r in 부르기('/fa/retrieveAbzmDetailCstsList7.do', fsyr=해, ddtlbzId=y['ddtlbzId'], dlvplId=y['상세'].get('dlvplId', '')).get('DATA') or []]
        except RuntimeError as e:   # 서버가 한 줄만 늘 500 을 내는 일이 있다(20240528000003057090, 11-12 — 전 부처 수집이 통째로 죽음) → 적고 넘어간다
            y.setdefault('상세', {})
            y['상세오류'] = str(e)
        return y

    # 받은 줄은 바로 .part.jsonl 에 쌓는다 — 3시간 넘는 수집이 중간에 죽어도 다시 돌리면 이어 받는다(오류 난 줄은 다시 부른다)
    부분 = os.path.join(ROOT, 'data', 'raw', f'bojo_paths_{해}' + (f'_{부처}' if 부처 else '') + '.part.jsonl')
    받음 = {}
    if os.path.exists(부분):
        for 줄 in open(부분, encoding='utf-8'):
            try:
                z = json.loads(줄)
            except ValueError:   # 끊길 때 반쯤 쓴 마지막 줄
                continue
            if not z.get('상세오류'):
                받음[z['ddtlbzId']] = z
    남은 = [y for y in 보조 if y['ddtlbzId'] not in 받음]
    print(f'이미 받음 {len(보조) - len(남은):,} · 남은 {len(남은):,}', flush=True)
    with ThreadPoolExecutor(6) as ex, open(부분, 'a', encoding='utf-8') as f:
        for i, y in enumerate(ex.map(보조상세, 남은), 1):
            f.write(json.dumps(y, ensure_ascii=False) + '\n')
            받음[y['ddtlbzId']] = y
            if i % 5000 == 0:
                f.flush()
                print(f'  {i:,}/{len(남은):,} {time.strftime("%H:%M")}', flush=True)
    보조 = [받음[y['ddtlbzId']] for y in 보조]
    p = os.path.join(ROOT, 'data', 'national_grants', f'{해}.json.gz')
    공시 = {x.get('ddtlbzId') for x in json.load(gzip.open(p))['줄']} if os.path.exists(p) else set()
    # 공시 상세의 주소(시·군·구까지) — 정부가 단체에 바로 준 줄은 경로에 지자체가 없어 이것으로 지역을 붙인다
    p = os.path.join(ROOT, 'data', 'national_grants', f'상세_{해}.json.gz')
    주소 = {k.split('|')[2]: v.get('주소') for k, v in json.load(gzip.open(p)).items() if isinstance(v, dict) and v.get('주소')} if os.path.exists(p) else {}
    for y in 보조:
        y['공시있음'] = y['ddtlbzId'] in 공시
        if y['ddtlbzId'] in 주소:
            y['공시주소'] = 주소[y['ddtlbzId']]
    보조 += 개인보충(해, sorted({x['jrsdNm'] for x in 내역}), 보조)
    os.makedirs(os.path.join(ROOT, 'data', 'raw'), exist_ok=True)
    out = os.path.join(ROOT, 'data', 'raw', f'bojo_paths_{해}' + (f'_{부처}' if 부처 else '') + '.json.gz')
    with gzip.open(out, 'wt', encoding='utf-8') as f:
        json.dump({'만든날': date.today().isoformat(), '해': 해, '부처': 부처, '내역사업': 내역, '보조사업': 보조}, f, ensure_ascii=False)
    os.remove(부분)
    print(f'끝 — {out} · 상세 오류 {sum(1 for y in 보조 if y.get("상세오류")):,} · 경로 있음 {sum(1 for y in 보조 if y["상세"].get("dlvplNmPath")):,} · 보조금정보 있음 {sum(1 for y in 보조 if y.get("보조금정보")):,} · 공시 있음 {sum(1 for y in 보조 if y.get("공시있음")):,}', flush=True)


if __name__ == '__main__':
    main()
