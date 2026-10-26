# 첫 화면 「우리 동네 페이지」(site/index.html)가 쓰는 표를 굽는다 — site/data/town.json
#
#   python scripts/build_town.py
#
# 이미 받은 자료만 쓴다 — dash.json·지표 원본(지표) · ongoing(진행 중인 사업) · score.json(투명성)
#   · contracts_summary(계약) · clik 알림(지켜보는 사업). 숫자는 여기서 고치지 않는다.
# 고향사랑 사업은 이름에 「고향사랑」이 든 것만 모은 것이라 쌓기·옮기기가 섞여 있다(합계 내지 말 것).
# 문을 고르는 내부 검토판 drafts/index.html 도 이 파일을 읽는다.
#
# ⚠️ 2026-10-15 에 원자료와 맞춰 보고 고친 것 — 화면 글을 바꿀 때 다시 볼 것
#   · 비율은 dash.json 에서 소수 둘째 자리로 잘려 있어 같은 값이 수십 곳씩 겹친다(의회경비 최대 21곳).
#     순위는 지표 원본의 금액 ÷ 분모로 다시 낸 값으로 매긴다(243곳 전부 API 비율과 반올림 안에서 맞음).
#   · 1인당 세출예산액은 일반회계 ÷ 인구다(세출예산 총액은 총계) — 화면에 「일반회계」라고 적는다.
#   · 연말지출비율의 분모는 세출결산 전체가 아니다(이 지표가 세는 돈, 세출결산의 0.1~32%, 가운데 12%).
#     「한 해 쓴 돈의 몇 %」라고 쓰면 틀린다. 그래서 분모 금액을 같이 싣는다.

import gzip
import json
import os
import re
import sys
from collections import Counter
from datetime import date

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
지표들 = ['세출예산 총액', '1인당 세출예산액', '재정자립도[당초]', '추경 증가율', '연말지출비율',
        '수의계약비율', '업무추진비비율', '행사축제경비비율', '지방의회경비비율', '공무원 국외여비비율',
        '의회 국외여비비율', '사회복지비중', '예산대비채무비율',
        # 2026-10-16 넣은 다섯 중 넷 — 자립도·자주도는 최종(2025)·결산(2024). 당초는 아래 「올해 당초」(2026)를 쓴다
        '재정자립도[최종]', '재정자립도[결산]', '재정자주도[당초]', '재정자주도[최종]', '재정자주도[결산]',
        '1인당 지방세부담액',   # 지방세 ÷ 인구(천원). 법인이 낸 것도 들어 있다 — 「주민이 낸 세금」이 아니다
        '자체사업비중', '보조사업비중', '정책사업비중']   # 「누가 정한 돈인가」(2026-10-20 사용자 ⓑ)


def 읽기(*p):
    return json.load(open(os.path.join(ROOT, *p), encoding='utf-8'))


정해진 = re.compile(r'인력운영|인건비|기초연금|생계급여')
회계 = re.compile(r'보전지출|내부거래|예비비|예치|상환|통합계정|재정안정화|전출금|예탁')


def main():
    dash = 읽기('site', 'data', 'dash.json')
    곳 = dash['곳']
    지표 = {}
    for x in dash['지표']:
        if x['이름'] in 지표들:
            지표[x['이름']] = {k: x[k] for k in ('단위', '기준', '연도', '나쁨', '비율', '금액')}
    # 분모와 반올림 안 한 비율은 지표 원본에서 꺼낸다
    ind = 읽기('data', 'indicators', f"{dash['결산연도']}-{dash['예산연도']}.json")
    원본 = {x['laf_cd']: x['지표'] for x in ind['자치단체']}
    for k, v in 지표.items():
        분모 = [((원본.get(c[0]) or {}).get(k) or {}).get('분모') for c in 곳]
        if not any(분모):
            continue
        v['분모'] = 분모
        v['비율'] = [round(a / b * 100, 6) if a is not None and b else r for a, b, r in zip(v['금액'], 분모, v['비율'])]
    # 세출예산 총액엔 기금이 들어 있다 — 자치단체별 세입 판의 재원 합은 기금을 뺀 회계 몫이라, 첫 카드에 기금을 같이 적는다(2026-10-19)
    지표['세출예산 총액']['기금'] = [((원본.get(c[0]) or {}).get('세출예산 총액') or {}).get('기금') for c in 곳]
    # 자립도·자주도는 올해 예산(당초)으로 본다(2026-10-16 사용자). dash 의 [당초] 는 최종과 해를 맞춘 것이라 한 해 늦다.
    for 이름 in ('재정자립도', '재정자주도'):
        k = f'{이름}[올해 당초]'
        v = [((원본.get(c[0]) or {}).get(k) or {}) for c in 곳]
        지표[k] = {'단위': '%', '기준': '예산[당초]', '연도': next(x['연도'] for x in v if x), '나쁨': 0,
                  '비율': [x.get('비율') for x in v]}

    집행, 분야, 부문, 고향, 큰사업, 재원몫, 정해진합 = [], [], [], [], [], [], []
    기준 = 받은날 = ''
    for c in 곳:
        p = os.path.join(ROOT, 'site', 'data', 'ongoing', f'{c[0]}.json.gz')
        if not os.path.exists(p):
            집행.append(None); 분야.append([]); 부문.append({}); 고향.append([]); 큰사업.append([]); 재원몫.append(None); 정해진합.append(None)
            continue
        j = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        기준 = 기준 or j['기준']
        받은날 = max(받은날, j.get('받은날', ''))
        i = {k: n for n, k in enumerate(j['열차례'])}
        분야이름 = j['이름표']['분야']
        합, 속 = Counter(), {}
        for r in j['사업']:
            합[분야이름[r[i['분야']]]] += r[i['예산현액']] or 0
            속.setdefault(분야이름[r[i['분야']]], Counter())[j['이름표']['부문'][r[i['부문']]]] += r[i['예산현액']] or 0
        집행.append([j['예산현액'], j['지출'], j['사업수']])
        # 「올해 지금까지 얼마 썼나」 큰 사업 다섯 · 「돈은 어디서 나왔나」 재원 넷(2026-10-20 사용자 ⓐⓑ)
        #   큰 사업은 어디나 인력운영비·기초연금·생계급여가 1~3위라(239곳 거의 전부) 그 셋은 「정해진 돈」 한 줄로 묶고,
        #   보전지출·예비비 같은 회계 숫자는 아예 뺀 뒤 **동네 돈**(광역은 시도비, 기초는 시군구비) 큰 순으로(2026-10-20 사용자)
        자기 = i['시도비'] if c[3] == '광역' else i['시군구비']
        고른 = [r for r in j['사업'] if not 정해진.search(r[i['이름']]) and not 회계.search(r[i['이름']])]
        큰사업.append([[r[i['이름']], r[i['예산현액']] or 0, r[i['지출']] or 0, r[자기] or 0]
                      for r in sorted(고른, key=lambda r: -(r[자기] or 0))[:5]])
        정해진합.append(sum(r[i['예산현액']] or 0 for r in j['사업'] if 정해진.search(r[i['이름']])))
        재원몫.append([j['국비'], j['시도비'], j['시군구비'], j['기타']])
        분야.append([[k, v] for k, v in 합.most_common()])   # 다섯째 「분야별 예산」 — 전부(2026-10-16, 전에는 6개)
        부문.append({k: [[n, v] for n, v in c.most_common()] for k, c in 속.items() if len(c) > 1})   # 눌러 펼치는 부문(2026-10-20) — 하나뿐인 분야(기타)는 안 펼친다
        고향.append(sorted(([r[i['이름']], r[i['예산현액']] or 0, r[i['지출']] or 0]
                           for r in j['사업'] if '고향사랑' in r[i['이름']]), key=lambda r: -r[1]))

    # 세금 종류별(2024 결산, 지방세통계연감) — 자치단체별 세입 판과 같은 것(build_revenue.py 가 낸 것을 그대로).
    # ⚠️ 그 구역에서 걷힌 지방세 전부(광역세 + 기초세)다. 지표 「1인당 지방세부담액」(그 자치단체 예산의 지방세)과 다르다.
    세목 = []
    for c in 곳:
        p = os.path.join(ROOT, 'site', 'data', 'revenue', f'{c[0]}.json')
        x = 읽기('site', 'data', 'revenue', f'{c[0]}.json').get('세목') if os.path.exists(p) else None
        세목.append(x and {k: x.get(k) for k in ('해', '단위', '이곳것아님', '천원단위', '합계', '소계', '시도전체', '칸')})

    재원 = json.load(gzip.open(os.path.join(ROOT, 'data', 'revenue', 'FIACRV.json.gz'), 'rt', encoding='utf-8'))
    재원해 = max(int(r['_해']) for r in 재원)
    # 서울 구 — 예산(결산)의 「지방세수입」 = 연감 구세 + 공동재산세(특별시분 재산세를 25구에 똑같이 나눈 것).
    # 2026-10-16 확인: 2024 결산에서 25구 모두 차이가 679.17억으로 같다(천원 반올림 안). 「1명당 세금」에 이 몫이 들어 있다.
    지방세수입 = {r['laf_cd']: r['tott_sum_amt'] for r in 재원
                if int(r['_해']) == 재원해 and str(r.get('lvl_no')) == '2' and r.get('armk_nm') == '지방세수입'}
    for j, c in enumerate(곳):
        t = 세목[j]
        if c[2] == '서울' and c[3] == '구' and t and t.get('소계', {}).get('구세') and c[0] in 지방세수입:
            t['공동재산세'] = 지방세수입[c[0]] - t['소계']['구세'] * 1000

    # 투명성은 첫 화면에서 뺐다(2026-10-15, 선배 몫) — drafts/index.html 검토판만 쓴다
    s = 읽기('data', 'score.json')
    판 = {x['cd']: x['판'] for x in s['곳']}
    투명 = []
    for c in 곳:
        v = [(판.get(c[0]) or {}).get(h['키'], {}).get('값') for h in s['항목']]
        투명.append([v.count('O'), v.count('X'), len(v) - v.count('O') - v.count('X')])

    알림 = 읽기('data', 'clik', '알림_모음.json')
    지켜봄 = {}
    for 키, 줄 in 알림.items():
        if 키.startswith('_'):   # _마지막성공 같은 장부 칸
            continue
        달 = Counter(m for m, _ in {(x['날짜'][:6], x['글']) for x in 줄})   # 회의 수(같은 회의의 여러 쪽은 하나)
        y, m = date.today().year, date.today().month
        달들 = []
        for _ in range(18):   # 빈 달도 0 으로 — 건너뛰면 그래프가 시간을 속인다
            달들.append(f'{y}{m:02d}')
            y, m = (y, m - 1) if m > 1 else (y - 1, 12)
        본, 최근 = set(), []
        for x in sorted(줄, key=lambda x: x['날짜'], reverse=True):   # 회의록은 쪽마다 한 줄 — 회의 하나로 묶는다
            if x['글'] not in 본:
                본.add(x['글']); 최근.append(x)
        지켜봄[키.split(':', 1)[-1]] = {
            '처음': min(x['날짜'] for x in 줄),
            '임기회의수': len({x['글'] for x in 줄 if '20220701' <= x['날짜'] <= '20260630'}),   # 8대 의회(지난 4년)만
            '건수': len(줄), '회의수': len({x['글'] for x in 줄}), '갈래': Counter(x['갈래'] for x in 줄),
            '달': [[d, 달.get(d, 0)] for d in reversed(달들)], '최근': 최근[:8]}

    # 「얼마 받았나」는 아직 없다 — 누리집 게시판 수집(find_boards.js)이 고향사랑 게시판을 찾은 곳 수만
    b = 읽기('data', 'boards.json')['곳'] if os.path.exists(os.path.join(ROOT, 'data', 'boards.json')) else {}
    게시판 = {'찾은날': 읽기('data', 'boards.json')['만든날'] if b else '',
             '고향사랑': [cd for cd, v in b.items() if v.get('고향사랑')]}

    # 계약 — 다 끝난 마지막 해(올해는 아직 진행 중이라 뺀다). 조달청은 업체가 아니라 「대신 사 주는 곳」이라 상위 업체에서 뺀다
    cs = 읽기('data', 'contracts_summary.json')
    계약해 = str(date.today().year - 1)
    계약 = []
    for c in 곳:
        y = (cs['곳'].get(c[0]) or {}).get(계약해)
        if not y:
            계약.append(None)
            continue
        업체 = [u for u in y.get('상위5', []) if '조달청' not in u['이름']][:3]
        계약.append([y['건수'], y['수의건수'], y['수의건수율'], y['수의금액률'], y['금액'],
                   [[u['이름'], u['금액']] for u in 업체], y['수의금액'], y.get('1인건수'), y.get('1인금액'),
                   y.get('수의종류')])

    # 수의계약 근거 조항·업체 있는 곳 — 나라장터 줄(build_suui.py, 봇이 R2 에서 굽는다). 계약현황과 다른 자료라 따로 싣는다
    su = 읽기('site', 'data', 'suui.json') if os.path.exists(os.path.join(ROOT, 'site', 'data', 'suui.json')) else {'곳': {}}
    수의 = [(su['곳'].get(c[0]) or {}).get(계약해) for c in 곳]

    # 올해 빌릴 돈 — 올해 세입예산(재원별, FIRVBG)의 「지방채」(2026-10-26 사용자 「26년 지방채 발행계획은 따로 볼 수 있게」). 없으면 0
    채 = {r['laf_cd']: r['last_bdg_tott_amt'] for r in json.load(gzip.open(os.path.join(ROOT, 'data', 'revenue', 'FIRVBG.json.gz'), 'rt', encoding='utf-8'))
         if str(r['_해']) == dash['예산연도'] and r['armk_nm'] == '지방채'}
    지방채계획 = [채.get(c[0], 0) for c in 곳]

    # 2026 통합 뒤 계약 자료가 광주·전남 본청을 「광주 」·「전남 」(끝에 빈칸)으로 준다 — 짧은이름이 빈칸이 되어 제목이 사라졌다(10-16 발견)
    통합전이름 = {'2900000': '광주광역시', '4600000': '전라남도'}
    이름 = [통합전이름.get(c[0]) or cs['곳이름'].get(c[0], c[1]) for c in 곳]
    # 시·도 앞말은 그 시·도 본청 이름으로 맞춘다 — 계약 자료 이름이 섞여 온다(2026-10-19: 군위군이 「경상북도」(2023 대구 편입),
    # 정읍만 「전라북도」, 통합 뒤 광주·전남 기초가 「광주 동구」·「전남 목포시」).
    광역이름 = {c[2]: n for c, n in zip(곳, 이름) if c[3] == '광역'}
    assert all(' ' in n for c, n in zip(곳, 이름) if c[3] != '광역'), '기초 이름에 시·도 앞말이 없다'
    이름 = [n if c[3] == '광역' else f"{광역이름[c[2]]} {n.split(' ', 1)[1]}" for c, n in zip(곳, 이름)]
    out = {'만든날': date.today().isoformat(), '진행기준': 기준, '진행받은날': 받은날,
           '결산연도': dash['결산연도'], '예산연도': dash['예산연도'],
           '곳칸': dash['곳칸'], '곳': 곳, '지표': 지표, '집행칸': ['예산현액', '지출', '사업수'], '집행': 집행,
           '큰사업칸': ['이름', '예산현액', '지출', '동네 돈'], '큰사업': 큰사업, '정해진합': 정해진합, '재원칸': ['국비', '시도비', '시군구비', '기타'], '재원': 재원몫,
           '분야': 분야, '부문': 부문, '세목': 세목, '고향': 고향, '투명칸': ['됨', '안 됨', '못 봄'], '투명항목수': len(s['항목']), '투명': 투명,
           '지켜봄': 지켜봄, '게시판': 게시판,
           '이름': 이름, '계약해': 계약해,
           '계약칸': ['건수', '수의건수', '수의건수율', '수의금액률', '금액', '상위업체(조달청 뺌)', '수의금액', '1인건수', '1인금액', '수의종류 {종류: [건수, 금액]}'], '계약': 계약,
           '수의칸': su.get('칸'), '수의법': su.get('사유'), '수의동네칸': su.get('동네칸'), '수의끝날': su.get('끝날'), '수의': 수의,
           '지방채계획': 지방채계획}
    path = os.path.join(ROOT, 'site', 'data', 'town.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    print(f'적음: site/data/town.json ({os.path.getsize(path) // 1024}KB) · 고향사랑 사업 {sum(map(len, 고향))}개 · 진행 {받은날} 받음')


if __name__ == '__main__':
    main()
