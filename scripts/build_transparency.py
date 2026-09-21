# 「공시 점검」 화면을 굽는다 — site/transparency.html
#
#   python scripts/build_transparency.py
#
# 기준은 **지방재정법 제60조 제1항**이다(예산·결산 확정 뒤 2개월 안에 16가지를 주민에게 공시).
# 지표를 **세 켜**로 짠다 —
#   ① 있나        : 재정공시 주소를 냈나, 법 60조 항목이 그 페이지에 보이나
#   ② 닿을 수 있나 : 그 주소가 눌러서 열리나
#   ③ 쓸 수 있나   : 파일 이름이 뜻을 갖나 · 엑셀/CSV 로 냈나 · 기계가 읽을 수 있나(API 등재)
#
# ⚠️ **이 화면은 「공시했는가」가 아니라 「우리가 볼 수 있었는가」다.** 못 본 것을 없다고 적지 말 것.
#
# 두 번 봤고 **둘을 합친다** —
#   ① `data/disclosure.json`     urllib 로 원문 HTML (check_disclosure.py)
#   ② `data/disclosure_dom.json` 크롬으로 그려진 화면 (recheck_disclosure.js) ← **이쪽이 우선**
#      해시 이름 뒤에 숨은 **글자 이름**과 JS 로 그리는 목록이 여기서 잡힌다.
# 그밖 — `data/coverage.json`(146종 API 조사) · `site/data/loc/index.json`(이름·시도·갈래)
# 결과 — site/transparency.html

import collections
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

# 지방재정법 제60조 제1항이 시키는 것 ↔ 파일 이름에 나올 만한 말
항목 = [
    ('세입·세출예산 운용상황', ['세입세출', '세입·세출', '운용상황', '예산기준', '결산기준']),
    ('재무제표', ['재무제표', '재정상태표', '재정운영표']),
    ('채권관리 현황', ['채권']),
    ('기금운용 현황', ['기금']),
    ('공유재산 증감·현재액', ['공유재산']),
    ('지역통합재정통계', ['통합재정']),
    ('공기업·출자출연 경영정보', ['공기업', '출자', '출연']),
    ('중기지방재정계획', ['중기지방재정', '중기재정']),
    ('성인지 예산서·결산서', ['성인지']),
    ('예산편성기준별 운영상황', ['예산편성기준']),
    ('주민참여예산 운영·의견서', ['주민참여', '주민의견']),
    ('재정운용상황 개요서', ['개요서']),
    ('재정건전화계획', ['건전화']),
    ('재정건전성관리계획', ['건전성관리']),
    ('투자심사·지방채·민자·보증채무', ['투자심사', '지방채', '민간투자', '민자', '보증채무']),
    ('지방보조금', ['보조금']),
]
해시이름 = re.compile(r'^[0-9a-f]{8,}[._]', re.I)
엑셀 = {'.xlsx', '.xls', '.csv'}
문서 = {'.pdf', '.hwp', '.hwpx', '.doc', '.docx', '.zip', '.ppt', '.pptx'}
확장자찾기 = re.compile(r'\.(hwpx?|xlsx?|csv|pdf|docx?|pptx?|zip)(?=$|[?&#"\'\s])', re.I)
# 「첨부파일」·「바로보기」 같은 단추 글자는 이름이 아니다 — 뜻을 갖는 이름만 센다
껍데기 = re.compile(r'^(첨부|첨부파일|파일첨부|다운로드|내려받기|바로보기|미리보기|보기|열기|'
                    r'pdf파일첨부|한글파일첨부|붙임|다운|download|file)\s*\d*$', re.I)


def 까닭갈래(c):
    c = c or ''
    if 'HTTP Error' in c:
        return '주소가 죽었다'
    if 'SSL' in c or 'CERTIFICATE' in c.upper():
        return '인증서가 이상하다'
    if 'timed out' in c:
        return '너무 느리다'
    return '그밖'


def 뜻있는이름(s):
    """무슨 문서인지 이름만 보고 알 수 있나."""
    s = (s or '').strip()
    if not s or 해시이름.match(s) or 껍데기.match(s):
        return False
    한글 = len(re.findall(r'[가-힣]', s))
    return 한글 >= 3


def 확장들(글들):
    out = set()
    for g in 글들:
        for m in 확장자찾기.finditer(g or ''):
            out.add('.' + m.group(1).lower())
    return out


def main():
    dis = json.load(open(os.path.join(ROOT, 'data', 'disclosure.json'), encoding='utf-8'))
    cov = json.load(open(os.path.join(ROOT, 'data', 'coverage.json'), encoding='utf-8'))
    idx = json.load(open(os.path.join(SITE, 'data', 'loc', 'index.json'), encoding='utf-8'))
    메타 = {r['cd']: r for r in idx['곳']}

    dom = {}
    dom날 = ''
    p = os.path.join(ROOT, 'data', 'disclosure_dom.json')
    if os.path.exists(p):
        d = json.load(open(p, encoding='utf-8'))
        dom날 = d.get('만든날', '')
        dom = {r['laf_cd']: r for r in d['곳']}

    # ── ③의 기계 쪽 : 「모두가 내는 자료」에서 빠진 곳
    # ⚠️ 곳수가 적다고 미제출이 아니다. 광역만 내는 자료·그해 해당 없는 자료가 섞여 있으므로
    #    **거의 전부가 내는 자료**(기초 220곳 이상 / 광역 16곳 이상)만 잣대로 삼는다.
    광역 = {cd for cd in 메타 if cd.endswith('00000')}
    기초 = set(메타) - 광역
    빠진자료 = collections.defaultdict(list)
    기초잣대 = 광역잣대 = 0
    for code, v in cov['서비스'].items():
        낸곳 = set(v.get('곳', {}))
        이름 = v.get('이름', code)[:40]
        if len(낸곳 & 기초) >= 220:
            기초잣대 += 1
            for q in 기초 - 낸곳:
                빠진자료[q].append(이름)
        if len(낸곳 & 광역) >= 16:
            광역잣대 += 1
            for q in 광역 - 낸곳:
                빠진자료[q].append(이름)

    곳 = []
    for r in dis['곳']:
        cd = r['laf_cd']
        m = 메타.get(cd, {})
        d = dom.get(cd, {})

        옛파일 = r.get('파일', []) or []                       # urllib 이 본 것(해시 이름이 많다)
        새파일 = [f.get('이름', '') for f in d.get('파일', [])]  # 크롬이 본 것(글자 이름)
        새주소 = [f.get('주소', '') for f in d.get('파일', [])]

        옛열림 = r['상태'] == '열림'
        새열림 = bool(d.get('코드')) and d['코드'] < 400 and (d.get('글자수') or 0) > 120
        열림 = 옛열림 or 새열림

        # 어느 쪽이 보여 줬나 — 화면에 그대로 적는다
        if 새파일 and not [f for f in 옛파일 if 뜻있는이름(f)]:
            본법 = '크롬'
        elif 옛파일:
            본법 = '원문'
        else:
            본법 = ''

        이름들 = [f for f in 새파일 + 옛파일 if f]
        읽힌 = [f for f in 이름들 if 뜻있는이름(f)]
        확장 = 확장들(이름들 + 새주소) | {os.path.splitext(f)[1].lower() for f in 옛파일}

        if not 열림:
            형식 = '못 봄'
        elif 확장 & 엑셀:
            형식 = '엑셀 있음'
        elif 확장 & 문서:
            형식 = '문서뿐'
        else:
            형식 = '못 봄'

        걸린항목 = []
        if 읽힌:
            글 = ' '.join(읽힌)
            걸린항목 = [i for i, (_, 말들) in enumerate(항목) if any(w in 글 for w in 말들)]

        보일것 = (읽힌 or 이름들)[:12]
        곳.append({
            'cd': cd,
            '이름': r['이름'],
            '시도': m.get('시도', ''),
            '갈래': m.get('갈래', '광역' if cd in 광역 else '기초'),
            '주소': r['주소'],
            '링크': '열림' if 열림 else '안 열림',
            '까닭': '' if 열림 else 까닭갈래(r.get('까닭')),
            '크롬만': bool(새열림 and not 옛열림),     # 파이썬은 튕겼는데 크롬은 열린 곳
            '제목': ((d.get('제목') or r.get('제목') or '')
                   .replace('&lt;', '<').replace('&gt;', '>')[:60]),
            '파일수': len(이름들),
            '읽힌수': len(읽힌),
            '본법': 본법,
            '올린날': d.get('날짜', ''),
            '형식': 형식,
            '항목': 걸린항목,
            '파일': [f[:48] for f in 보일것],
            '더': max(0, len(이름들) - len(보일것)),
            'API빠짐': 빠진자료.get(cd, [])[:6],
            'API빠짐수': len(빠진자료.get(cd, [])),
        })
    곳.sort(key=lambda x: (x['갈래'] != '광역', x['시도'], x['이름']))

    요약 = {
        '모두': len(곳),
        '주소냄': sum(1 for x in 곳 if x['주소']),
        '열림': sum(1 for x in 곳 if x['링크'] == '열림'),
        '파일잡힘': sum(1 for x in 곳 if x['파일수']),
        '이름읽힘': sum(1 for x in 곳 if x['읽힌수']),
        '엑셀': sum(1 for x in 곳 if x['형식'] == '엑셀 있음'),
        '문서뿐': sum(1 for x in 곳 if x['형식'] == '문서뿐'),
        '파일못봄': sum(1 for x in 곳 if x['링크'] == '열림' and not x['파일수']),
        '해시': sum(1 for x in 곳 if x['파일수'] and not x['읽힌수']),
        '크롬이살림': sum(1 for x in 곳 if x['본법'] == '크롬'),
        '크롬만열림': sum(1 for x in 곳 if x['크롬만']),
        '올린날앎': sum(1 for x in 곳 if x['올린날']),
        '까닭': dict(collections.Counter(x['까닭'] for x in 곳 if x['까닭'])),
        'API빠진곳': sum(1 for x in 곳 if x['API빠짐수']),
        'API잣대기초': 기초잣대,
        'API잣대광역': 광역잣대,
        '만든날': dis.get('만든날', ''),
        '크롬날': dom날,
    }

    tpl = open(os.path.join(SITE, 'transparency.template.html'), encoding='utf-8').read()
    out = (tpl
           .replace('__ROWS__', json.dumps(곳, ensure_ascii=False, separators=(',', ':')))
           .replace('__SUM__', json.dumps(요약, ensure_ascii=False, separators=(',', ':')))
           .replace('__ITEMS__', json.dumps([n for n, _ in 항목], ensure_ascii=False,
                                            separators=(',', ':'))))
    path = os.path.join(SITE, 'transparency.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(out)
    print(f'구움: site/transparency.html ({os.path.getsize(path)/1024:,.0f} KB) · {len(곳)}곳')
    for k, v in 요약.items():
        print(f'   {k:<10} {v}')


if __name__ == '__main__':
    main()
