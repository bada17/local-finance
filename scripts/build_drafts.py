# 「문」 초안 화면(drafts/index.html)이 쓰는 표를 굽는다 — drafts/data.json
#
#   python scripts/build_drafts.py
#
# ⚠️ 초안이다. drafts/ 는 site/ 밖이라 깃허브 페이지에 안 올라간다(pages.yml 은 site/** 만 본다).
#    보려면: python -m http.server 8000  →  http://localhost:8000/drafts/
# 이미 받은 자료만 쓴다 — dash.json(지표) · ongoing(진행 중인 사업) · score.json(투명성) · clik 알림(지켜보는 사업).
# 숫자는 여기서 고치지 않는다. 고향사랑 사업은 이름에 「고향사랑」이 든 것만 모은 것이라 쌓기·옮기기가 섞여 있다(합계 내지 말 것).

import gzip
import json
import os
import sys
from collections import Counter
from datetime import date

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
지표들 = ['세출예산 총액', '1인당 세출예산액', '재정자립도[당초]', '추경 증가율', '연말지출비율',
        '수의계약비율', '업무추진비비율', '행사축제경비비율', '사회복지비중', '예산대비채무비율']


def 읽기(*p):
    return json.load(open(os.path.join(ROOT, *p), encoding='utf-8'))


def main():
    dash = 읽기('site', 'data', 'dash.json')
    곳 = dash['곳']
    지표 = {}
    for x in dash['지표']:
        if x['이름'] in 지표들:
            지표[x['이름']] = {k: x[k] for k in ('단위', '기준', '연도', '나쁨', '비율', '금액')}
    # 추경 증가율의 분모(당초 예산)는 dash.json 에 없어 지표 원본에서 꺼낸다
    ind = 읽기('data', 'indicators', f"{dash['결산연도']}-{dash['예산연도']}.json")
    분모 = {x['laf_cd']: (x['지표'].get('추경 증가율') or {}).get('분모') for x in ind['자치단체']}
    지표['추경 증가율']['분모'] = [분모.get(c[0]) for c in 곳]

    집행, 분야, 고향 = [], [], []
    기준 = ''
    for c in 곳:
        p = os.path.join(ROOT, 'site', 'data', 'ongoing', f'{c[0]}.json.gz')
        if not os.path.exists(p):
            집행.append(None); 분야.append([]); 고향.append([])
            continue
        j = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        기준 = 기준 or j['기준']
        i = {k: n for n, k in enumerate(j['열차례'])}
        분야이름 = j['이름표']['분야']
        합 = Counter()
        for r in j['사업']:
            합[분야이름[r[i['분야']]]] += r[i['예산현액']] or 0
        집행.append([j['예산현액'], j['지출'], j['사업수']])
        분야.append([[k, v] for k, v in 합.most_common(6)])
        고향.append(sorted(([r[i['이름']], r[i['예산현액']] or 0, r[i['지출']] or 0]
                           for r in j['사업'] if '고향사랑' in r[i['이름']]), key=lambda r: -r[1]))

    s = 읽기('data', 'score.json')
    판 = {x['cd']: x['판'] for x in s['곳']}
    투명 = []
    for c in 곳:
        v = [(판.get(c[0]) or {}).get(h['키'], {}).get('값') for h in s['항목']]
        투명.append([v.count('O'), v.count('X'), len(v) - v.count('O') - v.count('X')])

    알림 = 읽기('data', 'clik', '알림_모음.json')
    지켜봄 = {}
    for 키, 줄 in 알림.items():
        달 = Counter(x['날짜'][:6] for x in 줄)
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
            '건수': len(줄), '회의수': len({x['글'] for x in 줄}), '갈래': Counter(x['갈래'] for x in 줄),
            '달': [[d, 달.get(d, 0)] for d in reversed(달들)], '최근': 최근[:8]}

    # 「얼마 받았나」는 아직 없다 — 누리집 게시판 수집(find_boards.js)이 고향사랑 게시판을 찾은 곳 수만
    b = 읽기('data', 'boards.json')['곳'] if os.path.exists(os.path.join(ROOT, 'data', 'boards.json')) else {}
    게시판 = {'찾은날': 읽기('data', 'boards.json')['만든날'] if b else '',
             '고향사랑': [cd for cd, v in b.items() if v.get('고향사랑')]}

    out = {'만든날': date.today().isoformat(), '진행기준': 기준, '결산연도': dash['결산연도'], '예산연도': dash['예산연도'],
           '곳칸': dash['곳칸'], '곳': 곳, '지표': 지표, '집행칸': ['예산현액', '지출', '사업수'], '집행': 집행,
           '분야': 분야, '고향': 고향, '투명칸': ['됨', '안 됨', '못 봄'], '투명항목수': len(s['항목']), '투명': 투명,
           '지켜봄': 지켜봄, '게시판': 게시판}
    os.makedirs(os.path.join(ROOT, 'drafts'), exist_ok=True)
    path = os.path.join(ROOT, 'drafts', 'data.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    print(f'적음: drafts/data.json ({os.path.getsize(path) // 1024}KB) · 고향사랑 사업 {sum(map(len, 고향))}개 · 진행 기준 {기준}')


if __name__ == '__main__':
    main()
