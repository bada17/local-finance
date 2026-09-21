# data/lofin365_146.json 을 읽어 docs/지방재정365_API코드_146종.xlsx 를 다시 굽는다.
#
#   python scripts/build_map.py
#
# 시트 셋으로 만든다.
#   데이터 지도 — 146종을 한 줄씩. 되는지·필수인자·보유연도·건수·필드수
#   출력 필드  — 어느 서비스에 무슨 값이 들어 있는지 (한글 항목명)
#   읽는 법    — 칸 뜻과 구운 날짜
#
# 손으로 고치지 말 것. 다시 구우면 덮어쓴다.

import json
import os
import re
import sys
from datetime import date

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'docs', '지방재정365_API코드_146종.xlsx')

HEAD_FILL = PatternFill('solid', fgColor='2F5496')
HEAD_FONT = Font(color='FFFFFF', bold=True)


def axis(r):
    """갱신 축 — 날짜 인자를 받으면 일별, 아니면 연 단위."""
    need = [q['id'] for q in r.get('req', []) if q['need'] == '필수']
    if any(p.endswith('ymd') for p in need):
        return '일별'
    return '연'


def last_year(r):
    """보유연도의 끝 해."""
    found = re.findall(r'(\d{4})', r.get('years') or '')
    return int(found[-1]) if found else 0


def alive(r, this_year):
    """지속가능성 — 자료가 계속 올라오는가. 보유연도 끝 해로 판정한다.

    결산·공시 자료는 원래 두 해 늦게 나온다(2026년에 2024 결산이 최신).
    그러니 끝 해가 재작년이어도 살아 있는 것이고, 그보다 옛날이면 끊긴 것이다.
    """
    y = last_year(r)
    if not y:
        return '?'
    if y >= this_year:
        return '살아있음(올해)'
    if y >= this_year - 1:
        return '살아있음(작년)'
    if y >= this_year - 2:
        return '살아있음(결산주기)'
    return f'멈춤({y})'


def scope(r):
    """건수로 본 단위."""
    t = r.get('total') or 0
    if t == 243:
        return '자치단체 전수(243)'
    if t == 0:
        return '-'
    if t < 300:
        return f'자치단체 단위({t})'
    return '사업·항목 단위'


def sheet_map(wb, rows):
    ws = wb.create_sheet('데이터 지도')
    cols = ['번호', '분류', '서비스코드', '데이터명', '상태', '지속', '갱신 축', '보유연도',
            '끝 해', '필수인자', '선택인자', '건수(시험 호출)', '단위', '필드수', '요청주소']
    ws.append(cols)
    this_year = date.today().year
    for n, r in enumerate(rows, 1):
        need = [q['id'] for q in r.get('req', []) if q['need'] == '필수']
        opt = [q['id'] for q in r.get('req', []) if q['need'] == '선택']
        ws.append([
            n,
            r.get('cat', ''),
            r['code'],
            r['name'],
            r.get('stat', ''),
            alive(r, this_year),
            axis(r),
            r.get('years', ''),
            last_year(r),
            ', '.join(need) or '없음',
            ', '.join(opt) or '없음',
            r.get('total') or 0,
            scope(r),
            len(r.get('fields') or []),
            'https://www.lofin365.go.kr/lf/hub/' + r['code'],
        ])
    widths = [5, 16, 10, 46, 7, 11, 8, 16, 7, 20, 30, 14, 18, 7, 46]
    finish(ws, widths)
    return ws


def sheet_fields(wb, rows):
    ws = wb.create_sheet('출력 필드')
    ws.append(['서비스코드', '데이터명', '분류', '항목 ID', '항목명', '설명'])
    for r in rows:
        # 카탈로그의 name 은 이름과 설명이 붙어 있어 기계적으로 못 가른다. 앞쪽만 보인다
        short = r['name'][:24]
        for f in r.get('fields') or []:
            ws.append([r['code'], short, r.get('cat', ''), f['id'], f['nm'], f.get('desc', '')])
    finish(ws, [10, 24, 16, 20, 24, 40])
    return ws


def sheet_legend(wb, rows):
    ws = wb.create_sheet('읽는 법')
    opened = sum(1 for r in rows if r.get('stat') == '열림')
    daily = sum(1 for r in rows if axis(r) == '일별')
    live = sum(1 for r in rows if not alive(r, date.today().year).startswith('멈춤'))
    ws.append(['칸', '뜻'])
    for a, b in [
        ('상태', '열림 = 실제로 호출해서 행을 받아봤음 / 자료없음 = 응답은 정상인데 행이 0'),
        ('지속', '자료가 계속 올라오는가. 보유연도 끝 해로 본다. 결산·공시는 원래 두 해 늦게 나오므로'
                ' 끝 해가 재작년이면 정상이다(2026년에 2024 결산이 최신). 「멈춤」은 그보다 옛날에 끊긴 것 —'
                ' 시계열로는 몰라도 「지금 이 자치단체가 어떤가」에는 못 쓴다'),
        ('갱신 축', '일별 = 날짜 인자를 받는 것(매일 도는 축) / 연 = 회계연도 단위'),
        ('필수인자', '이것을 안 넣으면 ERROR-300. 값은 fyr=연도, *_ymd=YYYYMMDD, laf_cd=자치단체 7자리'),
        ('건수(시험 호출)', '보유연도 끝 해로 한 번 불러봤을 때의 전체 건수. 해마다 다르다'),
        ('단위', '243이면 자치단체 전수. 그보다 크면 사업·항목까지 쪼개진 자료'),
        ('필드수', '출력 항목 수. 항목별 한글 이름은 「출력 필드」 시트에'),
        ('', ''),
        ('인증키', '없어도 호출된다. 다만 한 쪽에 5행 고정이라 전수 수집은 키가 있어야 한다'),
        ('굽는 법', 'python scripts/build_map.py — 손으로 고치지 말 것'),
        ('', ''),
        ('구운 날', str(date.today())),
        ('종수', f'{len(rows)}종 중 {opened}종 열림 · 일별 축 {daily}종 · 계속 올라오는 것 {live}종'),
    ]:
        ws.append([a, b])
    finish(ws, [16, 96])
    return ws


def finish(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for c in ws[1]:
        c.fill = HEAD_FILL
        c.font = HEAD_FONT
        c.alignment = Alignment(vertical='center')
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions


def main():
    rows = json.load(open(os.path.join(ROOT, 'data', 'lofin365_146.json'), encoding='utf-8'))
    rows = sorted(rows, key=lambda r: (r.get('cat', ''), r['code']))

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    sheet_map(wb, rows)
    sheet_fields(wb, rows)
    sheet_legend(wb, rows)
    wb.save(OUT)

    fields = sum(len(r.get('fields') or []) for r in rows)
    print(f'구움: {os.path.relpath(OUT, ROOT)}')
    print(f'  데이터 지도 {len(rows)}줄 · 출력 필드 {fields}줄')


if __name__ == '__main__':
    main()
