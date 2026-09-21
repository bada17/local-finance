# 「지금 돌아가는 사업」 화면에 넣을 데이터를 굽는다.
#
#   python scripts/build_ongoing.py --all              243곳 전부 (전국 한 번에 받아 쪼갠다)
#   python scripts/build_ongoing.py 4612000            한 곳만
#   python scripts/build_ongoing.py --all --month 202609
#
# 지방재정365 QWGJK(세부사업별 세출현황)를 자치단체별로 갈라
# site/data/ongoing/<자치단체코드>.json.gz 로 낸다(눌러서). 화면이 받아서 푼다.
#
# ⚠️ ep_amt 는 그날까지의 누계다. 두 날짜를 빼야 그 사이 집행액이 나온다.
#    여기서는 「올해 들어 지금까지 얼마나 썼나」로만 쓴다.
# ⚠️ 달만 넣어도 먹힌다(202609). 날짜를 하루하루 부르면 호출이 30배로 는다.
# ⚠️ 단체마다 올리는 시점이 다르다 — 2026년 것이 아직 없는 곳이 있다(전남본청이 그랬다).
#    없으면 그 단체는 건너뛰고, 있던 파일은 그대로 둔다. 못 받은 것은 없어졌다는 뜻이 아니다.
#
# 파일이 243개나 되므로 **칸 이름을 빼고 줄줄이 늘어놓는다**(아래 열차례).
# 그냥 담으면 한 곳에 500KB 가 넘어 저장소가 감당이 안 된다.

import gzip
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

# 한 사업이 담기는 차례. 화면도 이 차례로 읽는다
열차례 = ['이름', '분야', '부문', '회계', '예산현액', '지출', '국비', '시도비', '시군구비', '기타']


def 굽기(code, rows, month):
    """한 자치단체의 행 목록을 파일 하나로 낸다."""
    이름표 = {'분야': [], '부문': [], '회계': []}
    자리 = {k: {} for k in 이름표}

    def 번호(칸, 값):
        값 = 값 or ''
        if 값 not in 자리[칸]:
            자리[칸][값] = len(이름표[칸])
            이름표[칸].append(값)
        return 자리[칸][값]

    사업 = []
    for r in rows:
        사업.append([
            r.get('dbiz_nm') or '',
            번호('분야', r.get('fld_nm')),
            번호('부문', r.get('part_nm')),
            번호('회계', r.get('acnt_dv_nm')),
            r.get('bdg_cash_amt') or 0,     # 예산현액
            r.get('ep_amt') or 0,           # 지출액(누계)
            r.get('bdg_ntep') or 0,         # 국비
            r.get('capep') or 0,            # 시도비
            r.get('sggep') or 0,            # 시군구비
            r.get('etc_amt') or 0,          # 기타
        ])
    사업.sort(key=lambda x: -x[4])

    합 = lambda i: sum(x[i] for x in 사업)  # noqa: E731
    out = {
        '자치단체': rows[0].get('laf_hg_nm') or '',
        'laf_cd': code,
        '연도': month[:4],
        '기준': month,
        '받은날': date.today().isoformat(),
        '사업수': len(사업),
        '예산현액': 합(4), '지출': 합(5),
        '국비': 합(6), '시도비': 합(7), '시군구비': 합(8), '기타': 합(9),
        '열차례': 열차례,
        '이름표': 이름표,
        '사업': 사업,
    }

    os.makedirs(OUT, exist_ok=True)
    # 눌러서 담는다 — 243곳이면 36MB 가 12MB 로 준다. 화면이 받아서 푼다
    path = os.path.join(OUT, f'{code}.json.gz')
    tmp = path + '.tmp'
    with gzip.open(tmp, 'wt', encoding='utf-8', compresslevel=9) as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    os.replace(tmp, path)
    return out, os.path.getsize(path)


def 한곳(code, month, key):
    fyr = month[:4]
    try:
        rows, total = fetch('QWGJK', {'fyr': fyr, 'exe_ymd': month, 'laf_cd': code}, key)
    except SystemExit as e:
        print(f'  {code}: 자료 없음 — 건너뜀 ({e})')
        return False
    if not rows:
        print(f'  {code}: 0행 — 건너뜀')
        return False
    if len(rows) != total:
        print(f'  {code}: {len(rows)}/{total} 덜 받았다 — 저장 안 함')
        return False
    o, size = 굽기(code, rows, month)
    말하기(o, size)
    return True


def 말하기(o, size):
    rt = o['지출'] / o['예산현액'] * 100 if o['예산현액'] else 0
    print(f"  {o['자치단체']}({o['laf_cd']}) 사업 {o['사업수']:,}개 · "
          f"예산현액 {o['예산현액']/1e8:,.0f}억 · 지출 {o['지출']/1e8:,.0f}억({rt:.0f}%) · {size/1024:,.0f}KB")


def 전부(month, key):
    """전국을 한 번에 받아 자치단체별로 쪼갠다. laf_cd 를 빼면 243곳이 함께 온다."""
    print('전국 한 번에 받는다 — 46만 행쯤 된다. 8분쯤 걸린다')
    rows, total = fetch('QWGJK', {'fyr': month[:4], 'exe_ymd': month}, key)
    if len(rows) != total:
        print(f'⚠ {len(rows):,}/{total:,} 덜 받았다 — 저장 안 함')
        return 0

    묶음 = {}
    for r in rows:
        묶음.setdefault(r['laf_cd'], []).append(r)
    print(f'{len(rows):,}행 → {len(묶음)}곳')

    총크기 = 0
    for code in sorted(묶음):
        o, size = 굽기(code, 묶음[code], month)
        총크기 += size
    print(f'{len(묶음)}곳 · 모두 {총크기/1024/1024:,.1f}MB')
    return len(묶음)


def main():
    args = list(sys.argv[1:])
    month = None
    if '--month' in args:
        i = args.index('--month')
        month = args[i + 1]
        del args[i:i + 2]
    모두 = '--all' in args
    if 모두:
        args.remove('--all')
    codes = args or ['2600000', '4373000', '4612000']
    if not month:
        t = date.today()
        month = f'{t.year}{t.month:02d}'

    key = load_key()
    if not key:
        raise SystemExit('LOFIN_KEY 가 없다. 키 없이는 한 쪽에 5행뿐이라 못 쓴다')
    print(f'진행 중인 사업 {month} · 인증키 있음')

    if 모두:
        return 0 if 전부(month, key) else 1

    ok = sum(1 for cd in codes if 한곳(cd, month, key))
    print(f'{ok}/{len(codes)} 곳 구움 → site/data/ongoing/')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
