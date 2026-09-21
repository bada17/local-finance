# 「무슨 자료가 있나」 화면을 굽는다 — site/catalog.html
#
#   python scripts/build_catalog_page.py
#
# 지방재정365 146종을 **검색해 볼 수 있게** 한 판에 늘어놓는다.
# "재정자립도 자료가 있나" 같은 물음에 바로 답하기 위한 화면이다.
#
# 쓰는 것 — data/lofin365_146.json(이름·분류·연도·필수인자) + data/coverage.json(최신연도·단위·곳수)

import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, 'site')


def main():
    cat = json.load(open(os.path.join(ROOT, 'data', 'lofin365_146.json'), encoding='utf-8'))
    cov, 잰날 = {}, ''
    p = os.path.join(ROOT, 'data', 'coverage.json')
    if os.path.exists(p):
        c = json.load(open(p, encoding='utf-8'))
        cov, 잰날 = c['서비스'], c.get('만든날', '')

    rows = []
    for it in cat:
        c = cov.get(it['code'], {})
        # ⚠️ 이름과 설명이 한 칸에 붙어 온다. 띄어쓰기로 자르면 「기관운영 업무추진비」가
        #    「기관운영」으로 잘린다 — 자르지 말고 통째로 보여준다
        이름 = it['name']
        필수 = [r['id'] for r in it.get('req', []) if r.get('need') == '필수']
        rows.append({
            'cd': it['code'], '이름': 이름[:110], '갈래': it['cat'],
            '해': it['years'], '최신': c.get('연도', ''), '단위': c.get('단위', ''),
            '곳수': c.get('곳수', None), '행': it.get('total'),
            '필수': ' '.join(필수), '막힘': c.get('건너뜀', ''),
        })
    rows.sort(key=lambda r: (r['갈래'], r['이름']))

    tpl = open(os.path.join(SITE, 'catalog.template.html'), encoding='utf-8').read()
    # ⚠️ 날짜·해를 화면에 박지 말 것 — 자료에서 꺼내 넣는다
    out = (tpl.replace('__ROWS__', json.dumps(rows, ensure_ascii=False, separators=(',', ':')))
              .replace('__ASOF__', 잰날))
    path = os.path.join(SITE, 'catalog.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(out)
    print(f'구움: site/catalog.html ({os.path.getsize(path)/1024:,.0f} KB) · {len(rows)}종')


if __name__ == '__main__':
    main()
