# e나라도움(bojo.go.kr) 「공모사업 목록」·공모정보 수집기 — 공모 → 선정된 곳 → (보조사업 ID 로) 사업경로·돈 → 계약
# (2026-11-12 사용자 「공모사업은 이전부터 하는게 나오니까 19년자료부터 별도로 수집하는 봇을 만들어」)
#
#   python scripts/fetch_bojo_contests.py              2019 ~ 올해
#   python scripts/fetch_bojo_contests.py 2024         그 해만
#   python scripts/fetch_bojo_contests.py --시간 290   290분까지만 받고 멈춘다 — 다음에 부르면 이어 받는다(봇이 이렇게 돈다)
#
# 창구 — 사용자가 준 공모정보 팝업 링크(/ia/getIA005100Popup.do)에서 찾은 호출. 열쇠·CSRF 없음, bojo.do 쿠키만(2026-11-12):
#   목록  POST /da/retrieveTaskReqstList.do     curPage·perPage(100 됨)·searchBsnsYear·searchFilterYn=N → ntbdList(totCnt)
#         국고(bsnsSe 1, e나라도움)와 지방보조(bsnsSe 2, 보탬e) 공모가 섞여 온다. 2024 = 4,466(국고 4,163·보탬e 303)
#   상세  POST /da/retrieveTaskReqstPopAjax.do  bsnsyear·nttId (보탬e 는 + wdrLcgvCode·labSfrndCode·manageBsnsId)
#         → taskReqstVo 공모정보(ddtlbzId = 보조사업 ID → fetch_bojo_paths.py 사업경로와 이어짐) · slctnResultList 선정결과
#           · pssrpRealm 공모분야 · pssrpDetlList · attachList 첨부
# ⚠️ 담당자·작성자 이름·아이디·전화·메일, 선정결과 대표자 이름은 담지 않는다. 선정된 곳 주소는 시·군·구까지만(개인이면 집 주소다).
#    선정된 곳 이름이 있어 저장소에 안 올리고 R2(공모/)에 둔다 — bojo-contests.yml.
# 다시 받기(사용자 원칙: 안 끝난 것은 늘 다시 받는다):
#   목록은 돌 때마다 다 받는다(한 해 45번 남짓). 상세는 처음 보는 공모 + 7일 지난 것 중 「선정결과가 아직 없고 접수 마감 2년 안」 또는 올해·작년 공모.
#   ponytail: 마감 2년 넘어 선정결과가 붙는 공모는 놓친다 — 그런 게 보이면 기간을 늘릴 것.
# 결과: data/bojo_contests/<해>.json.gz {만든날, 해, 목록: [...], 상세: {nttId: {...공모정보, 선정결과, 받은날}}}

import gzip, http.cookiejar, json, os, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'bojo_contests')
B = 'https://www.bojo.go.kr'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
뺄칸 = {'chargerNm', 'chargerTelno', 'chargerEmail', 'chargerId', 'wrterCn', 'rprsntvNm', 'userNm', 'telno', 'email', 'emailSn', 'mailnYn', 'instYn'}
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


깨끗 = lambda d: {k: v for k, v in (d or {}).items() if k not in 뺄칸 and v not in (None, '')}
시군구 = lambda s: ' '.join(str(s or '').split()[:2])


def 목록(해):
    줄 = []
    for 쪽 in range(1, 10_000):
        L = 부르기('/da/retrieveTaskReqstList.do', curPage=쪽, perPage=100, searchBsnsYear=해, searchFilterYn='N').get('ntbdList') or []
        줄 += [깨끗(x) for x in L]
        if not L or 쪽 * 100 >= int(L[0]['totCnt']):
            return 줄


def 상세(x):
    인자 = {'bsnsyear': x.get('bsnsyear', ''), 'nttId': x['nttId']}
    if x.get('manageBsnsId'):   # 보탬e 공모
        인자.update(wdrLcgvCode=x.get('wdrLcgvCode', ''), labSfrndCode=x.get('labSfrndCode', ''), manageBsnsId=x['manageBsnsId'])
    try:
        r = 부르기('/da/retrieveTaskReqstPopAjax.do', **인자)
    except RuntimeError as e:   # 한 줄이 늘 500 인 일이 있다(bojo 사업경로 수집 11-12) — 적고 넘어간다, 다음에 다시 부른다
        return {'오류': str(e), '받은날': date.today().isoformat()}
    선정 = [깨끗(s) for s in r.get('slctnResultList') or []]
    for s in 선정:
        if s.get('dlvplAddr'):
            s['dlvplAddr'] = 시군구(s['dlvplAddr'])
    return {'공모정보': 깨끗(r.get('taskReqstVo')), '선정결과': 선정, '공모분야': r.get('pssrpRealm'),
            '공모상세': [깨끗(p) for p in r.get('pssrpDetlList') or []],
            '첨부': [{k: a.get(k) for k in ('docId', 'fileId', 'name')} for a in r.get('attachList') or []],
            '받은날': date.today().isoformat()}


def 다시받나(해, x, d):
    if not d or d.get('오류'):
        return True
    if date.fromisoformat(d['받은날']) > date.today() - timedelta(days=7):
        return False
    if int(해) >= date.today().year - 1:
        return True
    마감 = (x.get('rceptEndDt') or '')[:8]
    return not d.get('선정결과') and len(마감) == 8 and datetime.strptime(마감, '%Y%m%d').date() > date.today() - timedelta(days=730)


def 저장(해, 줄, 상):
    with gzip.open(os.path.join(OUT, f'{해}.json.gz'), 'wt', encoding='utf-8') as f:
        json.dump({'만든날': date.today().isoformat(), '해': 해, '목록': 줄, '상세': 상}, f, ensure_ascii=False)


def main():
    a = sys.argv[1:]
    한도 = time.time() + 60 * int(a[a.index('--시간') + 1]) if '--시간' in a else float('inf')
    해들 = [x for x in a if x.isdigit() and len(x) == 4] or [str(y) for y in range(2019, date.today().year + 1)]
    os.makedirs(OUT, exist_ok=True)
    op.open(B + '/bojo.do', timeout=60).read()   # 쿠키
    for 해 in 해들:
        p = os.path.join(OUT, f'{해}.json.gz')
        상 = json.load(gzip.open(p, 'rt', encoding='utf-8'))['상세'] if os.path.exists(p) else {}
        줄 = 목록(해)
        할 = [x for x in 줄 if 다시받나(해, x, 상.get(x['nttId']))]
        print(f'{해}: 목록 {len(줄):,} · 상세 받을 것 {len(할):,}', flush=True)
        with ThreadPoolExecutor(4) as ex:
            for i in range(0, len(할), 500):   # 500개마다 저장 — 시간 한도·끊김에도 받은 건 남는다
                if time.time() > 한도:
                    저장(해, 줄, 상)
                    print('시간이 다 돼 멈춘다', flush=True)
                    return
                묶음 = 할[i:i + 500]
                for x, d in zip(묶음, ex.map(상세, 묶음)):
                    상[x['nttId']] = d
                저장(해, 줄, 상)
        print(f'  끝 · 상세 {len(상):,} · 선정결과 있음 {sum(1 for d in 상.values() if d.get("선정결과")):,} · 오류 {sum(1 for d in 상.values() if d.get("오류")):,}', flush=True)


if __name__ == '__main__':
    main()
