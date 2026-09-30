# 「중앙투자심사」 화면을 굽는다 — site/review.html
#
#   python scripts/fetch_review.py && python scripts/build_review_page.py
#
# 전국 목록 한 판이다(2026-09-30 사용자 결정 — 자치단체별 판이 아니라 맨 위 메뉴로).
# 곳마다 몇 건 안 돼 곳별 판으로는 비어 보이고, 이 자료의 힘은 「반려 몇 건」 같은 전국 숫자에 있다.
# 자치단체별 화면에서는 `review.html#전남(여수시)` 링크로 이 판의 그 곳 줄만 연다.

import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, 'site')


# 원문 오타 — 자치단체별 화면의 링크(「전남(여수시)」)가 걸리게 맞춘다. 경자청·음성군진천군은 곳이 아니라 그대로 둔다.
고침 = {'강원(횡성시)': '강원(횡성군)', '경기(앙평군)': '경기(양평군)', '경남(도본청)': '경남(본청)',
        '경북(경산)': '경북(경산시)', '전남(여수)': '전남(여수시)'}


def 회차(파일, 글):
    """「2024-3차」·「2023-수시2차」 — 2023 수시는 zip 하나에 세 회차라 글보다 파일 이름이 정확하다."""
    s = re.sub(r'\s+', '', 파일 + ' ' + 글)
    해 = re.search(r'(20\d\d)', s)
    차 = re.search(r'(수시)?제?(\d)차', s)
    if not 해:
        return 글
    return 해[1] + '-' + ((차[1] or '') + 차[2] + '차' if 차 else '수시' if '수시' in s else '')


def main():
    d = json.load(open(os.path.join(ROOT, 'data', 'review.json'), encoding='utf-8'))
    rows = []
    for x in d['사업']:
        돈 = x['사업비(억원)']
        m = re.match(r'\s*([\d,]+)', 돈)
        rows.append([x['올린날'], 회차(x['파일'], x['글']), 고침.get(곳 := re.sub(r'\s+', '', x['광역명(시군명)']), 곳),
                     x['사업명'], x['사업기간'].replace(' ', ''), x['사업량'],
                     int(m[1].replace(',', '')) if m else None, 돈, x['심사결과']])
    rows.sort(key=lambda r: r[0], reverse=True)

    tpl = open(os.path.join(SITE, 'review.template.html'), encoding='utf-8').read()
    out = (tpl.replace('__ROWS__', json.dumps(rows, ensure_ascii=False, separators=(',', ':')))
              .replace('__FROM__', d['부터']))
    path = os.path.join(SITE, 'review.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(out)
    print(f'구움: site/review.html ({os.path.getsize(path)/1024:,.0f} KB) · {len(rows)}줄')


if __name__ == '__main__':
    main()
