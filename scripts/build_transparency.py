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
# ⚠️ **이 화면은 「공시했는가」가 아니라 「자동 점검이 볼 수 있었는가」다.**
#    해시 이름·자바스크립트 목록·SSL 때문에 못 본 곳이 많다. 「없다」고 단정하지 말 것.
#
# 쓰는 것 — data/disclosure.json(243곳 링크 실측) + data/coverage.json(146종 API 조사)
#          + site/data/loc/index.json(이름·시도·갈래·인구)
# 결과   — site/transparency.html

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
문서 = {'.pdf', '.hwp', '.hwpx', '.doc', '.docx', '.zip'}


def 까닭갈래(c):
    c = c or ''
    if 'HTTP Error' in c:
        return '주소가 죽었다'
    if 'SSL' in c or 'CERTIFICATE' in c.upper():
        return '자동 점검이 못 붙었다'
    if 'timed out' in c:
        return '너무 느리다'
    return '그밖'


def main():
    dis = json.load(open(os.path.join(ROOT, 'data', 'disclosure.json'), encoding='utf-8'))
    cov = json.load(open(os.path.join(ROOT, 'data', 'coverage.json'), encoding='utf-8'))
    idx = json.load(open(os.path.join(SITE, 'data', 'loc', 'index.json'), encoding='utf-8'))
    메타 = {r['cd']: r for r in idx['곳']}

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
            for p in 기초 - 낸곳:
                빠진자료[p].append(이름)
        if len(낸곳 & 광역) >= 16:
            광역잣대 += 1
            for p in 광역 - 낸곳:
                빠진자료[p].append(이름)

    곳 = []
    for r in dis['곳']:
        cd = r['laf_cd']
        m = 메타.get(cd, {})
        파일 = r.get('파일', []) or []
        읽힌 = [f for f in 파일 if not 해시이름.match(f) and re.search(r'[가-힣]', f)]
        확장 = {os.path.splitext(f)[1].lower() for f in 파일}
        열림 = r['상태'] == '열림'

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

        곳.append({
            'cd': cd,
            '이름': r['이름'],
            '시도': m.get('시도', ''),
            '갈래': m.get('갈래', '광역' if cd in 광역 else '기초'),
            '인구': m.get('인구'),
            '주소': r['주소'],
            '링크': '열림' if 열림 else '안 열림',
            '까닭': '' if 열림 else 까닭갈래(r.get('까닭')),
            '제목': (r.get('제목') or '').replace('&lt;', '<').replace('&gt;', '>')[:60],
            '파일수': len(파일),
            '읽힌수': len(읽힌),
            '형식': 형식,
            '항목': 걸린항목,
            '파일': [f[:48] for f in (읽힌 or 파일)[:12]],
            '더': max(0, len(파일) - 12),
            'API빠짐': 빠진자료.get(cd, [])[:6],
            'API빠짐수': len(빠진자료.get(cd, [])),
        })
    곳.sort(key=lambda r: (r['갈래'] != '광역', r['시도'], r['이름']))

    요약 = {
        '모두': len(곳),
        '주소냄': sum(1 for r in 곳 if r['주소']),
        '열림': sum(1 for r in 곳 if r['링크'] == '열림'),
        '파일잡힘': sum(1 for r in 곳 if r['파일수']),
        '이름읽힘': sum(1 for r in 곳 if r['읽힌수']),
        '엑셀': sum(1 for r in 곳 if r['형식'] == '엑셀 있음'),
        '문서뿐': sum(1 for r in 곳 if r['형식'] == '문서뿐'),
        '파일못봄': sum(1 for r in 곳 if r['링크'] == '열림' and not r['파일수']),
        '해시': sum(1 for r in 곳 if r['파일수'] and not r['읽힌수']),
        '까닭': dict(collections.Counter(r['까닭'] for r in 곳 if r['까닭'])),
        'API빠진곳': sum(1 for r in 곳 if r['API빠짐수']),
        'API잣대기초': 기초잣대,
        'API잣대광역': 광역잣대,
        '만든날': dis.get('만든날', ''),
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
