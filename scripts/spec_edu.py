# 지방교육재정알리미 638종을 **포털 화면의 나무 모양 그대로** 표로 굽는다.
#
#   python scripts/spec_edu.py            표만 굽는다 (호출 0회)
#   python scripts/spec_edu.py --맛보기    마디마다 한 번씩 실제로 불러 본 값을 붙인다
#
#   → docs/교육재정알리미_638종.xlsx
#
# 왜 — 17개 시·도교육청은 243개 자치단체와 **축이 다르다.** 따로 정리해야 한다
#      (2026-09-22 사용자). 먼저 「어떻게 나오는지」가 보여야 고를 수 있다.
#
# ⭐ **638종은 겉보기만 많다.** 622종이 `회계연도 · 지역구분 · 항목구분 · 금액(원)`
#    **넉 줄짜리 같은 표**다. 사업 이름만 다르다. 219개 이름은 예산·결산 양쪽에 똑같이 있다.
#
# ⭐⭐ **나무 구조가 `dsId` 에 들어 있다** — `VW_CLSG01020103` =
#    `결산(CLSG)` + `대분류01` + `중분류02` + `소분류01` + `순번03`.
#    2026-09-22 에 포털 화면(결산통합공시)과 맞춰 보니 **순서까지 똑같았다** —
#    화면의 「세입 > 총괄·이전수입·자체수입·차입 및 기타·내부거래」가 `CLSG-01-02` 다섯 종이다.
#
# ⚠️ **다만 API 는 「분류 이름」을 안 준다.** `재정규모`·`세입`·`사업별 세출` 같은 이름은
#    포털 화면에만 있다. 그래서 이 표의 「분류 이름」 칸은 두 가지가 섞여 있다 —
#    **포털에서 확인한 것**과 **내가 자식들을 보고 붙인 것(확인 필요)**. 칸으로 갈라 뒀다.
#    ⛔ 확인 안 된 이름을 확인된 것처럼 쓰지 말 것.
#
# ⚠️ **포털 나무와 dsId 나무가 한 군데 어긋난다.** 화면의 결산 「통합재정」은 넷인데
#    (총계·순계·통합재정통계·지역통합재정통계) dsId 로는 셋이고, `지역통합재정통계` 만
#    `CLSG-02` 밑에 따로 있다. 예산 쪽(`BUDG-02-01`)은 넷이 다 한 자리에 있다.

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

import keys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 'http://openapi.eduinfo.go.kr/openApi.do'   # ⚠️ HTTPS 가 안 열린다
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')

# ── 분류 이름 ──────────────────────────────────────────────────────────────
# '포털' = 포털 화면에서 눈으로 확인한 것. '추정' = 자식 이름을 보고 내가 붙인 것.
# ⛔ 추정을 포털로 옮기려면 **포털 화면에서 확인하고 나서** 옮길 것.
대분류 = {
    ('CLSG', '01'): ('재정규모', '포털'),
    ('CLSG', '02'): ('재정운영 상황', '추정'),
    ('CLSG', '03'): ('주요 사업·재산', '추정'),
    ('CLSG', '04'): ('재무제표와 재정분석', '추정'),
    ('BUDG', '01'): ('계획서·성과', '추정'),
    ('BUDG', '02'): ('재정규모', '추정'),
    ('BUDG', '03'): ('재정지표', '추정'),
}
중분류 = {
    ('CLSG', '01', '01'): ('통합재정', '포털'),
    ('CLSG', '01', '02'): ('세입', '포털'),
    ('CLSG', '01', '03'): ('사업별 세출', '포털'),
    ('CLSG', '01', '04'): ('성질별 세출', '추정'),
    ('CLSG', '01', '05'): ('이월액 및 집행잔액', '추정'),
    ('CLSG', '01', '07'): ('기금', '추정'),
    ('CLSG', '01', '08'): ('사업별 세출 (다른 갈래)', '추정'),
    ('BUDG', '02', '01'): ('통합재정', '추정'),
    ('BUDG', '02', '02'): ('세입', '추정'),
    ('BUDG', '02', '03'): ('사업별 세출', '추정'),
    ('BUDG', '02', '04'): ('성질별 세출', '추정'),
    ('BUDG', '02', '08'): ('사업별 세출 (다른 갈래)', '추정'),
}

# 맛보기로 불러 볼 것 — 마디마다 대표 하나씩
맛보기 = [
    ('예산 총괄', 'opbdSummr'),
    ('결산 총괄', 'opclSummr'),
    ('세출 총괄(예산)', 'opbdSpendTot'),
    ('세출 총괄(결산)', 'opclSpendTot'),
    ('지방채무 총괄', 'opclDebt'),
    ('이월액 및 집행잔액', 'opclFwardBal'),
    ('집행내역', 'opclClsgExecList'),
    ('예산 집행비율', 'opclBudgExecRate'),
]


def 쪼갬(ds):
    m = re.match(r'VW_(CLSG|BUDG)(\d{2})(\d{2})(\d{2})(\d{2})', ds or '')
    return m.groups() if m else None


def 부르기(서비스, 해='2025', 개수=3):
    키 = keys.키읽기('EDU_ALIMI_KEY')
    q = {'requestType': 서비스, 'key': 키, 'type': 'json',
         'pIndex': 1, 'pSize': 개수, 'FSCL_Y': 해}
    req = urllib.request.Request(BASE + '?' + urllib.parse.urlencode(q),
                                 headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        본문 = r.read().decode('utf-8', 'replace').replace(키, '<키>')
    return json.loads(본문)


머리칠 = PatternFill('solid', fgColor='DDE6F0')


def 판(wb, 이름, 머리, 줄들, 너비):
    ws = wb.create_sheet(이름)
    ws.append(머리)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = 머리칠
    for 줄 in 줄들:
        ws.append(list(줄))
    for i, w in enumerate(너비, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    ws.freeze_panes = 'A2'
    for 행 in ws.iter_rows(min_row=2):
        for c in 행:
            c.alignment = Alignment(vertical='top', wrap_text=True)
    return ws


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--맛보기', action='store_true')
    args = ap.parse_args()

    자료 = json.load(open(os.path.join(ROOT, 'data', 'eduinfo_catalog.json'),
                        encoding='utf-8'))

    # ── 638종 전수 ──────────────────────────────────────────────────────
    전수 = []
    나무 = {}
    for r in 자료:
        g = 쪼갬(r.get('dsId'))
        갈래 = {'CLSG': '결산', 'BUDG': '예산'}.get(g[0], '') if g else ''
        대, 대출처 = 대분류.get((g[0], g[1]), ('(이름 미확인)', '')) if g else ('', '')
        중, 중출처 = 중분류.get((g[0], g[1], g[2]), ('(이름 미확인)', '')) if g else ('', '')
        전수.append((
            갈래 or '그밖', 대, 대출처, 중, 중출처,
            f'{g[3]}-{g[4]}' if g else '',
            r.get('name') or '', r.get('service') or '(없음)',
            r.get('dsId') or '(없음)',
            ' + '.join(r.get('args') or []),
            ' · '.join(r.get('cols') or []),
        ))
        if g:
            나무.setdefault((갈래, g[1], g[2]), []).append(r.get('name') or '')
    전수.sort(key=lambda x: (x[0], x[8]))

    판(wb := openpyxl.Workbook(), '_', ['x'], [], [5])
    wb.remove(wb['_'])
    wb.remove(wb.active) if wb.sheetnames and wb.active.title == 'Sheet' else None

    판(wb, '전수 638종',
       ['갈래', '대분류', '대분류 출처', '중분류', '중분류 출처', '소분류-순번',
        '자료 이름', '서비스명(호출에 쓰는 것)', 'dsId', '요청인자', '나오는 칸'],
       전수, [6, 18, 10, 20, 10, 12, 26, 24, 20, 22, 40])

    # ── 나무 ────────────────────────────────────────────────────────────
    가지 = []
    for (갈래, 대, 중), 이름들 in sorted(나무.items()):
        대이름, 대출처 = 대분류.get(({'결산': 'CLSG', '예산': 'BUDG'}[갈래], 대),
                               ('(이름 미확인)', ''))
        중이름, 중출처 = 중분류.get(({'결산': 'CLSG', '예산': 'BUDG'}[갈래], 대, 중),
                               ('(이름 미확인)', ''))
        가지.append((갈래, f'{대}', 대이름, 대출처, f'{중}', 중이름, 중출처,
                    len(이름들), ', '.join(이름들[:8]) +
                    (f' … (모두 {len(이름들)}종)' if len(이름들) > 8 else '')))
    판(wb, '나무',
       ['갈래', '대', '대분류 이름', '출처', '중', '중분류 이름', '출처',
        '자료 수', '들어 있는 것'],
       가지, [6, 5, 20, 8, 5, 22, 8, 8, 78])

    # ── 한계와 함정 ─────────────────────────────────────────────────────
    판(wb, '알아둘 것', ['무엇', '내용'], [
        ('규모', '638종 = 결산 326 + 예산 296 + 그밖 16'),
        ('겉보기만 많다',
         '622종이 「회계연도 · 지역구분 · 항목구분 · 금액(원)」 넉 줄짜리 같은 표다. '
         '사업 이름만 다르다. 219개 이름은 예산·결산 양쪽에 똑같이 있다'),
        ('축', '17개 시·도교육청. 243개 자치단체와 축이 달라 같은 표에 못 섞는다'),
        ('요청인자', '거의 다 「회계연도 + 지역구분」. 자치단체 코드가 아니라 시·도 이름이다'),
        ('응답 모양', 'TOTAL_CNT · RESULT · RESULT_LIST. 한 줄은 '
                   'IDX · YMQ(연도) · ITEM_CD1(지역) · ITEM_CD2(항목) · AMT(금액) · ITEM_CD1_SEQ'),
        ('⚠️ 항목이 들여쓰기로 계층을 표시한다',
         'ITEM_CD2 가 「세입예산액」 / 「        이전수입」처럼 **앞 빈칸으로 단을 나눈다.** '
         '빈칸을 지우면 합계와 항목이 섞여 이중 계산된다'),
        ('⚠️ 빈 서비스', '16종은 서비스명이 아예 없다(예산서·결산서·성과보고서 따위 문서류). '
                    'API 로 못 받는다'),
        ('⚠️ 빈 응답', 'opclClsgExecList(집행내역)·opclBudgExecRate 는 FSCL_Y=2025 로 '
                   '0건이 온다. 해를 바꿔 다시 볼 것'),
        ('⚠️ HTTPS 안 됨', 'openapi.eduinfo.go.kr 은 http 로만 열린다'),
        ('나무가 한 군데 어긋난다',
         '포털 화면의 결산 「통합재정」은 넷인데(총계·순계·통합재정통계·지역통합재정통계) '
         'dsId 로는 셋이고 지역통합재정통계만 CLSG-02 밑에 따로 있다. 예산 쪽은 넷이 한자리다'),
        ('분류 이름', 'API 가 안 준다. 이 표의 이름은 「포털」(확인함)과 「추정」(내가 붙임)이 '
                  '섞여 있다 — 출처 칸을 볼 것'),
    ], [22, 96])

    # ── 맛보기 ──────────────────────────────────────────────────────────
    if args.맛보기:
        줄들 = []
        for 이름, 서비스 in 맛보기:
            try:
                d = 부르기(서비스)
                L = d.get('RESULT_LIST') or []
                보기 = ' | '.join(
                    f'{r.get("ITEM_CD1")} {str(r.get("ITEM_CD2")).strip()} '
                    f'{int(r.get("AMT") or 0):,}' for r in L[:2]) or '(빈 응답)'
                줄들.append((이름, 서비스, d.get('TOTAL_CNT'),
                           ' · '.join(L[0].keys()) if L else '', 보기))
            except Exception as e:
                줄들.append((이름, 서비스, '✗', '', f'{type(e).__name__}: {e}'))
            time.sleep(0.3)
        판(wb, '맛보기', ['무엇', '서비스명', '건수(2025)', '나온 칸', '앞 두 줄'],
           줄들, [20, 24, 12, 44, 70])

    나갈곳 = os.path.join(ROOT, 'docs', '교육재정알리미_638종.xlsx')
    os.makedirs(os.path.dirname(나갈곳), exist_ok=True)
    wb.save(나갈곳)
    확인 = sum(1 for _, ㅅ in 대분류.values() if ㅅ == '포털') + \
        sum(1 for _, ㅅ in 중분류.values() if ㅅ == '포털')
    print(f'구웠다 — {나갈곳}')
    print(f'  전수 {len(전수)}종 · 나무 가지 {len(가지)}개 · '
          f'분류 이름 {len(대분류) + len(중분류)}개 중 포털에서 확인한 것 {확인}개')


if __name__ == '__main__':
    main()
