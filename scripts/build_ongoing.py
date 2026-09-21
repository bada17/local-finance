# 「지금 돌아가는 사업」 화면에 넣을 데이터를 굽는다.
#
#   python scripts/build_ongoing.py 2600000 4373000 4612000
#   python scripts/build_ongoing.py 4612000 --month 202609
#
# 지방재정365 QWGJK(세부사업별 세출현황)를 자치단체별로 받아
# site/data/ongoing/<자치단체코드>.json 으로 낸다. 화면이 그 파일을 직접 읽는다.
#
# ⚠️ ep_amt 는 그날까지의 누계다. 두 날짜를 빼야 그 사이 집행액이 나온다.
#    여기서는 「올해 들어 지금까지 얼마나 썼나」로만 쓴다.
# ⚠️ 달만 넣어도 먹힌다(202609). 날짜를 하루하루 부르면 호출이 30배로 는다.
# ⚠️ 단체마다 올리는 시점이 다르다 — 2026년 것이 아직 없는 곳이 있다(전남본청이 그랬다).
#    없으면 그 단체는 건너뛰고, 있던 파일은 그대로 둔다. 못 받은 것은 없어졌다는 뜻이 아니다.

import json
import os
import sys
from datetime import date

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lofin import fetch, load_key  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'site', 'data', 'ongoing')


def build(code, month, key):
    fyr = month[:4]
    try:
        rows, total = fetch('QWGJK', {'fyr': fyr, 'exe_ymd': month, 'laf_cd': code}, key)
    except SystemExit as e:
        # INFO-200 은 「그 단체의 그 달 자료가 없다」는 뜻이다
        print(f'  {code}: 자료 없음 — 건너뜀 ({e})')
        return False
    if not rows:
        print(f'  {code}: 0행 — 건너뜀')
        return False
    if len(rows) != total:
        print(f'  {code}: {len(rows)}/{total} 덜 받았다 — 저장 안 함')
        return False

    사업 = []
    for r in rows:
        사업.append({
            'nm': r.get('dbiz_nm') or '',
            'cd': r.get('dbiz_cd') or '',
            'fld': r.get('fld_nm') or '',
            'part': r.get('part_nm') or '',
            'acnt': r.get('acnt_dv_nm') or '',
            'bdg': r.get('bdg_cash_amt') or 0,     # 예산현액
            'ep': r.get('ep_amt') or 0,            # 지출액(누계)
            'gb': r.get('bdg_ntep') or 0,          # 국비
            'sd': r.get('capep') or 0,             # 시도비
            'sgg': r.get('sggep') or 0,            # 시군구비
            'etc': r.get('etc_amt') or 0,          # 기타
        })
    사업.sort(key=lambda x: -x['bdg'])

    s = lambda k: sum(x[k] for x in 사업)  # noqa: E731
    out = {
        '자치단체': rows[0].get('laf_hg_nm') or '',
        'laf_cd': code,
        '연도': fyr,
        '기준': month,                      # 집행일자 인자로 준 것
        '받은날': date.today().isoformat(),
        '사업수': len(사업),
        '예산현액': s('bdg'), '지출': s('ep'),
        '국비': s('gb'), '시도비': s('sd'), '시군구비': s('sgg'), '기타': s('etc'),
        '사업': 사업,
    }

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f'{code}.json')
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    os.replace(tmp, path)

    kb = os.path.getsize(path) / 1024
    rt = out['지출'] / out['예산현액'] * 100 if out['예산현액'] else 0
    print(f"  {out['자치단체']}({code}) 사업 {len(사업):,}개 · 예산현액 {out['예산현액']/1e8:,.0f}억 · "
          f"지출 {out['지출']/1e8:,.0f}억({rt:.0f}%) · {kb:,.0f}KB")
    return True


def main():
    args = [a for a in sys.argv[1:]]
    month = None
    if '--month' in args:
        i = args.index('--month')
        month = args[i + 1]
        del args[i:i + 2]
    codes = args or ['2600000', '4373000', '4612000']
    if not month:
        t = date.today()
        # 이달 것이 아직 없을 수 있으니 지난달까지 물러선다
        month = f'{t.year}{t.month:02d}'

    key = load_key()
    print(f'진행 중인 사업 {month} · 인증키 {"있음" if key else "없음(한 쪽 5행)"}')
    ok = 0
    for cd in codes:
        if build(cd, month, key):
            ok += 1
    print(f'{ok}/{len(codes)} 곳 구움 → site/data/ongoing/')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
