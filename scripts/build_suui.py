# 나라장터 지자체 수의계약(사유 붙은 것)을 자치단체 × 해로 묶는다 — data/수의계약/ → site/data/suui.json
#
#   python scripts/build_suui.py               data/수의계약/ (봇이 R2 에서 내려받은 것)
#   python scripts/build_suui.py <폴더>         다른 폴더 — 시험용
#
# ⚠️ 원자료는 R2(수의계약/)에만 있고 **이 PC 엔 R2 키가 없다** — 그래서 달마다 봇(monthly.yml)이 내려받아 굽는다.
# 무엇을 세나(2026-10-16 사용자 답 4) — 「왜 수의계약인가」(근거 조항)·「동네 업체가 받았나」(사업자번호 → 조달업체 등록 주소).
#   · 1인 견적 / 2인 이상 견적은 여기 말고 지방재정365 계약현황(contracts_summary)에서 센다 — 나라장터 줄엔 그 칸이 없다.
# ⚠️⚠️ **같은 계약이 계약번호만 바꿔 다시 올라온다(2026-10-26 잼).** 2025년 203만 줄 중 106만 줄이 번호 말고는 똑같다
#    → 번호를 뺀 나머지 칸이 다 같으면 하나로 센다. 그래도 고쳐 다시 올린 변경 계약(날·금액이 다름)은 못 거른다:
#    거른 뒤 지방재정365 수의계약과 견주면 곳마다 건수는 가운데 1.13배(10~90% 0.55~1.58)지만 **금액은 1.81배**로 부푼다.
#    「기관·계약명·업체」로 묶으면 같은 이름의 따로 맺은 계약까지 합쳐져 0.81배로 모자란다 — 맞는 열쇠가 없다.
#    → **화면은 건수 몫(%)만 쓴다. 금액 칸은 싣지만 합계·몫으로 내걸지 말 것.** 금액은 계약현황(contracts_summary) 몫이다.
#    ⭐ 2026-10-26 부터 받는 파일엔 원계약·차수 칸이 있다(fetch_bizno.py) → 있으면 원계약마다 차수가 가장 큰 줄 하나만 센다.
#       2025년 12달은 suui-refetch.yml 이 다시 받아 채운다. 다 차면 2025 금액을 지방재정365 와 다시 견줘 볼 것.
#       ponytail: 차수 칸 있는 해와 없는 해에 걸친 계약은 두 번 셀 수 있다 — 2024·2026 도 다시 받으면 사라진다
# ⚠️ 2024년치는 `사유` 칸이 거의 비고 `법` 칸만 찼다 → 조항으로 묶고, 이름은 그 조항에 가장 많이 붙은 사유를 쓴다.
# ⭐ 같은 업체와 여러 번 맺었나(2026-10-26 사용자 — 「유착을 보려는 게 아니라 구조적 문제가 있나 보는 게 먼저」, 업체 이름은 공개된 것이라 싣는다)
#    → site/data/suui/<코드>.json: 작년 한 해, 업체당 건수 분포와 가장 여러 번 맺은 업체 열 곳·그 계약들. 우리 동네가 고른 곳 것만 받는다.
# 기관 이름(「경상북도 구미시 맑은물사업소」)의 앞 두 낱말로 243곳에 붙인다 — 교육청·통합 뒤 광주·전남 본청은 못 붙인다(따로 센다).

import collections
import glob
import gzip
import json
import os
import sys
from datetime import date

from build_grants import 시도줄임

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'data', '수의계약')
동네칸 = ['이 동네', '같은 시·도 다른 곳', '다른 시·도', '주소 모름']
조항N = 6      # 곳마다 금액 큰 조항 여섯 + 그 밖
업체N = 10     # 곳마다 가장 여러 번 맺은 업체 열 곳
계약N = 50     # 업체마다 계약은 금액 큰 차례로 쉰 건까지(포항은 한 업체 377건 — 파일이 192KB 가 됐다). 건수는 다 센다
업체해 = str(date.today().year - 1)      # 업체 목록은 다 끝난 마지막 해만 — 우리 동네 계약해와 같다
분포칸 = ['한 번', '2~4번', '5~9번', '10번 넘게']


def 읽기(경로):
    with gzip.open(경로, 'rt', encoding='utf-8') as f:
        return json.load(f)


def main():
    idx = json.load(open(os.path.join(ROOT, 'site', 'data', 'loc', 'index.json'), encoding='utf-8'))
    코드 = {x['이름']: x['cd'] for x in idx['곳']}
    시도of = {x['cd']: x['시도'] for x in idx['곳']}
    광역 = {x['cd'] for x in idx['곳'] if x['갈래'] == '광역'}

    def 곳찾기(이름):
        t = (이름 or '').split()
        if not t:
            return None
        머리 = t[0][:-1] if t[0].endswith('도청') else t[0]      # 「경기도청 북부청사」
        후보 = ['광주', '전남'] if 머리 == '전남광주통합특별시' else ([시도줄임[머리]] if 머리 in 시도줄임 else [])
        if len(t) > 1:
            for s in 후보:
                n = {'인천서해구': '인천서구'}.get(s + t[1], s + t[1])
                if n in 코드:
                    return 코드[n]
        return 코드.get(후보[0] + '본청') if len(후보) == 1 else None

    # 사업자번호 → 업체가 있는 곳(조달업체 등록, 등록해 차례라 늦은 등록이 덮는다)
    업체곳, 업체이름 = {}, {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'vendors', '*.json.gz'))):
        for v in 읽기(f):
            if v.get('번호'):
                업체곳[v['번호']] = 곳찾기(v.get('지역'))
                업체이름[v['번호']] = [v.get('이름') or '', ' '.join((v.get('지역') or '').split()[:2])]

    파일 = sorted(glob.glob(os.path.join(IN, '*.json.gz')) + glob.glob(os.path.join(IN, '일', '*.json.gz')))
    if not 파일:
        raise SystemExit(f'{IN} 에 파일이 없다 — R2 내려받기가 됐나')
    계약 = {}                  # 원계약(없으면 계약번호 뺀 칸들) → (날, cd, 금액, 법, 사유, 동네칸번호, 업체번호, 계약명, 차수)
    사유꼴 = collections.defaultdict(collections.Counter)   # 법 → {사유: 건수}
    못붙임 = collections.Counter()
    for f in 파일:
        표 = 읽기(f)
        k = {n: j for j, n in enumerate(표['칸'])}
        for r in 표['줄']:
            if '원자료' in k:      # 2026-10-26 뒤 파일은 모든 계약 줄 — 지자체 수의계약만 고른다(그 전 파일은 이미 골라 담았다)
                o = r[k['원자료']]
                if o.get('cntrctInsttJrsdctnDivNm') != '지방자치단체' or '수의' not in str(o.get('cntrctCnclsMthdNm') or ''):
                    continue
            법 = (r[k['법']] or '').strip() or '근거 조항 없음'
            사유 = (r[k['사유']] or '').strip()
            if 사유:
                사유꼴[법][사유] += 1
            cd = 곳찾기(r[k['곳']])
            금액 = r[k['금액']] or 0
            if not cd:
                못붙임[r[k['곳']]] += 금액
                continue
            날 = r[k['날']] or ''
            번호 = (r[k['업체']] or [None])[0]     # ponytail: 공동수급은 첫 업체 하나로 — 몫을 나누려면 업체마다 금액 칸이 필요
            u = 업체곳.get(번호)
            칸 = 3 if not u else 0 if (u == cd or (cd in 광역 and 시도of[u] == 시도of[cd])) else 1 if 시도of[u] == 시도of[cd] else 2
            if 금액 <= 0:                         # 감액 변경으로 보이는 음수·0원 줄(2025 년 29줄)
                continue
            원 = r[k['원계약']] if '원계약' in k else None
            차 = r[k['차수']] if 원 else -1
            키 = ('#', 원) if 원 else (r[k['기관']], 날, r[k['갈래']], 금액, r[k['총액']], 법, 사유, tuple(r[k['업체']] or ()), r[k['건']])   # 없으면 계약번호만 뺀 전부
            옛 = 계약.get(키)
            if 옛 and (옛[-1], 옛[0]) > (차, 날):
                continue
            건 = r[k['건']] or (r[k['원자료']].get('cnstwkNm') if '원자료' in k else None)   # 공사 이름은 cnstwkNm(2026-10-26 전 파일엔 빔)
            계약[키] = (날, cd, 금액, sys.intern(법), sys.intern(사유), 칸, 번호, 건, 차)

    법이름 = {법: c.most_common(1)[0][0] for 법, c in 사유꼴.items()}
    셈 = collections.defaultdict(lambda: {'건수': 0, '금액': 0, '법': collections.Counter(), '법건': collections.Counter(), '동네': [0, 0, 0, 0]})   # 동네 = 건수
    첫날, 끝날 = min(x[0] for x in 계약.values() if x[0]), max(x[0] for x in 계약.values())
    # 사유 글로 묶는다 — 조항이 달라도 사유가 같으면 한 줄(「2천만원 이하 물품 또는 용역」이 두 조항으로 갈려 왔다).
    #   사유가 빈 줄은 그 조항에 가장 많이 붙은 사유, 그것도 없으면 조항 이름 그대로
    업체별 = collections.defaultdict(lambda: collections.defaultdict(list))   # cd → 업체번호 → [(날, 금액, 계약명, 사유)]
    이름꼴 = lambda x: ' '.join((x or '').split())
    for 날, cd, 금액, 법, 사유, 칸, 번호, 건, _ in 계약.values():
        if len(날) < 4:        # 체결일·계약일 둘 다 빈 줄
            continue
        법 = 사유 or 법이름.get(법) or ('근거 조항이 비어 있음' if '(조 항 호 )' in 법 else 법)   # 「지방계약법 (조 항 호 )」로 빈 채 온다
        if 날[:4] == 업체해 and 번호:
            업체별[cd][번호].append((날, 금액, 이름꼴(건), 법))
        s = 셈[(cd, 날[:4])]
        s['건수'] += 1
        s['금액'] += 금액
        s['법'][법] += 금액
        s['법건'][법] += 1
        s['동네'][칸] += 1

    법들 = sorted({법 for s in 셈.values() for 법 in s['법']})
    법번호 = {법: j for j, 법 in enumerate(법들)}
    곳 = collections.defaultdict(dict)
    for (cd, 해), s in 셈.items():
        위 = s['법건'].most_common(조항N)
        나머지 = [s['금액'] - sum(s['법'][b] for b, _ in 위), s['건수'] - sum(n for _, n in 위)]
        곳[cd][해] = [s['건수'], s['금액'], [[법번호[b], n, s['법'][b]] for b, n in 위] + ([[-1, 나머지[1], 나머지[0]]] if 나머지[1] else []), s['동네']]

    # 같은 업체와 여러 번 — 곳마다 한 파일(작년). 금액은 계약마다 그대로 싣는다(고쳐 다시 올린 계약이 따로 있을 수 있다)
    곳폴더 = os.path.join(ROOT, 'site', 'data', 'suui')
    os.makedirs(곳폴더, exist_ok=True)
    for f in glob.glob(os.path.join(곳폴더, '*.json')):
        os.remove(f)
    for cd, 업 in 업체별.items():
        분포 = [[0, 0] for _ in 분포칸]
        for 줄 in 업.values():
            n = len(줄)
            칸 = 분포[0 if n == 1 else 1 if n < 5 else 2 if n < 10 else 3]
            칸[0] += 1
            칸[1] += n
        위 = sorted(업.items(), key=lambda kv: (-len(kv[1]), -sum(x[1] for x in kv[1])))[:업체N]
        with open(os.path.join(곳폴더, f'{cd}.json'), 'w', encoding='utf-8') as f:
            json.dump({'해': 업체해, '분포칸': 분포칸, '분포': 분포,
                       '칸': ['이름', '있는 곳', '건수', '2천만원 이하 사유 건수', '계약 [날, 금액, 계약명, 사유번호]'],
                       '업체': [[*업체이름.get(b, ['이름 못 찾음', '']), len(줄),
                               sum(1 for x in 줄 if x[3].startswith('추정가격 2천만원 이하')),
                               [[x[0], x[1], x[2], 법번호[x[3]]] for x in sorted(sorted(줄, key=lambda x: -x[1])[:계약N])]] for b, 줄 in 위]},
                      f, ensure_ascii=False, separators=(',', ':'))

    out = {'만든날': date.today().isoformat(), '첫날': 첫날, '끝날': 끝날, '파일': len(파일),
           '사유': 법들, '동네칸': 동네칸,
           '칸': ['건수', '금액(부풂 — 내걸지 말 것)', '사유별 [사유번호(-1=그 밖), 건수, 금액] 건수 큰 차례', '업체 있는 곳별 건수'], '곳': 곳}
    path = os.path.join(ROOT, 'site', 'data', 'suui.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))

    모두 = sum(s['금액'] for s in 셈.values()) + sum(못붙임.values())
    print(f'적음: site/data/suui.json ({os.path.getsize(path) // 1024}KB) · 파일 {len(파일)} · 계약 {len(계약):,} · {첫날}~{끝날} · 사유 {len(법들)}가지')
    print(f'못 붙인 기관 금액 {sum(못붙임.values()) / max(1, 모두) * 100:.1f}% — 큰 것', 못붙임.most_common(5))
    print(f'업체 목록 {업체해}년: {len(업체별)}곳 → site/data/suui/')
    for 해 in sorted({h for _, h in 셈 if h >= "2024"}):
        d = [sum(s['동네'][j] for (c, h), s in 셈.items() if h == 해) for j in range(4)]
        print(f'  {해}  ' + ' · '.join(f'{n} {v / max(1, sum(d)) * 100:.0f}%' for n, v in zip(동네칸, d)))


if __name__ == '__main__':
    main()
