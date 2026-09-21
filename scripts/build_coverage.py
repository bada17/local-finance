# 「무엇이 있고 무엇이 없나」를 센다 — 투명성 지표의 절반이 이것이다.
#
#   python scripts/build_coverage.py                 146종을 차례로 눌러 본다
#   python scripts/build_coverage.py --limit 30      30종만 (조금씩 채우기)
#
# 지방재정365의 146종을 **자치단체별로 몇 행 있는지** 세어 둔다. 그러면
#   · 어느 자치단체가 어느 자료를 안 냈는지
#   · 어느 자료가 몇 해에서 멈췄는지
# 를 243곳 전수로 말할 수 있다. **다른 어느 사이트도 이걸 안 보여준다.**
#
# ⚠️ 미공개는 세 가지를 다 친다(2026-09-21 결정) —
#    ① 아예 안 올린 것 ② 링크가 깨진 것 ③ 몇 해 밀린 것.
#    이 스크립트는 ①과 ③을 센다. ②(원문 링크)는 따로 봐야 한다.
#
# 결과: data/coverage.json — 한 번 만들면 화면 쪽에서 여러 가지로 쓸 수 있다.

import json
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lofin import fetch, load_key  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'coverage.json')
큰것 = 20000          # 이보다 큰 자료는 건너뛴다(일별 축 넷 따위)


def 해들(years):
    """'2015~2026' → [2026, 2025, 2024] (최신부터 세 해만 눌러 본다)"""
    try:
        끝 = int(str(years).split('~')[-1].strip()[:4])
    except Exception:
        return []
    return [str(끝 - i) for i in range(3)]


def main():
    limit = None
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])

    catalog = json.load(open(os.path.join(ROOT, 'data', 'lofin365_146.json'), encoding='utf-8'))
    have = {}
    if os.path.exists(OUT):
        have = json.load(open(OUT, encoding='utf-8')).get('서비스', {})

    key = load_key()
    if not key:
        raise SystemExit('LOFIN_KEY 가 없다')

    새로 = 0
    시각 = time.time()
    for it in catalog:
        code = it['code']
        if code in have:
            continue
        필수 = [r['id'] for r in it.get('req', []) if r.get('need') == '필수']
        낯선필수 = [x for x in 필수 if x != 'fyr']
        if 낯선필수:
            have[code] = {'이름': it['name'][:40], '건너뜀': '날짜·코드가 필요함(' + ','.join(낯선필수) + ')'}
            continue
        if (it.get('total') or 0) > 큰것:
            have[code] = {'이름': it['name'][:40], '건너뜀': f"너무 큼({it['total']:,}행)"}
            continue

        찾음 = None
        for yr in 해들(it.get('years')):
            args = {'fyr': yr} if 필수 or 'fyr' in [r['id'] for r in it.get('req', [])] else {}
            try:
                rows, total = fetch(code, args, key)
            except SystemExit:
                continue
            if rows:
                찾음 = (yr, rows, total)
                break
        if not 찾음:
            have[code] = {'이름': it['name'][:40], '건너뜀': '세 해를 눌러도 빈 응답'}
        else:
            yr, rows, total = 찾음
            # ⚠️ 자치단체 코드가 없는 자료가 있다 — 시도(wa_laf_cd)로만 오거나
            #    아예 지역 구분이 없는 것(세목별 따위). 「안 냈다」와 헷갈리면 안 된다
            곳 = {}
            단위 = '없음'
            for r in rows:
                cd = r.get('laf_cd')
                if cd:
                    단위 = '자치단체'
                    곳[cd] = 곳.get(cd, 0) + 1
            if not 곳:
                for r in rows:
                    cd = r.get('wa_laf_cd')
                    if cd:
                        단위 = '시도'
                        곳[cd] = 곳.get(cd, 0) + 1
            have[code] = {'이름': it['name'][:40], '연도': yr, '행': len(rows),
                          '단위': 단위, '곳수': len(곳), '곳': 곳}
        새로 += 1
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump({'만든날': time.strftime('%Y-%m-%d'), '서비스': have}, f,
                      ensure_ascii=False, separators=(',', ':'))
        if 새로 % 10 == 0:
            print(f'  {새로}종 · {(time.time()-시각)/60:.0f}분')
        if limit and 새로 >= limit:
            print(f'  {limit}종 채웠다. 다시 부르면 그다음부터 간다')
            break

    센것 = [v for v in have.values() if '곳수' in v]
    print(f'모두 {len(have)}/146종 · 센 것 {len(센것)}종 · 이번에 {새로}종 · '
          f'{(time.time()-시각)/60:.0f}분')


if __name__ == '__main__':
    main()
