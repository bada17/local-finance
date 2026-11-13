# bojo 사업경로(fetch_bojo_paths.py 결과)로 부처별 국고보조 표 — 두 가지로 맞춰 본다(규칙: 수첩 「돈 나무」·11-12)
#
#   python scripts/bojo_ministry_table.py 2024                 data/raw/bojo_paths_2024.json.gz
#   python scripts/bojo_ministry_table.py 2024 <파일>          다른 결과 파일(예: 부처 하나)
#
# ① 총액   = 1단계(부처 > 받은 곳) 교부받은 국비 gsDtamt 합  ÷  열린재정 OPFI939 국회확정 세목 넷(자치단체·민간 경상·자본보조)
# ② 나눠 보기 = 곳마다 「제 손에 남은 국비」 합  ÷  data.go.kr 내역사업현황 예산현액   (11-13 전 부처로 고침)
#    같은 내역사업·같은 경로를 한 곳으로 묶고, 남은 국비 =
#      단체   : 교부받은 국비 gsDtamt − 바로 아래(단체·지자체)가 교부받은 국비
#      지자체 : 직접 하는 사업비 국비 govsuby − 바로 아래 단체가 교부받은 국비
#               (govsuby 는 아래 지자체로 넘긴 몫은 이미 빠져 있고, 아래 단체에 준 몫은 들어 있다 — 아이돌봄 시군구)
#               아래가 없는데 govsuby 0·교부 있으면 교부(7호선 청라 연장 등 시가 받아 바로 쓰는 철도)
#      모자라면 0(아래가 더 큰 몫은 「아래 넘침」 합만 찍음).
#    11-12 해수부 시험의 「단체 교부 + 지자체 govsuby = 99.99%」는 위·아래 단체를 두 번 세고 다른 데서 덜 센 우연 —
#    전 부처에선 중기부 124%·고용부 149%·여가부 129% 로 깨짐. 고친 규칙: 사업 4,258개 중 3,823개가 1단계 교부와 ±5% 안.
#    「목록에만」(개인 등, 경로 없음) 줄은 따로 칸.
# 내역사업현황(T_OPD_DTLBZ_CSTS)은 부처마다 한 번 받아 data/raw/dtlbz_csts_<해>.json.gz 에 둔다(있으면 다시 안 받음).

import gzip, json, os, re, sys, time, urllib.parse, urllib.request
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')
세목 = {'자치단체경상보조', '자치단체자본보조', '민간경상보조', '민간자본보조'}
# 「경기도」「서울특별시 마포구」「경기도 수원시 장안구」 꼴만 지자체 — 「강원도 ○○협회」는 단체
지자체 = re.compile(r'^\S+(특별시|광역시|특별자치시|특별자치도|도)청?( \S+(시|군|구)청?){0,2}$')   # 「경상남도 창원시청」(2024 1,363줄)
열린재정이름 = {'국가유산청': '문화재청'}   # 2024-05 이름 바뀜, 열린재정 2024 는 옛 이름
수 = lambda v: float(str(v or 0).replace(',', '') or 0)


def 예산현액받기(해, 부처들):
    p = os.path.join(RAW, f'dtlbz_csts_{해}.json.gz')
    있음 = json.load(gzip.open(p)) if os.path.exists(p) else {}
    from keys import 키읽기
    키 = 키읽기('DATA_GO_KR_KEY')
    for 부처 in sorted(set(부처들) - set(있음)):
        줄 = []
        for 쪽 in range(1, 1000):
            q = urllib.parse.urlencode({'serviceKey': 키, 'pageNo': 쪽, 'numOfRows': 1000, 'resultType': 'json', 'bsnsyear': 해, 'jrsd_nm': 부처})
            for t in range(4):
                try:
                    b = json.loads(urllib.request.urlopen(urllib.request.Request(
                        f'https://apis.data.go.kr/1051000/MoefOpenAPI/T_OPD_DTLBZ_CSTS?{q}', headers={'User-Agent': 'Mozilla/5.0'}), timeout=120).read())['response']['body']
                    break
                except Exception as e:
                    if t == 3:
                        raise RuntimeError(f'내역사업현황 {부처} {쪽}쪽 네 번 실패: {e!r}')
                    time.sleep(5 * (t + 1))
            it = (b.get('items') or {}).get('item') or []
            줄 += it if isinstance(it, list) else [it]
            if 쪽 * 1000 >= int(b.get('totalCount') or 0):
                break
        있음[부처] = 줄
        with gzip.open(p, 'wt', encoding='utf-8') as f:   # 부처마다 저장 — 중간에 끊겨도 받은 건 남게
            json.dump(있음, f, ensure_ascii=False)
    return 있음


def 표(해, 파일):
    d = json.load(gzip.open(파일))
    교부 = lambda y: sum(수(r.get('gsDtamt')) for r in y.get('보조금정보') or [])
    t = defaultdict(lambda: defaultdict(float))
    for x in d['내역사업']:
        t[x['jrsdNm']]['내역'] += 1
    곳 = defaultdict(lambda: {'교': 0.0, 'gv': 0.0})   # (내역사업, 경로) → 묶은 금액
    for y in d['보조사업']:
        s = y['상세']
        부처 = s.get('jrsdNm') or y.get('jrsdNm')
        a = t[부처]
        if y.get('목록에만'):
            a['목록에만'] += 수(s.get('govsuby'))
            continue
        a['보조'] += 1
        경로 = tuple(p.strip() for p in (s.get('dlvplNmPath') or '').split('>') if p.strip())
        if len(경로) == 2:
            a['1단계'] += 교부(y)
        n = 곳[(s.get('dtlbzId'), 경로)]
        n['부처'] = 부처
        n['교'] += 교부(y)
        n['gv'] += 수(s.get('govsuby'))
    아래단체, 아래지자체, 아래있음 = defaultdict(float), defaultdict(float), set()
    for (dz, p), n in 곳.items():
        if len(p) > 2:
            아래있음.add((dz, p[:-1]))
            (아래지자체 if 지자체.match(p[-1]) else 아래단체)[(dz, p[:-1])] += n['교']
    for (dz, p), n in 곳.items():
        a, k = t[n['부처']], (dz, p)
        if p and 지자체.match(p[-1]):
            몫 = n['교'] if k not in 아래있음 and n['gv'] == 0 else n['gv'] - 아래단체[k]
            a['지자체'] += max(0, 몫)
        else:
            몫 = n['교'] - 아래단체[k] - 아래지자체[k]
            a['단체'] += max(0, 몫)
        a['아래넘침'] += max(0, -몫)

    열린 = defaultdict(float)   # 천원
    for x in json.load(gzip.open(os.path.join(ROOT, 'data', 'openfiscal', 'OPFI939.json.gz')))['줄']:
        if x['FSCL_YY'] == str(해) and x['EITM_NM'] in 세목:
            열린[x['OFFC_NM']] += x['Y_YY_DFN_MEDI_KCUR_AMT'] or 0
    for 새, 옛 in 열린재정이름.items():
        if 새 not in 열린 and 옛 in 열린:
            열린[새] = 열린.pop(옛)
    현액 = {k: sum(int(r['BUDGET_CRNTAM']) for r in v if r.get('EXTI_NM') in 세목) / 1e3   # 원 → 천원
            for k, v in 예산현액받기(해, t).items()}

    억 = lambda v: f'{v / 1e5:,.0f}'
    비 = lambda a, b: f'{a / b:.0%}' if b else '—'
    줄 = lambda k, a: (f"| {k} | {a['내역']:,.0f} | {a['보조']:,.0f} | {억(a['1단계'])} | {억(a['열린'])} | {비(a['1단계'], a['열린'])} | "
                      f"{억(a['지자체'])} | {억(a['단체'])} | {억(a['나눠'])} | {억(a['현액'])} | {비(a['나눠'], a['현액'])} | {억(a['목록에만'])} |")
    print(f'| 부처 | 내역 | 보조 | ① 1단계 교부 | 열린재정 예산 | ①÷ | 지자체 남은 | 단체 남은 | ② 나눠 보기 | 예산현액 | ②÷ | 목록에만 |')
    print('|' + '---|' * 12)
    합, 보육 = defaultdict(float), defaultdict(float)
    for k, a in sorted(t.items(), key=lambda kv: -(kv[1]['지자체'] + kv[1]['단체'])):
        a['열린'], a['현액'], a['나눠'] = 열린.get(k, 0), 현액.get(k, 0), a['지자체'] + a['단체']
        for c, v in a.items():
            합[c] += v
            if k in ('교육부', '보건복지부'):
                보육[c] += v
        print(줄(k, a))
    print(줄('**합**', 합))
    if 보육['내역']:   # 영유아보육료 등은 예산현액이 두 부처로 나뉘었는데 bojo 는 교육부로만 적음(2024 보육 이관)
        print(줄('(교육부+보건복지부)', 보육))
    print(f"(억원. ② 아래가 위보다 큰 몫(0으로 둠) {억(합['아래넘침'])}. 열린재정에 이름이 없는 부처: "
          + (', '.join(k for k in t if k not in 열린) or '없음') + ')')


if __name__ == '__main__':
    assert 지자체.match('경기도') and 지자체.match('전북특별자치도 부안군') and 지자체.match('경기도 수원시 장안구')
    assert 지자체.match('경상남도 창원시청')
    assert not 지자체.match('강원도 수산업협동조합') and not 지자체.match('사단법인한국김산업연합회')
    해 = sys.argv[1]
    표(해, sys.argv[2] if len(sys.argv) > 2 else os.path.join(RAW, f'bojo_paths_{해}.json.gz'))
