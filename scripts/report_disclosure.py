# 재정공시 페이지에 붙은 파일 이름으로 「법이 시키는 것을 올렸나」를 센다.
#
#   python scripts/report_disclosure.py
#
# ⚠️ **파일 이름만 보고 세는 것이다.** 이름이 해시(`67c141f1….pdf`)인 곳은 판별이 안 되고,
#    목록을 자바스크립트로 그리는 곳은 파일이 아예 안 잡힌다. **「없다」고 단정하면 안 된다.**
#    이 셈은 「홈페이지에서 곧바로 확인되는가」이지 「공시했는가」가 아니다.

import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 지방재정법 제60조 제1항이 시키는 것 ↔ 파일 이름에 나올 만한 말
항목 = [
    ('1. 세입·세출예산 운용상황', ['재정공시', '세입세출', '운용상황', '예산기준']),
    ('2. 재무제표', ['재무제표', '재정상태표', '재정운영표']),
    ('3. 채권관리 현황', ['채권']),
    ('4. 기금운용 현황', ['기금']),
    ('5. 공유재산 증감·현재액', ['공유재산']),
    ('6. 지역통합재정통계', ['통합재정']),
    ('7. 공기업·출자출연 경영정보', ['공기업', '출자', '출연']),
    ('8. 중기지방재정계획', ['중기지방재정', '중기재정']),
    ('9. 성인지 예산서·결산서', ['성인지']),
    ('10. 예산편성기준별 운영상황', ['예산편성기준']),
    ('10의2. 주민참여예산 운영·의견서', ['주민참여', '주민의견']),
    ('11. 재정운용상황개요서', ['개요서']),
    ('12. 재정건전화계획', ['건전화']),
    ('13. 재정건전성관리계획', ['건전성관리']),
    ('14. 투자심사·지방채·민자·보증채무', ['투자심사', '지방채', '민간투자', '민자', '보증채무']),
    ('15. 지방보조금', ['보조금']),
]
해시이름 = re.compile(r'^[0-9a-f]{8,}[._]', re.I)


def main():
    d = json.load(open(os.path.join(ROOT, 'data', 'disclosure.json'), encoding='utf-8'))['곳']
    셈 = {}
    for r in d:
        셈[r['상태']] = 셈.get(r['상태'], 0) + 1
    print(f'재정공시 링크 {len(d)}곳')
    for k, v in sorted(셈.items(), key=lambda kv: -kv[1]):
        print(f'   {k:<8} {v:>3}곳')

    열린것 = [r for r in d if r['상태'] == '열림']
    파일있 = [r for r in 열린것 if r.get('파일수')]
    해시만 = [r for r in 파일있
              if all(해시이름.match(f) or not re.search(r'[가-힣]', f) for f in r['파일'])]
    빈것 = [r for r in 열린것 if not r.get('파일수')]
    print(f'\n■ 열린 {len(열린것)}곳 가운데')
    print(f'   파일 이름이 잡힌 곳      {len(파일있) - len(해시만):>3}곳')
    print(f'   파일 이름이 해시라 못 읽음 {len(해시만):>3}곳')
    print(f'   파일이 아예 안 잡힘       {len(빈것):>3}곳  (목록을 자바스크립트로 그리는 곳)')

    볼수있는 = [r for r in 파일있 if r not in 해시만]
    print(f'\n■ 파일 이름을 읽을 수 있는 {len(볼수있는)}곳에서, 법 제60조 항목이 이름으로 확인되는 비율')
    for 이름, 말들 in 항목:
        n = sum(1 for r in 볼수있는 if any(w in ' '.join(r['파일']) for w in 말들))
        칸 = '█' * round(n / max(1, len(볼수있는)) * 20)
        print(f'   {n:>3}곳 ({n/max(1,len(볼수있는))*100:>3.0f}%) {칸:<20} {이름}')

    print('\n   ⚠️ 낮다고 「안 올렸다」가 아니다 — 한 파일에 여러 항목을 묶어 넣은 곳이 많다.')
    print('      이 셈은 「홈페이지에서 곧바로 확인되는가」다.')

    안열림 = [r for r in d if r['상태'] != '열림']
    if 안열림:
        print(f'\n■ 링크가 안 열리거나 없는 {len(안열림)}곳')
        for r in 안열림[:20]:
            print(f'   {r["이름"]:<12} {r["상태"]}  {(r.get("까닭") or r.get("주소") or "")[:54]}')


if __name__ == '__main__':
    main()
