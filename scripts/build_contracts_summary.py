# 계약 원본을 자치단체별로 묶는다 — data/contracts/*.json.gz → data/contracts_summary.json
#
#   python scripts/build_contracts_summary.py
#
# 원본은 날짜별 파일 994개(165MB, 320만 건)다. **대화창에 쏟지 말 것** — 여기서 세어서
# 자치단체 × 연도로만 남긴다. 결과는 1MB 안쪽이다.
#
# 무엇을 세나 — 감시에 쓸 수 있는 것만.
#   · 건수·금액          그 해에 얼마를 계약으로 썼나
#   · **수의계약 비중**   경쟁 없이 준 것이 얼마나 되나 (건수·금액 두 갈래)
#   · 업체 수            몇 군데와 거래했나
#   · **상위 5개 업체 몫** 한 줌에 몰렸나 (금액 기준)
#   · 종류별(공사·용역·물품) 금액
#
# ⚠️ **연도는 계약일(`smz_ctrt_ymd`) 기준이다.** 받아 둔 범위가 2024-01-01 ~ 2026-09-20 이라
#    **2026년은 아홉 달치뿐**이다. 화면에서 2025년과 나란히 놓지 말 것.
# ⚠️ 금액은 `ctrt_tot_tott_amt`(계약 총액, 원)다. 변경계약이 따로 한 줄로 오는지는 확인 못 했다.
#
# ⚠️⚠️ **원자료에 자릿수 오류가 있다(2026-09-21 에 잡음).** 임실군 마을 진입로 관급자재가
#    **708조원**, 거창군 격자블록이 202조원으로 들어와 있다. 셋만으로 2025년 합계가
#    68조 → 978조로 부풀었다. 그래서 **1조원을 넘는 줄은 빼고 따로 적는다** —
#    실제로 제일 큰 진짜 계약은 인천대로 도로개량 8,211억이다.
#    **지우는 게 아니라 「수상한줄」로 남긴다.** 이것 자체가 공시 품질에 대한 할 말이다.

import collections
import glob
import gzip
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, 'data', 'contracts')
OUT = os.path.join(ROOT, 'data', 'contracts_summary.json')
곳별 = os.path.join(ROOT, 'site', 'data', 'contracts')      # 자치단체 화면 ⑥번 칸이 받아 간다
상위N = 30
한도 = 1_000_000_000_000        # 1조원. 이보다 큰 단일 계약은 자릿수 오류로 본다


def main():
    files = sorted(glob.glob(os.path.join(IN, '*.json.gz')))
    print(f'파일 {len(files)}개를 센다')

    # (laf_cd, 연도) → 셈
    셈 = collections.defaultdict(lambda: {
        '건수': 0, '금액': 0, '수의건수': 0, '수의금액': 0,
        '종류': collections.Counter(),        # 공사·용역·물품 금액
        '업체': {},                           # 업체 → [금액, 건수, 수의금액]
    })
    이름 = {}
    첫날 = 끝날 = ''
    버린것 = 0
    수상한줄 = []
    금액없음 = 0

    for i, f in enumerate(files, 1):
        try:
            rows = json.load(gzip.open(f, 'rt', encoding='utf-8'))
        except Exception as e:                      # 빈 날·깨진 파일은 건너뛴다
            버린것 += 1
            print(f'   건너뜀 {os.path.basename(f)} — {e}')
            continue
        for r in rows:
            cd = str(r.get('laf_cd') or '')
            날 = str(r.get('smz_ctrt_ymd') or '')
            if len(cd) != 7 or len(날) != 8:
                버린것 += 1
                continue
            if not 첫날 or 날 < 첫날:
                첫날 = 날
            if 날 > 끝날:
                끝날 = 날
            해 = 날[:4]
            금액 = int(r.get('ctrt_tot_tott_amt') or 0)
            if 금액 >= 한도:
                수상한줄.append({
                    'laf_cd': cd, '곳': r.get('laf_hg_nm') or '', '날': 날, '금액': 금액,
                    '계약명': (r.get('ctrt_trgt_nm') or '')[:60],
                    '방법': r.get('ctrt_mth_nm') or '', '업체': r.get('clt_nm') or '',
                })
                continue
            if 금액 <= 0:
                금액없음 += 1
            s = 셈[(cd, 해)]
            방법 = r.get('ctrt_mth_nm') or ''
            업체 = sys.intern((r.get('clt_nm') or '이름없음').strip())
            s['건수'] += 1
            s['금액'] += 금액
            if 방법.startswith('수의'):
                s['수의건수'] += 1
                s['수의금액'] += 금액
            s['종류'][r.get('ctrt_knd_nm') or '그밖'] += 금액
            칸 = s['업체'].get(업체)
            if 칸 is None:
                칸 = s['업체'][업체] = [0, 0, 0]
            칸[0] += 금액
            칸[1] += 1
            if 방법.startswith('수의'):
                칸[2] += 금액
            이름.setdefault(cd, r.get('laf_hg_nm') or '')
        if i % 100 == 0:
            print(f'   {i}/{len(files)}  ({len(셈)}칸)')

    곳 = collections.defaultdict(dict)
    자세히 = collections.defaultdict(dict)
    for (cd, 해), s in 셈.items():
        업체 = s['업체']
        차례 = sorted(업체.items(), key=lambda kv: -kv[1][0])
        상위 = [(k, v[0]) for k, v in 차례[:5]]
        곳[cd][해] = {
            '건수': s['건수'],
            '금액': s['금액'],
            '수의건수': s['수의건수'],
            '수의금액': s['수의금액'],
            '수의건수율': round(s['수의건수'] / s['건수'] * 100, 1) if s['건수'] else None,
            '수의금액률': round(s['수의금액'] / s['금액'] * 100, 1) if s['금액'] else None,
            '업체수': len(업체),
            '상위5몫': round(sum(v for _, v in 상위) / s['금액'] * 100, 1) if s['금액'] else None,
            '상위5': [{'이름': k, '금액': v} for k, v in 상위],
            '종류': dict(s['종류'].most_common()),
        }
        # 자치단체 화면에 세울 것 — 상위 업체를 금액·건수·수의금액까지
        자세히[cd][해] = {
            '건수': s['건수'], '금액': s['금액'],
            '수의건수': s['수의건수'], '수의금액': s['수의금액'],
            '업체수': len(업체),
            '종류': dict(s['종류'].most_common()),
            '업체': [[k, v[0], v[1], v[2]] for k, v in 차례[:상위N]],
        }

    out = {
        '만든날': __import__('datetime').date.today().isoformat(),
        '범위': {'첫날': 첫날, '끝날': 끝날, '파일': len(files), '버린것': 버린것,
                 '한도': 한도, '금액없음': 금액없음},
        '수상한줄': sorted(수상한줄, key=lambda x: -x['금액']),
        '곳이름': 이름,
        '곳': 곳,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))

    # 곳마다 한 파일씩 — 화면은 고른 곳 것만 받아 간다
    os.makedirs(곳별, exist_ok=True)
    for cd, 해별 in 자세히.items():
        with open(os.path.join(곳별, f'{cd}.json'), 'w', encoding='utf-8') as f:
            json.dump({'laf_cd': cd, '이름': 이름.get(cd, ''),
                       '범위': out['범위'], '칸': ['업체', '금액', '건수', '수의금액'],
                       '해': 해별}, f, ensure_ascii=False, separators=(',', ':'))
    print(f'   곳별 파일 {len(자세히)}개 → site/data/contracts/')

    총건 = sum(v['건수'] for c in 곳.values() for v in c.values())
    총액 = sum(v['금액'] for c in 곳.values() for v in c.values())
    print(f'\n적음: data/contracts_summary.json ({os.path.getsize(OUT)/1024/1024:.1f} MB)')
    print(f'   {첫날}~{끝날} · 자치단체 {len(곳)}곳 · {총건:,}건 · {총액/1e12:.1f}조원 · 버린 줄 {버린것}')
    print(f'   금액 0 인 줄 {금액없음:,}개')
    if 수상한줄:
        print(f'   ⚠️ 1조원 넘는 줄 {len(수상한줄)}개는 빼고 셌다 (자릿수 오류로 보인다)')
        for x in 수상한줄[:6]:
            print(f'      {x["금액"]/1e12:>9.1f}조  {x["곳"]} {x["계약명"][:34]} {x["날"]}')
    for 해 in sorted({y for c in 곳.values() for y in c}):
        건 = sum(c[해]['건수'] for c in 곳.values() if 해 in c)
        액 = sum(c[해]['금액'] for c in 곳.values() if 해 in c)
        수의 = sum(c[해]['수의금액'] for c in 곳.values() if 해 in c)
        print(f'   {해}  {건:>9,}건  {액/1e12:>5.1f}조  수의 {수의/max(1,액)*100:>4.1f}%')


if __name__ == '__main__':
    main()
