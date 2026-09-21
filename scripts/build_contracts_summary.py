# 계약 원본을 자치단체별로 묶는다 — data/contracts/*.json.gz → data/contracts_summary.json
#
#   python scripts/build_contracts_summary.py              다 다시 센다 (5분쯤)
#   python scripts/build_contracts_summary.py --해 2026     그 해 것만 다시 센다
#
# ⚠️ **해가 쌓이면 전수 재집계가 무거워진다.** 하루치가 계속 들어오므로,
#    평소에는 `--해` 로 올해치만 다시 세고 지난해 것은 그대로 둔다.
#    (합쳐 둔 결과를 읽어 그 해 칸만 갈아끼운다. 지난해 자료가 뒤늦게 고쳐지면 전수로 한 번 돌릴 것.)
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
# ⚠️ 금액은 `ctrt_tot_tott_amt`(계약 총액, 원)다. **그 해에 맺은 계약의 총액**이지 그 해에 나간 돈이 아니다.
#
# ⚠️⚠️ **다년계약이 두 번 들어온다(2026-09-21 에 잡음).** 인천미추홀구 생활폐기물 수집운반을 보면
#    「2025년~2027년 …(1권역)」 200억과 「…(1권역)(1년차)」 66억이 **같은 날 따로** 들어와 있다.
#    그래서 우리 셈이 지방재정365 `수의계약비율` 보다 커진다(미추홀구 70.9% vs 46.6%).
#    전국으로는 금액의 2.3%뿐이지만 **한 곳에서는 판을 뒤집는다.**
#    → 합치거나 빼지 않는다. 대신 **`다년금액` 으로 세어 화면이 경고하게 한다.**
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
import re
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
# 계약명에 기간이 적힌 것 — 「2025년~2027년 …」, 「…(1년차)」
다년표기 = re.compile(r'20\d\d\s*년?\s*[~∼-]\s*20\d\d|\d\s*년\s*차')


def main():
    골라낸해 = None
    if '--해' in sys.argv:
        골라낸해 = sys.argv[sys.argv.index('--해') + 1]

    files = sorted(glob.glob(os.path.join(IN, '*.json.gz')))
    모든파일 = len(files)          # 화면 꼬리말이 「원본 며칠치」를 여기서 읽는다
    if 골라낸해:
        # 파일 이름이 날짜(20260921.json.gz)라 이름만 보고 고른다
        files = [f for f in files if os.path.basename(f).startswith(골라낸해)]
        print(f'{골라낸해}년치 파일 {len(files)}개만 다시 센다')
    else:
        print(f'파일 {len(files)}개를 센다')

    # (laf_cd, 연도) → 셈
    셈 = collections.defaultdict(lambda: {
        '건수': 0, '금액': 0, '수의건수': 0, '수의금액': 0, '다년건수': 0, '다년금액': 0,
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
            if 다년표기.search(r.get('ctrt_trgt_nm') or ''):
                s['다년건수'] += 1
                s['다년금액'] += 금액
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
            '다년건수': s['다년건수'],
            '다년금액': s['다년금액'],
            '다년몫': round(s['다년금액'] / s['금액'] * 100, 1) if s['금액'] else None,
            '상위5몫': round(sum(v for _, v in 상위) / s['금액'] * 100, 1) if s['금액'] else None,
            '상위5': [{'이름': k, '금액': v} for k, v in 상위],
            '종류': dict(s['종류'].most_common()),
        }
        # 자치단체 화면에 세울 것 — 상위 업체를 금액·건수·수의금액까지
        자세히[cd][해] = {
            '건수': s['건수'], '금액': s['금액'],
            '수의건수': s['수의건수'], '수의금액': s['수의금액'],
            '다년건수': s['다년건수'], '다년금액': s['다년금액'],
            '업체수': len(업체),
            '종류': dict(s['종류'].most_common()),
            '업체': [[k, v[0], v[1], v[2]] for k, v in 차례[:상위N]],
        }

    범위 = {'첫날': 첫날, '끝날': 끝날, '파일': 모든파일, '버린것': 버린것,
            '한도': 한도, '금액없음': 금액없음}
    수상 = sorted(수상한줄, key=lambda x: -x['금액'])

    # 한 해만 다시 셌으면 **앞서 해 둔 다른 해는 그대로 둔다**
    if 골라낸해 and os.path.exists(OUT):
        옛 = json.load(open(OUT, encoding='utf-8'))
        for cd, 해별 in 옛['곳'].items():
            for 해, v in 해별.items():
                if 해 != 골라낸해:
                    곳[cd].setdefault(해, v)
                    자세히[cd].setdefault(해, None)      # 아래에서 옛 파일로 채운다
        이름 = {**옛.get('곳이름', {}), **이름}
        수상 = sorted([x for x in 옛.get('수상한줄', []) if x['날'][:4] != 골라낸해] + 수상,
                     key=lambda x: -x['금액'])
        범위['첫날'] = min(첫날, 옛['범위']['첫날']) if 첫날 else 옛['범위']['첫날']
        범위['끝날'] = max(끝날, 옛['범위']['끝날'])
        범위['한해만'] = 골라낸해

    out = {
        '만든날': __import__('datetime').date.today().isoformat(),
        '범위': 범위,
        '수상한줄': 수상,
        '곳이름': 이름,
        '곳': 곳,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))

    # 곳마다 한 파일씩 — 화면은 고른 곳 것만 받아 간다
    os.makedirs(곳별, exist_ok=True)
    for cd, 해별 in 자세히.items():
        if 골라낸해:
            # 이 곳의 옛 파일에서 다른 해는 그대로 가져온다
            옛길 = os.path.join(곳별, f'{cd}.json')
            옛해 = json.load(open(옛길, encoding='utf-8'))['해'] if os.path.exists(옛길) else {}
            해별 = {**옛해, **{k: v for k, v in 해별.items() if v is not None}}
        with open(os.path.join(곳별, f'{cd}.json'), 'w', encoding='utf-8') as f:
            json.dump({'laf_cd': cd, '이름': 이름.get(cd, ''),
                       '범위': out['범위'], '칸': ['업체', '금액', '건수', '수의금액'],
                       '해': 해별}, f, ensure_ascii=False, separators=(',', ':'))
    print(f'   곳별 파일 {len(자세히)}개 → site/data/contracts/')

    총건 = sum(v['건수'] for c in 곳.values() for v in c.values())
    총액 = sum(v['금액'] for c in 곳.values() for v in c.values())
    print(f'\n적음: data/contracts_summary.json ({os.path.getsize(OUT)/1024/1024:.1f} MB)')
    print(f'   {범위["첫날"]}~{범위["끝날"]} · 자치단체 {len(곳)}곳 · {총건:,}건 · '
          f'{총액/1e12:.1f}조원 · 버린 줄 {버린것}')
    print(f'   금액 0 인 줄 {금액없음:,}개')
    다년 = sum(v['다년금액'] for c in 곳.values() for v in c.values())
    print(f'   계약명에 기간이 적힌 줄 {다년/1e12:.2f}조 ({다년/max(1,총액)*100:.2f}%) '
          f'— 총액 줄과 연차 줄이 겹쳐 들어온다')
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
