# 지방재정365 146종의 공식 명세(요청인자·출력 항목)를 받아 적는다.
#
#   python scripts/spec_lofin.py
#
# 사이트가 SPA 라 OpenAPI 명세는 화면 조각으로만 온다. pdtaId 를 폼으로 POST 하면
# 그 조각이 통째로 돌아오고, 거기 요청인자 표와 출력값 표가 들어 있다.
# 출력 항목은 한글 이름이 붙어 있어서, 이것 없이는 필드 뜻을 알 수 없다.
#
# data/lofin365_146.json 에 다음 칸을 덧붙인다.
#   req    : [{id, type, need(필수/선택), desc}]  검색 요청인자
#   fields : [{id, nm, desc}]                    출력값

import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = 'https://www.lofin365.go.kr/lf/pfinDtaOpen/dtst/dtstSvi/retvDtstDtsApi.do'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')


def fetch(pdta_id, tries=3):
    body = urllib.parse.urlencode({'pdtaId': pdta_id}).encode()
    req = urllib.request.Request(SPEC, data=body, headers={
        'User-Agent': UA,
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'https://www.lofin365.go.kr/',
        'Content-Type': 'application/x-www-form-urlencoded',
    })
    for n in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode('utf-8')
        except Exception:
            if n == tries - 1:
                return ''
            time.sleep(2 * (n + 1))
    return ''


def cell_text(td):
    t = re.sub(r'<[^>]+>', ' ', td)
    return re.sub(r'\s+', ' ', html.unescape(t)).strip()


def table_rows(page, caption):
    """<caption>이 caption 인 표의 tbody 행들을 셀 목록으로 돌려준다."""
    m = re.search(r'<table>\s*<caption>' + re.escape(caption) + r'</caption>(.*?)</table>',
                  page, re.S)
    if not m:
        return []
    body = re.search(r'<tbody>(.*?)</tbody>', m.group(1), re.S)
    if not body:
        return []
    out = []
    for tr in re.findall(r'<tr>(.*?)</tr>', body.group(1), re.S):
        tds = [cell_text(td) for td in re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)]
        if tds:
            out.append(tds)
    return out


def parse(page):
    req = []
    for tds in table_rows(page, '검색 요청인자'):
        if len(tds) < 3:
            continue
        typ = tds[1]
        need = '필수' if '필수' in typ else ('선택' if '선택' in typ else '')
        req.append({
            'id': tds[0],
            'type': typ.replace('(필수)', '').replace('(선택)', '').strip(),
            'need': need,
            'desc': tds[2],
        })
    fields = []
    for tds in table_rows(page, '출력값'):
        if len(tds) < 3:
            continue
        fields.append({'id': tds[1], 'nm': tds[2], 'desc': tds[3] if len(tds) > 3 else ''})
    return req, fields


def main():
    path = os.path.join(ROOT, 'data', 'lofin365_146.json')
    rows = json.load(open(path, encoding='utf-8'))

    miss = 0
    for n, r in enumerate(rows, 1):
        page = fetch(r['pdtaId'])
        req, fields = parse(page)
        r['req'] = req
        r['fields'] = fields
        need = [q['id'] for q in req if q['need'] == '필수']
        if not fields:
            miss += 1
        print(f"{n:3}/{len(rows)} {r['code']:8} 인자 {len(req):2} (필수 {','.join(need) or '없음'})"
              f" · 출력 {len(fields):2}필드  {r['name'][:24]}")
        time.sleep(0.15)

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f'\n명세 못 받은 것 {miss}종')


if __name__ == '__main__':
    main()
