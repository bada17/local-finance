# bojo 사업경로 × 지방재정365 세입결산 국고보조금(51000) — 243곳마다 맞춰 본다
# (2026-11-13 사용자 「지자체별로 결산과 맞춰서 데이터를 정하는 거」)
#
#   python scripts/bojo_local_table.py 2024        → 요약 출력 + data/bojo_local_2024.json.gz (금액 천원)
#
# 견줌(결산 = 세입결산 FIACRV 51000 「국고보조금등」 총계)
#   시도   : 사업경로에서 정부(또는 단체)에게 바로 받은 국비 = 교부 gsDtamt         2024: 83.2조 / 84.6조(98%), 17곳 다 ±10%
#   시군구 : 사업경로 govsuby(이 곳이 직접 하는 사업비 국비 — 아래 단체에 준 몫 포함, 일반구 합침), govsuby 0 이면 교부
#            2024: 67.4조 / 69.1조(98%)
#            govsuby 를 쓰는 까닭: 시도 → 시군구 교부(gsDtamt)는 일부만 적힘(결산의 23%).
#            govsuby 0 이면 교부(11-13): 여러 해 사업 줄(여수 어촌뉴딜300 78억 = 가계부 79억) → ±5% 163 → 174곳, 넘치는 곳 안 늘어남
#            결산 「순계」(정부에서 바로 온 몫, 2024 시군구 3.7조)는 못 가름 — 경로엔 거의 다 「부처 > 시도 > 시군구」.
# 채움(추정 — 꼬리표 「가계부로 채움」, 원문 몫과 따로 칸):
#   사업경로에 빠진 시군구가 있다. 대전 영유아보육료: 대전시 교부 919억, 경로엔 4개 구 605억, 유성구 없음
#   → 유성구 가계부 「영유아보육료(국비)」 314.0억 = 남은 돈.
#   시도 교부 − 시도 govsuby − 아래 시군구 govsuby 가 남은 사업마다, 경로에 없는 같은 시도 시군구의 가계부(QWGJK 국비 bdg_ntep)에서
#   내역사업 이름과 앞 6자가 맞는 사업을 찾아 남은 돈을 장부 비율로 나눈다. 나누는 합 = min(남은 돈, 장부 합). 약.
#   2024: 시도에 남은 3.40조 중 0.54조 채움 → 시군구 ±5% 안 174 → 188곳, ±10% 안 216 → 222곳.
#   ±10% 밖 4곳(강원 고성 83%·화천 87%, 경북 영덕 86%, 전북 진안 88%) — 고성·영덕·진안은 재해 복구 사업 국비가 가계부보다 적게 잡힘,
#   화천은 여러 해 사업(화천대교·동서녹색평화도로) 2024 줄이 govsuby·교부 0, 집행만 있음 → 다른 해 사업경로로 볼 것.
# 참고_국비0집행(더하지 않음): 시군구 줄 중 govsuby·교부 0 인데 2024 집행이 있는 몫. 여러 해 사업은 국비가 앞선 해(2022·2023) 줄에 적히고
#   2024 줄엔 쓴 돈만 남는다(화천대교 2022 국비 50억·2023 59억 → 2024 국비 0·집행 99.8억). 4곳은 이 몫 ≈ 설명 안 된 차이
#   (고성 244/192억·영덕 225/236·화천 161/158·진안 134/147) — 하지만 전부 더하면 105% 넘는 곳이 3 → 16곳(앞선 해에 받아 둔 돈도 섞임).
#   그 국비가 2024 결산에 들어왔나(현금 시점)는 사업경로로 확인 안 됨(2023 줄을 fsyr=2024 로 불러도 0). 계획 ≠ 실제는 까닭 아님:
#   정부→시도 실제 교부와 시도·시군구 계획 합이 생계급여 100%·기초연금 101%·전체 97%(시군구 줄 교부가 적어 보이는 건 회차 일부만 적혀서).
# 사업경로 이름 → 지방재정365 코드: 시도 이름 표(bojo_ministry_table.시도정식) · 「전남광주통합특별시」 구 = 광주, 시군 = 전남
#   · 인천 서해구·검단구 = 서구, 영종구 = 중구(지금 이름으로 옴). 시도 단계는 옛 이름(광주광역시·전라남도) 그대로 온다.
# ⚠️ 받은 곳(단체) 이름은 담지 않는다. 곳·사업 이름·금액만.

import gzip, json, os, re, sys
from collections import defaultdict
from bojo_ministry_table import ROOT, RAW, 수, 지자체, 시도정식

새이름 = {('인천', '서해구'): '서구', ('인천', '검단구'): '서구', ('인천', '영종구'): '중구'}
곳 = json.load(open(os.path.join(ROOT, 'site', 'data', 'loc', 'index.json'), encoding='utf-8'))['곳']
코드 = {x['이름']: x['cd'] for x in 곳}
정보 = {x['cd']: x for x in 곳}
이름꼴 = lambda t: re.sub(r'\(.*?\)|\d{4}년?|[^가-힣A-Za-z0-9]', '', t or '')


def laf(nm):
    """사업경로 한 칸 → 지방재정365 코드(지자체 아니면 None)"""
    if not 지자체.match(nm or ''):
        return None
    w = nm.split()
    s = 시도정식[w[0].removesuffix('청')]
    if s == '전남광주':
        if len(w) == 1:
            return None
        s = '광주' if w[1].removesuffix('청').endswith('구') else '전남'
    if len(w) == 1:
        return 코드.get(s + '본청')
    b = w[1].removesuffix('청') if w[1].endswith(('시청', '군청', '구청')) else w[1]
    return 코드.get(s + 새이름.get((s, b), b))


def 만들기(해):
    d = json.load(gzip.open(os.path.join(RAW, f'bojo_paths_{해}.json.gz')))
    내 = {x['dtlbzId']: x for x in d['내역사업']}
    노드 = defaultdict(lambda: {'교': 0.0, 'gv': 0.0})   # (내역사업, 경로) 로 묶음
    국비0집행 = defaultdict(float)                         # 참고 칸(머리말) — 줄 단위로 센다(묶으면 국비 있는 다른 줄에 섞여 빠짐)
    for y in d['보조사업']:
        if y.get('목록에만'):
            continue
        s = y['상세']
        p = tuple(q.strip() for q in (s.get('dlvplNmPath') or '').split('>') if q.strip())
        n = 노드[(s.get('dtlbzId'), p)]
        교, gv = sum(수(r.get('gsDtamt')) for r in y.get('보조금정보') or []), 수(s.get('govsuby'))
        n['교'] += 교
        n['gv'] += gv
        c = laf(p[-1]) if len(p) >= 2 else None
        if c and not 교 and not gv and 정보[c]['갈래'] == '기초' and laf(p[-2]):
            국비0집행[c] += sum(수(r.get('gsEamt')) for r in y.get('보조금정보') or [])

    받음 = defaultdict(lambda: defaultdict(float))                 # 곳 → 내역사업 → 원문 몫
    광 = defaultdict(lambda: {'교': 0.0, 'gv': 0.0, '아래': 0.0, '있음': set()})   # (내역사업, 시도)
    for (dz, p), n in 노드.items():
        c = laf(p[-1]) if p else None
        if not c:
            continue
        위 = laf(p[-2]) if len(p) >= 2 else None
        if 정보[c]['갈래'] == '광역':
            if 위 is None:
                받음[c][dz] += n['교']
                광[(dz, c)]['교'] += n['교']
                광[(dz, c)]['gv'] += n['gv']
        else:
            if 위 is None:                       # 정부·단체에서 바로(드묾)
                받음[c][dz] += n['교']
            else:                                # 시도 거침, 또는 일반구(위 = 같은 시)
                몫 = n['gv'] or n['교']          # 여러 해 사업은 govsuby 0·교부만 있는 줄이 있다(여수 어촌뉴딜300 78억·울릉 통구미항 39억)
                받음[c][dz] += 몫
                if 정보[위]['갈래'] == '광역':
                    광[(dz, 위)]['아래'] += 몫
                    광[(dz, 위)]['있음'].add(c)

    # 채움 — 가계부
    p = os.path.join(RAW, f'QWGJK__exe_ymd-{해}1231_fyr-{해}.json')
    rows = json.load(open(p, encoding='utf-8'))
    가 = defaultdict(lambda: defaultdict(float))
    for y in rows if isinstance(rows, list) else rows['rows']:
        if (y.get('bdg_ntep') or 0) > 0:
            가[y['laf_cd']][이름꼴(y['dbiz_nm'])] += y['bdg_ntep'] / 1e3
    기초들 = defaultdict(list)
    for x in 곳:
        if x['갈래'] == '기초':
            기초들[x['시도']].append(x['cd'])
    채움 = defaultdict(lambda: defaultdict(float))
    남은합 = 0.0
    for (dz, c), g in 광.items():
        남 = g['교'] - g['gv'] - g['아래']
        if 남 <= 0:
            continue
        남은합 += 남
        # 열쇠는 내역사업 이름 하나만 — 다른 곳 보조사업 이름까지 쓰면 흔한 낱말이 엉뚱하게 맞음(내륙 순창에 어촌뉴딜 10억, 11-13)
        열쇠 = [k for k in {이름꼴(내.get(dz, {}).get('dtlbzNm'))} if len(k) >= 4]
        후보 = [(b, sum(v for k, v in 가[b].items() if any(k[:6] in q or q[:6] in k for q in 열쇠)))
              for b in 기초들[정보[c]['시도']] if b not in g['있음']]
        후보 = [(b, v) for b, v in 후보 if v > 0]
        장 = sum(v for _, v in 후보)
        for b, v in 후보:
            채움[b][dz] += min(남, 장) * v / 장

    세 = json.load(gzip.open(os.path.join(ROOT, 'data', 'revenue', 'FIACRV.json.gz'), 'rt', encoding='utf-8'))
    결 = {x['laf_cd']: (x['tott_sum_amt'] / 1e3, x['prsm_amt'] / 1e3) for x in 세 if str(x['_해']) == str(해) and x['armk_cd'] == '51000'}
    p = os.path.join(RAW, f'FIACRV__fyr-{해}.json')   # data/revenue 에 아직 없는 해(2025 — 11-13 PC 에서 fetch_lofin.py FIACRV fyr=2025)
    if not 결 and os.path.exists(p):
        r = json.load(open(p, encoding='utf-8'))
        결 = {x['laf_cd']: (x['tott_sum_amt'] / 1e3, x['prsm_amt'] / 1e3) for x in (r if isinstance(r, list) else r['rows']) if x['armk_cd'] == '51000'}
    # ⚠️ 2025 세입과목이 바뀜(「지난연도 수입」 신설·「지방교부세 등」) — 51000 이 2024 보다 30~45% 큼(순창 1,159 → 1,487억, 세입 총계는 그대로).
    #    보전수입등이 그만큼 줄어 이월 국비가 국고보조금등으로 옮겨 온 것으로 보이나 원문(행안부 세입과목) 확인 전 — 2025 는 2024 와 바로 견주지 말 것.
    결과 = []
    for x in 곳:
        c = x['cd']
        사업 = [{'내역사업ID': dz, '내역사업': 내.get(dz, {}).get('dtlbzNm', '').strip(), '부처': 내.get(dz, {}).get('jrsdNm'),
               '원문': round(받음[c].get(dz, 0)), '채움': round(채움[c].get(dz, 0)),
               **({'시군구로': round(광[(dz, c)]['아래'])} if x['갈래'] == '광역' else {})}
              for dz in set(받음[c]) | set(채움[c])]
        결과.append({'cd': c, '이름': x['이름'], '갈래': x['갈래'], '결산총계': round(결.get(c, (0, 0))[0]), '결산순계': round(결.get(c, (0, 0))[1]),
                   '원문': round(sum(받음[c].values())), '채움': round(sum(채움[c].values())), '참고_국비0집행': round(국비0집행[c]),
                   '사업': sorted(사업, key=lambda r: -(r['원문'] + r['채움']))})
    out = os.path.join(ROOT, 'data', f'bojo_local_{해}.json.gz')
    with gzip.open(out, 'wt', encoding='utf-8') as f:
        json.dump({'해': int(해), '단위': '천원', '설명': '사업경로(e나라도움 bojo) × 세입결산 51000. 원문 = 시도는 받은 교부, 시군구는 govsuby. '
                   '채움 = 시도에 남은 돈을 경로에 없는 시군구 가계부 같은 이름 사업으로 나눈 추정(약).', '곳': 결과}, f, ensure_ascii=False)
    return 결과, 남은합


def 요약(결과, 남은합):
    조 = lambda v: f'{v / 1e9:,.2f}조'
    for 갈 in ('광역', '기초'):
        r = [x for x in 결과 if x['갈래'] == 갈]
        총, 원, 채 = (sum(x[k] for x in r) for k in ('결산총계', '원문', '채움'))
        print(f"\n## {'시도' if 갈 == '광역' else '시군구'} {len(r)}곳 — 결산 {조(총)} · 원문 {조(원)}({원 / 총:.0%}) · +채움 {조(채)} = {(원 + 채) / 총:.0%}")
        for k, f in (('원문', lambda x: x['원문']), ('원문+채움', lambda x: x['원문'] + x['채움'])):
            v = sorted(f(x) / x['결산총계'] for x in r)
            print(f"  {k}: 가운데 {v[len(v) // 2]:.0%} · ±5% 안 {sum(.95 <= a <= 1.05 for a in v)}곳 · ±10% 안 {sum(.9 <= a <= 1.1 for a in v)}곳 · {v[0]:.0%}~{v[-1]:.0%}")
        밖 = sorted((x for x in r if not .9 <= (x['원문'] + x['채움']) / x['결산총계'] <= 1.1), key=lambda x: (x['원문'] + x['채움']) / x['결산총계'])
        if 밖:
            print('  ±10% 밖: ' + ', '.join(f"{x['이름']} {(x['원문'] + x['채움']) / x['결산총계']:.0%}" for x in 밖))
    print(f'\n(시도에 남은 돈 {조(남은합)} 중 가계부로 시군구에 채움 {조(sum(x["채움"] for x in 결과))}. '
          f'참고: 국비 0 줄의 집행 {조(sum(x.get("참고_국비0집행", 0) for x in 결과))}(더하지 않음). 금액은 data/bojo_local_<해>.json.gz)')


if __name__ == '__main__':
    assert laf('경기도') == 코드['경기본청'] and laf('경상남도 창원시청') == 코드['경남창원시']
    assert laf('전남광주통합특별시 광산구') == 코드['광주광산구'] and laf('전남광주통합특별시 순천시') == 코드['전남순천시']
    assert laf('인천광역시 서해구') == 코드['인천서구'] and laf('경기도 수원시 장안구') == 코드['경기수원시']
    assert laf('당찬태권도') is None and laf('강원도 수산업협동조합') is None
    요약(*만들기(sys.argv[1]))
