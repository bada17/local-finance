# 「해마다 나란히」 자료 — 서로 다른 자료를 「같은 곳 · 같은 해」로 붙여 한 줄에 놓는다.
#
#   python scripts/build_side.py
#
# 2026-10-14 사용자: 「데이터의 엄밀성이 필요해. 괜히 대충 연결했다가 문제가 되면 안돼.」
# 붙이는 법은 둘뿐이다 — ① 자치단체 번호(지방재정365 laf_cd) ② 시도+이름(번호가 다른 자료).
# 붙일 때마다 점검을 같이 담는다 — 원자료 곳 수 · 붙은 곳 · 못 붙은 것과 까닭 · 손으로 고친 것 · 맞춰 본 것.
#   화면(자치단체별 「해마다 나란히」 판 · 시황판)이 칸마다 이 점검을 그대로 보여준다.
# ⛔ 못 붙은 것을 다른 해·다른 곳으로 채우지 않는다. 빈칸은 빈칸이다(0 이 아니다).
#    0 은 「그 해 전부를 담았다」를 확인한 갈래(투자심사 · 국외출장 게시판)의 다 지난 해에서만 쓴다.
# ⛔ 이건 「옆에 놓기」다. 계약 ○억이 어느 사업 돈인지는 모른다 — 다른 자료끼리 나누지(비율) 않는다.
#    비율은 같은 자료 안에서 원자료가 준 것(편성 비율)이나 우리가 센 것(수의계약 몫)뿐이다.
# ⛔ 한 칸에 두 원자료가 겹쳐 들어오면(번호를 고쳐 붙였더니 이미 값이 있는 등) 그 지표는 시황판에 안 올린다.
#
# 결과: site/data/side.json
#   {만든날, 해들, 지표:[{id, 이름, 묶음, 단위, 해뜻, 출처, 붙인법, 범위, 주의, 반쪽, 시황판, 온전한해, 금액짝, 나쁨, 점검}],
#    곳:{cd:{id:{해:값}}}}
#   build_board.py 가 「시황판: true」 칸을 온전한해 하나로 시황판에 붙인다. 자치단체별 화면은 곳 하나를 해마다 편다.

import collections
import datetime
import glob
import gzip
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_review_page import 고침 as 심사고침, 회차  # noqa: E402 — 투자심사 화면과 같은 이름 고침·회차

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'site', 'data', 'side.json')

# 번호가 바뀐 같은 곳 — 손으로 고친 것은 점검에 그대로 실린다
옛번호 = {'4771000': ('2772000', '군위군 — 2023-07-01 경북에서 대구로 옮기며 번호가 바뀌었다(같은 곳)')}

오늘 = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)).date()
해들 = [str(y) for y in range(2022, 오늘.year + 1)]


def 읽기(*p):
    return json.load(open(os.path.join(ROOT, *p), encoding='utf-8'))


def 읽기gz(*p):
    return json.load(gzip.open(os.path.join(ROOT, *p), 'rt', encoding='utf-8'))


목록 = 읽기('site', 'data', 'loc', 'index.json')['곳']
곳번호 = {x['cd'] for x in 목록}
이름키 = {f"{x['시도']}({x['이름'][len(x['시도']):]})": x['cd'] for x in 목록}   # 「전남(여수시)」·「서울(본청)」
assert len(이름키) == len(목록), '시도+이름이 겹치는 곳이 있다 — 이름으로 붙이면 안 된다'

값 = collections.defaultdict(lambda: collections.defaultdict(dict))
어디서 = {}          # (cd, id, 해) → 원자료 곳 표기 — 겹침을 잡는다
겹침 = collections.defaultdict(list)
지표 = []


def 번호(cd):
    if cd in 곳번호:
        return cd
    return 옛번호[cd][0] if cd in 옛번호 else None


def 넣기(id, cd, 해, v, 원):
    if v is None or 해 not in 해들:
        return
    k = (cd, id, 해)
    if k in 어디서 and 어디서[k] != 원:
        겹침[id].append(f'{cd} {해} — {어디서[k]} 와 {원}')
        return
    어디서[k] = 원
    값[cd][id][해] = v


def 칸(id, 이름, 묶음, 단위, 해뜻, 점검, **더):
    지표.append({'id': id, '이름': 이름, '묶음': 묶음, '단위': 단위, '해뜻': 해뜻, '점검': 점검,
               '시황판': 더.get('시황판', False), '온전한해': 더.get('온전한해'), '금액짝': 더.get('금액짝'),
               '나쁨': 더.get('나쁨', False), '반쪽': 더.get('반쪽', {})})


def 점검틀(출처, 붙인법, 범위, 주의, 원자료곳, 못붙음, 고친것=(), 맞춰본것=()):
    """못붙음: Counter{원자료 표기: 줄 수}"""
    return {'출처': 출처, '붙인법': 붙인법, '범위': 범위, '주의': list(주의),
            '원자료곳': len(원자료곳), '못붙음': [[k, n] for k, n in 못붙음.most_common()],
            '고친것': list(고친것), '맞춰본것': list(맞춰본것)}


def 붙은곳(ids):
    return sum(1 for cd in 값 if any(값[cd].get(i) for i in ids))


# ── 1. 세출 결산 총액 — 지방재정365 AJGCF, 번호로 ──
def 세출():
    s = 읽기('data', 'series.json')
    원, 못, 고친 = set(), collections.Counter(), set()
    for cd, 해별 in s['값'].items():
        for 해, row in 해별.items():
            if 해 not in 해들:
                continue
            원.add(cd)
            c = 번호(cd)
            if c is None:
                못[f"{s['자치단체'].get(cd, {}).get('이름', '')} {cd} ({해})"] += 1
                continue
            if c != cd:
                고친.add(f'{cd} → {c} · {옛번호[cd][1]}')
            넣기('세출', c, 해, row.get('세출'), cd)
    끝 = s['기간'].split('~')[-1]
    점검 = 점검틀('지방재정365 AJGCF 세출결산 총액(tot_pfa_amt)', '자치단체 번호',
              f'결산이 나온 해까지 — 지금 {끝}년', ['그 해에 실제로 쓴 돈 전부(결산). 예산이 아니다'], 원, 못, sorted(고친))
    칸('세출', '세출결산 총액', '살림 규모', '원', '회계연도 결산', 점검)


# ── 2. 계약 — 지방재정365 계약현황을 우리가 센 것(build_contracts_summary.py), 번호로 ──
def 계약():
    cs = 읽기('data', 'contracts_summary.json')
    첫, 끝 = cs['범위']['첫날'], cs['범위']['끝날']
    원, 못 = set(), collections.Counter()
    for cd, 해별 in cs['곳'].items():
        for 해, y in 해별.items():
            if 해 not in 해들:
                continue
            원.add(cd)
            c = 번호(cd)
            if c is None:
                못[f"{cs.get('곳이름', {}).get(cd, '')} {cd} ({해}) — 2026년에 새로 생긴 구역, 243곳 목록에 없다"] += 1
                continue
            for id, k in (('계약총액', '금액'), ('수의금액률', '수의금액률'), ('상위5몫', '상위5몫'), ('다년몫', '다년몫')):
                넣기(id, c, 해, y.get(k), cd)
    반쪽 = {} if 끝[4:] == '1231' else {끝[:4]: f'{int(끝[4:6])}월 {int(끝[6:])}일 계약까지'}
    점검 = 점검틀('지방재정365 계약현황(날마다 받는 원자료 320만여 건)을 우리가 센 것', '자치단체 번호',
              f'{첫[:4]}-{첫[4:6]}-{첫[6:]} ~ {끝[:4]}-{끝[4:6]}-{끝[6:]} 계약',
              ['그 해에 맺은 계약의 총액이다. 그 해에 나간 돈이 아니고, 세출의 일부도 아니다 — 세출과 나누지 말 것',
               '여러 해짜리 계약은 총액 줄과 해마다 줄이 같이 들어온다(「다년 계약 몫」 칸). 그만큼 커 보일 수 있다',
               '원자료 자릿수 오류로 한 건이 1조원을 넘는 줄은 빼고 셌다'], 원, 못)
    칸('계약총액', '계약 총액', '계약', '원', '계약한 날', 점검, 반쪽=반쪽)
    칸('수의금액률', '수의계약 금액 몫', '계약', '%', '계약한 날', 점검, 반쪽=반쪽)
    칸('상위5몫', '상위 5개 업체 몫(금액)', '계약', '%', '계약한 날', 점검, 반쪽=반쪽)
    칸('다년몫', '다년 계약 몫(겹쳐 셌을 수 있는 몫)', '계약', '%', '계약한 날', 점검, 반쪽=반쪽)


# ── 3. 업무추진비 편성 — 지방재정365 NBRILV(기관운영)·YQMZYF(시책추진), 번호로 ──
def 편성():
    for code, 이름 in (('NBRILV', '기관운영'), ('YQMZYF', '시책추진')):
        d = 읽기gz('data', 'items', f'{code}.json.gz')
        원, 못, 고친, 어긋 = set(), collections.Counter(), set(), []
        온전 = collections.Counter()
        for x in d['행']:
            해, cd = str(x['fyr']), x['laf_cd']
            if 해 not in 해들:
                continue
            원.add(cd)
            c = 번호(cd)
            if c is None:
                못[f"{x.get('laf_hg_nm', '')} {cd} ({해})"] += 1
                continue
            if c != cd:
                고친.add(f'{cd} → {c} · {옛번호[cd][1]}')
            온전[해] += 1
            if code == 'NBRILV':
                B, C, D, E, A = (x.get(k) for k in ('smy_cntt_amt', 'smy_cntt_amt2', 'smy_cntt_amt3', 'smy_cntt_amt5', 'smy_cntt_amt4'))
                if None not in (B, C, D, E) and B != C + D + E:
                    어긋.append(f'{x["laf_hg_nm"]} {해} 편성 {B:,} ≠ 단체장+부단체장+기타 {C + D + E:,}')
                넣기('기관편성', c, 해, B, cd)
                넣기('단체장편성', c, 해, C, cd)
                넣기('기관한도비율', c, 해, x.get('smy_cntt_amt_rt'), cd)
            else:
                A, B = x.get('smy_cntt_amt'), x.get('smy_cntt_amt2')
                넣기('시책편성', c, 해, B, cd)
                넣기('시책기준비율', c, 해, x.get('smy_cntt_amt_rt'), cd)
            rt = x.get('smy_cntt_amt_rt')
            if A and B is not None and rt is not None and abs(B / A * 100 - rt) > 0.05:
                어긋.append(f'{x["laf_hg_nm"]} {해} 비율 {rt} ≠ 편성/{"한도" if code == "NBRILV" else "기준액"} {B / A * 100:.2f}')
        온전한해 = max((h for h, n in 온전.items() if n == len(목록)), default=None)
        맞춤 = [f'{"편성 = 단체장 + 부단체장 + 실국장·읍면동장 등 기타, " if code == "NBRILV" else ""}비율 = 편성 ÷ {"총액한도" if code == "NBRILV" else "기준액"} × 100 — '
                + (f'어긋난 줄 {len(어긋)}개' if 어긋 else '모든 줄이 맞는다')] + 어긋[:10]
        점검 = 점검틀(f'지방재정365 {code} {이름} 업무추진비 편성현황', '자치단체 번호', f'2020~{max(온전)}년 예산',
                  ['예산에 잡아 둔 돈(편성)이다. 실제로 쓴 돈이 아니다',
                   '2021년부터 실국장·읍면동장 등 기타 항목이 더해졌다 — 2020년과 견주지 말 것' if code == 'NBRILV'
                   else '기준액은 행정안전부 기준으로 정한 한도다. 넘겼다고 곧 법 위반은 아니다'], 원, 못, sorted(고친), 맞춤)
        if code == 'NBRILV':
            칸('기관편성', '기관운영 업무추진비 편성액', '업무추진비 편성', '원', '회계연도 예산', 점검, 시황판=True, 온전한해=온전한해)
            칸('단체장편성', '그중 단체장 몫', '업무추진비 편성', '원', '회계연도 예산', 점검, 시황판=True, 온전한해=온전한해)
            칸('기관한도비율', '기관운영 총액한도 대비 편성', '업무추진비 편성', '%', '회계연도 예산', 점검,
               시황판=True, 온전한해=온전한해, 금액짝='기관편성')
        else:
            칸('시책편성', '시책추진 업무추진비 편성액', '업무추진비 편성', '원', '회계연도 예산', 점검, 시황판=True, 온전한해=온전한해)
            칸('시책기준비율', '시책추진 기준액 대비 편성', '업무추진비 편성', '%', '회계연도 예산', 점검,
               시황판=True, 온전한해=온전한해, 금액짝='시책편성', 나쁨=True)


# ── 4. 중앙투자심사 — 지방재정365 통합자료실 결과 파일을 우리가 정리한 것(fetch_review.py), 이름으로 ──
def 투자심사():
    r = 읽기('data', 'review.json')
    원, 못, 사업비못 = set(), collections.Counter(), 0
    셈 = collections.defaultdict(lambda: [0, 0, 0])      # (cd, 해) → 건수, 사업비, 재검토·반려
    회차들 = collections.defaultdict(set)
    for x in r['사업']:
        곳 = re.sub(r'\s+', '', x['광역명(시군명)'])
        곳 = 심사고침.get(곳, 곳)
        해 = 회차(x['파일'], x['글'])[:4]
        if 해 not in 해들:
            continue
        회차들[해].add(회차(x['파일'], x['글']))
        원.add(곳)
        cd = 이름키.get(곳)
        if not cd:
            못[f'{곳} — 자치단체가 아니다(경제자유구역청·여러 곳 공동 사업)'] += 1
            continue
        m = re.match(r'\s*([\d,]+)', x['사업비(억원)'])
        s = 셈[(cd, 해)]
        s[0] += 1
        if m:
            s[1] += int(m[1].replace(',', '')) * 100_000_000
        else:
            사업비못 += 1
        s[2] += x['심사결과'] in ('재검토', '반려')
    for (cd, 해), (n, 돈, 나쁨) in 셈.items():
        넣기('심사건수', cd, 해, n, cd)
        넣기('심사사업비', cd, 해, 돈, cd)
        넣기('재검토반려', cd, 해, 나쁨, cd)
    # 0 — 받은 첫해(반쪽)와 올해(아직 안 끝남)를 뺀 해는 통합자료실에 올라온 회차 전부를 받았다
    첫해 = r['부터'][:4]
    다찬해 = [h for h in 해들 if 첫해 < h < str(오늘.year)]
    for cd in 곳번호:
        for 해 in 다찬해:
            for id in ('심사건수', '심사사업비', '재검토반려'):
                값[cd][id].setdefault(해, 0)
    반쪽 = {첫해: f'{int(r["부터"][5:7])}월 뒤 회차만', str(오늘.year): '올해 올라온 회차까지'}
    점검 = 점검틀('지방재정365 통합자료실 > 중앙투자심사결과 — 회차별 결과 파일을 우리가 표로 정리', '시도 + 자치단체 이름(「전남(여수시)」)',
              f'{r["부터"]} 뒤 회차 — 해마다 회차 ' + ' · '.join(f'{h}년 {len(회차들[h])}' for h in sorted(회차들)),
              ['사업비는 여러 해에 걸친 총사업비다. 그 해 예산이 아니다',
               f'{"·".join(다찬해)}년은 올라온 회차를 전부 받았다 — 줄이 없는 곳은 0건이다',
               '「재검토·반려」는 심사결과 칸 글자 그대로 센 것이다(조건부·적정은 넣지 않았다)']
              + ([f'사업비 칸을 못 읽은 줄 {사업비못}개 — 건수에는 들고 사업비에는 안 들었다'] if 사업비못 else []),
              원, 못, [f'{a} → {b}' for a, b in 심사고침.items()])
    온전 = str(오늘.year - 1) if str(오늘.year - 1) in 다찬해 else None
    칸('심사건수', '중앙투자심사에 올린 사업', '중앙투자심사', '건', '심사 회차의 해', 점검, 시황판=True, 온전한해=온전, 반쪽=반쪽)
    칸('심사사업비', '그 사업들의 총사업비', '중앙투자심사', '원', '심사 회차의 해', 점검, 시황판=True, 온전한해=온전, 반쪽=반쪽)
    칸('재검토반려', '재검토·반려 받은 사업', '중앙투자심사', '건', '심사 회차의 해', 점검, 시황판=True, 온전한해=온전, 반쪽=반쪽)


# ── 5. 지방의회 — CLIK 회의록·의안(build_clik.py 가 의회 이름+시도로 곳에 붙인 것) ──
def 의회():
    meta = 읽기('site', 'data', 'clik.json')
    기간 = meta['수집']['회의록']['기간']                      # 「20220701~20261012」
    원, 못 = set(), collections.Counter()
    문서, 고유, 의안문서, 의안고유, 날없음 = (collections.Counter() for _ in range(5))
    for f in sorted(glob.glob(os.path.join(ROOT, 'site', 'data', 'clik', '*.json'))):
        cd = os.path.basename(f)[:-5]
        d = json.load(open(f, encoding='utf-8'))
        원.add(cd)
        c = 번호(cd)
        회의칸, 의안칸 = d['칸']['회의록'], d['칸']['의안']
        회의 = collections.defaultdict(set)
        for row in d['회의록']:
            r = dict(zip(회의칸, row))
            해 = (r.get('날짜') or '')[:4]
            if not 해:
                날없음['회의록'] += 1
                continue
            if 해 in 해들:
                문서[해] += 1
                회의[해].add((r['RASMBLY_ID'], r['MTG_DE'], r['MTGNM'], r['RASMBLY_SESN'], r['MINTS_ODR']))
        의안 = collections.defaultdict(set)
        for row in d['의안']:
            r = dict(zip(의안칸, row))
            해 = (r.get('날짜') or '')[:4]
            if not 해:
                날없음['의안'] += 1
                continue
            if 해 in 해들:
                의안문서[해] += 1
                의안[해].add((r['RASMBLY_ID'], r['RASMBLY_NUMPR'], r['BI_NO'], r['BI_SJ']))
        if c is None:
            n = sum(len(v) for v in 회의.values()) + sum(len(v) for v in 의안.values())
            if n:
                못[f'{cd} {", ".join(x["의회명"] for x in d["의회"])} — 2026년에 새로 생긴 구역, 243곳 목록에 없다'] += n
            continue
        for 해, v in 회의.items():
            고유[해] += len(v)
            넣기('회의수', c, 해, len(v), cd)
        for 해, v in 의안.items():
            의안고유[해] += len(v)
            넣기('의안수', c, 해, len(v), cd)
    for x in meta.get('미연결의회') or []:
        못[f'{x["의회명"]} — {x.get("까닭", "곳을 못 찾음")}'] += 0
    첫, 끝 = 기간.split('~')
    반쪽 = {첫[:4]: f'{int(첫[4:6])}월 {int(첫[6:])}일 뒤', 끝[:4]: f'{int(끝[4:6])}월 {int(끝[6:])}일까지'}
    빈의안 = sum(1 for cd in 곳번호 if not 값[cd].get('의안수'))
    빈회의 = sum(1 for cd in 곳번호 if not 값[cd].get('회의수'))
    겹 =' · '.join(f'{h}년 문서 {문서[h]:,} → 회의 {고유[h]:,}' for h in 해들 if 문서[h])
    겹2 = ' · '.join(f'{h}년 {의안문서[h]:,} → {의안고유[h]:,}' for h in 해들 if 의안문서[h])
    점검 = 점검틀('국회도서관 지방의회 회의록·의안(CLIK)', '의회 이름 + 시도(build_clik.py) — 광역 본청에는 시도의회가 붙는다',
              f'{첫[:4]}-{첫[4:6]}-{첫[6:]} ~ {끝[:4]}-{끝[4:6]}-{끝[6:]}',
              [f'의회마다 CLIK 에 올린 정도가 다르다 — 의안이 한 건도 없는 곳 {빈의안}, 회의록이 없는 곳 {빈회의}. '
               '그래서 이 숫자로 243곳을 줄 세우지 않는다(시황판에 안 올림). 곳 하나의 해마다 흐름으로만 볼 것',
               f'CLIK 에 같은 회의가 문서 번호만 달리 두 번 이상 올라간 경우가 많다 — 날짜·회의 이름·회기·차수가 같으면 한 번으로 셌다({겹})',
               f'의안도 같다 — 의회·대수·의안번호·제목이 같으면 하나로 셌다({겹2})',
               '의회가 CLIK 에 늦게 올리면 그만큼 비어 보인다. 회의가 0번인 해는 빈칸으로 둔다(0 으로 채우지 않는다)',
               '서울시의회 회의록은 CLIK 에 2026-06-24 까지만 있다']
              + ([f'날짜가 없는 문서 회의록 {날없음["회의록"]} · 의안 {날없음["의안"]} — 해를 몰라 뺐다'] if sum(날없음.values()) else []),
              원, 못)
    칸('회의수', '의회가 연 회의(본회의·위원회)', '지방의회', '번', '회의한 날', 점검, 반쪽=반쪽)
    칸('의안수', '의회에 올라온 의안', '지방의회', '건', '의안을 제안한 날', 점검, 반쪽=반쪽)


# ── 6. 의원 국외출장 — 의회 누리집 국외출장 게시판의 글(fetch_boards.js → read_post_files.py), 번호로 ──
def 국외출장():
    t = 읽기('data', 'trip_reports.json')['곳']
    판들 = 읽기('data', 'board_posts_council.json')['곳']
    원, 못 = set(t), collections.Counter()
    for cd, v in t.items():
        c = 번호(cd)
        if c is None:
            못[f'{v.get("이름", "")} {cd}'] += 1
            continue
        for 해, n in v['해별'].items():
            넣기('국외계획', c, 해, n.get('계획', 0), cd)
            넣기('국외결과', c, 해, n.get('결과', 0), cd)
    # 0 — 게시판이 있고, 그 해가 게시판에 남은 글의 범위 안이며 다 지난 해일 때만
    판수 = 0
    for cd, v in 판들.items():
        판 = v.get('국외출장')
        if not (isinstance(판, dict) and 판.get('종류') == '게시판') or 판.get('못읽은날') or 번호(cd) is None:
            continue
        판수 += 1
        날들 = sorted(x['날짜'] for x in 판.get('글') or [] if x.get('날짜'))
        처음 = 해들[0] if (판.get('멈춘까닭') or '').startswith('2022-01-01') else (날들[0][:4] if 날들 else None)
        for 해 in 해들:
            if 처음 and 처음 <= 해 < str(오늘.year):
                for id in ('국외계획', '국외결과'):
                    값[번호(cd)][id].setdefault(해, 0)
    점검 = 점검틀('의회 누리집 국외출장 게시판의 글 제목(우리가 모은 것)', '자치단체 번호(게시판 자리를 찾을 때 243곳 목록으로 셌다)',
              f'게시판을 찾은 의회 {판수}곳 — 나머지는 빈칸(게시판을 못 찾은 것이지 출장이 없던 것이 아니다)',
              ['제목으로 갈랐다 — 「결과·보고서·귀국」이 들면 결과, 「계획·심사·사전·일정」이 들면 계획. 둘 다 없으면 셈에 안 넣었다',
               '게시판에 남아 있는 글 기준이다. 결과 보고를 다른 곳(회의록·보도자료)에 올리는 의회도 있다 — 결과 0이 곧 「안 냈다」는 아니다',
               '글 하나에 여러 출장이 묶이기도 한다 — 출장 횟수가 아니라 글 수다'], 원, 못)
    칸('국외계획', '국외출장 계획 글', '의원 국외출장', '건', '글의 해(제목·올린 날)', 점검, 시황판=True, 온전한해=str(오늘.year - 1))
    칸('국외결과', '국외출장 결과 보고 글', '의원 국외출장', '건', '글의 해(제목·올린 날)', 점검, 시황판=True, 온전한해=str(오늘.year - 1))


# ── 7. 업무추진비 실제 내역 — 누리집 업무추진비 게시판 글 안 파일을 우리가 푼 것(read_post_files.py), 번호로 ──
#    ⛔ 시황판에는 안 올린다 — 곳마다 게시판에 남은 달이 다르고, 부단체장·시책추진이 섞여 실린 곳이 있어 줄 세우면 안 된다
섞임말 = {'단체장': r'부시장|부군수|부구청장|부지사|부단체장|국장|실장', '의장': r'부의장|공통경비|위원장'}


def 실제():
    rows = 읽기gz('data', 'expense_rows.json.gz')['줄']
    셈 = collections.defaultdict(lambda: [0, 0, set(), False])
    원, 못, 날없음 = collections.defaultdict(set), collections.Counter(), collections.Counter()
    for r in rows:
        원[r['고르기']].add(r['곳'])
        c = 번호(r['곳'])
        if c is None:
            못[f'{r["이름"]} {r["곳"]}'] += 1
            continue
        해 = (r.get('날짜') or '')[:4]
        if not 해:
            날없음[r['고르기']] += 1
            continue
        if 해 not in 해들:
            continue
        s = 셈[(c, r['고르기'], 해)]
        s[0] += r['금액']
        s[1] += 1
        s[2].add(r['날짜'][:7])
        s[3] = s[3] or bool(re.search(섞임말[r['고르기']], r['글']))
    for (cd, 고르기, 해), (돈, n, 달, 섞) in 셈.items():
        넣기(고르기 + '글합계', cd, 해, 돈, cd)
        넣기(고르기 + '글건수', cd, 해, n, cd)
        넣기(고르기 + '글달수', cd, 해, len(달), cd)
        if 섞:
            넣기(고르기 + '글섞임', cd, 해, 1, cd)
    for 고르기, 누구, 섞임설명 in (('단체장', '시장·군수·구청장·도지사가', '부단체장·실국장 몫이 같이 실린 글'),
                               ('의장', '의장(부의장 포함)이', '부의장·의정 공통경비·위원장 몫이 같이 실린 글')):
        점검 = 점검틀(f'누리집 업무추진비 게시판에서 제목에 {누구} 든 글 — 붙은 파일·본문 표를 우리가 풀었다',
                  '자치단체 번호(게시판 자리를 찾을 때 243곳 목록으로 셌다)',
                  f'게시판에서 읽힌 곳 {len({cd for (cd, g, _) in 셈 if g == 고르기})}곳 — 곳마다 게시판에 남은 달이 다르다(「몇 달치」 칸)',
                  ['편성액(위 「업무추진비 편성」)과 견주지 말 것 — 기관운영·시책추진이 섞여 실리고, 곳마다 싣는 범위가 다르다',
                   f'{섞임설명}이 섞인 해는 「섞임」으로 표시했다',
                   '같은 날·같은 금액·같은 곳·같은 내용이 본문 표와 파일에 겹쳐 실리면 하나로 셌다',
                   f'날짜를 못 읽은 줄 {날없음[고르기]}개 — 해를 몰라 뺐다'], 원[고르기], 못)
        칸(고르기 + '글합계', f'{"의장(부의장 포함)" if 고르기 == "의장" else "단체장"} 글에 실린 업무추진비', '업무추진비 실제(누리집 글)', '원', '쓴 날', 점검)
        칸(고르기 + '글달수', '　몇 달치가 실렸나', '업무추진비 실제(누리집 글)', '달', '쓴 날', 점검)
        칸(고르기 + '글건수', '　몇 건인가', '업무추진비 실제(누리집 글)', '건', '쓴 날', 점검)
        칸(고르기 + '글섞임', '　다른 사람 몫이 섞인 글', '업무추진비 실제(누리집 글)', '섞임', '쓴 날', 점검)


def main():
    for 하나 in (세출, 계약, 편성, 투자심사, 의회, 국외출장, 실제):
        하나()
    for m in 지표:
        if 겹침.get(m['id']):
            m['점검'] = {**m['점검'], '겹침': 겹침[m['id']][:20]}
            m['시황판'] = False
            print(f'⚠️ {m["이름"]}: 한 칸에 두 원자료가 겹쳤다 {len(겹침[m["id"]])}곳 — 시황판에서 뺐다')
        m['붙은곳'] = 붙은곳([m['id']])
    out = {'만든날': str(오늘), '해들': 해들, '곳수': len(목록), '지표': 지표,
           '곳': {cd: {i: v for i, v in d.items() if v} for cd, d in sorted(값.items())}}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    print(f'구움: site/data/side.json ({os.path.getsize(OUT) / 1024:,.0f} KB) · 지표 {len(지표)}')
    for m in 지표:
        p = m['점검']
        print(f'  {m["묶음"]:<14} {m["이름"]:<24} 붙은 곳 {m["붙은곳"]:>3}/{len(목록)} · 원자료 곳 {p["원자료곳"]:>3} · '
              f'못 붙음 {sum(n for _, n in p["못붙음"])}줄 · 시황판 {m["온전한해"] if m["시황판"] else "-"}')


if __name__ == '__main__':
    main()
