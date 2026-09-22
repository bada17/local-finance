# 17개 시·도교육청 화면을 굽는다 — site/edu.html
#
#   python scripts/build_edu_page.py
#
# 먼저 `python scripts/fetch_edu.py` 로 자료를 받아 둘 것.
#
# 왜 — 사용자 걱정이 **"공공데이터 트리를 못 보게 될까봐"** 였다(2026-09-22).
#      담을 때는 평평하게 담되(엉키지 않게), **볼 때는 포털 화면의 나무 그대로** 보여준다.
#      담는 모양과 보는 모양은 달라도 된다 — 트리를 줄마다 칸으로 박아 뒀으니 언제든 다시 세운다.
#
# 내는 것
#   site/edu.html                     화면
#   site/data/edu/<갈래>_<대>.json.gz  대분류마다 한 덩이 (눌렀을 때만 받아 간다)
#
# ⚠️ 한 덩이로 합치지 않는다 — 12만 줄을 첫 화면에서 다 받으면 느리다.
#    나무만 먼저 그리고, 고른 대분류만 받아 온다.
# ⚠️ **분류 이름은 `spec_edu.py` 에서 가져온다.** 거기서 「포털(확인)」과 「추정(내가 붙임)」을
#    가르고 있다. 화면에도 그 딱지를 그대로 띄운다 — 확인 안 된 것을 확인된 것처럼 보이면 안 된다.

import glob
import gzip
import json
import os
import shutil
import sys

import spec_edu

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
받는곳 = os.path.join(ROOT, 'data', 'edu')
SITE = os.path.join(ROOT, 'site')
낼곳 = os.path.join(SITE, 'data', 'edu')

갈래앞 = {'결산': 'CLSG', '예산': 'BUDG'}


def main():
    조각 = sorted(glob.glob(os.path.join(받는곳, '*.json.gz')))
    if not 조각:
        raise SystemExit('data/edu 가 비어 있다 — 먼저 python scripts/fetch_edu.py')

    os.makedirs(낼곳, exist_ok=True)
    for p in glob.glob(os.path.join(낼곳, '*.json.gz')):
        os.remove(p)

    나무 = {}
    줄수합 = 0
    해들 = set()
    서비스본것 = set()

    for p in 조각:
        이름 = os.path.basename(p)[:-len('.json.gz')]      # 결산_01
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            줄들 = json.load(f)
        줄수합 += len(줄들)
        shutil.copyfile(p, os.path.join(낼곳, 이름 + '.json.gz'))

        for r in 줄들:
            # ⚠️ 연도가 아예 안 오는 줄이 있다(빈 응답을 주는 서비스). 범위 셀 때 빼야 한다
            해 = r.get('회계연도')
            if 해 and 해 != 'None':
                해들.add(str(해))
            갈, 대, 중 = r['갈래'], r['대'], r['중']
            앞 = 갈래앞.get(갈, '')
            대칸 = 나무.setdefault(갈, {}).setdefault(대, {'중': {}})
            중칸 = 대칸['중'].setdefault(중, {})
            잎 = 중칸.setdefault(r['서비스'], {'이름': r['자료이름'], '줄수': 0})
            잎['줄수'] += 1
            서비스본것.add(r['서비스'])

    # 화면이 쓸 모양으로 옮긴다
    낼나무 = []
    for 갈 in ['결산', '예산']:
        if 갈 not in 나무:
            continue
        앞 = 갈래앞[갈]
        대목록 = []
        for 대 in sorted(나무[갈]):
            대이름, 대출처 = spec_edu.대분류.get((앞, 대), ('(이름 미확인)', '추정'))
            중목록 = []
            for 중 in sorted(나무[갈][대]['중']):
                잎들 = [{'서비스': s, '이름': v['이름'], '줄수': v['줄수']}
                       for s, v in sorted(나무[갈][대]['중'][중].items(),
                                          key=lambda kv: kv[1]['이름'])]
                중이름, 중출처 = spec_edu.중분류.get((앞, 대, 중), (None, None))
                if not 중이름:
                    # ⭐ 자료가 하나뿐인 마디는 **그 자료 이름을 그대로 쓴다.**
                    #    지어낸 것이 아니라 자료에서 온 것이라 「(이름 미확인)」보다 정직하다.
                    #    둘 이상이면 무엇으로 묶인 것인지 모르니 미확인으로 남긴다.
                    if len(잎들) == 1:
                        중이름, 중출처 = 잎들[0]['이름'], '자료에서'
                    else:
                        중이름, 중출처 = '(이름 미확인)', '추정'
                중목록.append({'번호': 중, '이름': 중이름, '출처': 중출처, '자식': 잎들})
            대목록.append({'번호': 대, '이름': 대이름, '출처': 대출처, '자식': 중목록})
        낼나무.append({'이름': 갈, '파일서두': 갈, '자식': 대목록})

    해범위 = f'{min(해들)}~{max(해들)}' if 해들 else '?'
    상태 = {}
    상태파일 = os.path.join(받는곳, '상태.json')
    if os.path.exists(상태파일):
        상태 = json.load(open(상태파일, encoding='utf-8'))

    tpl = open(os.path.join(SITE, 'edu.template.html'), encoding='utf-8').read()
    # ⚠️ 날짜·해를 화면에 박지 말 것 — 자료에서 꺼내 넣는다
    나온 = (tpl
            .replace('__TREE__', json.dumps(낼나무, ensure_ascii=False,
                                            separators=(',', ':')))
            .replace('__SVC__', f'{len(서비스본것):,}')
            .replace('__ROWS__', f'{줄수합:,}')
            .replace('__YEARS__', 해범위)
            .replace('__ASOF__', 상태.get('마지막수집', '')))
    길 = os.path.join(SITE, 'edu.html')
    open(길, 'w', encoding='utf-8').write(나온)

    덩이 = sum(os.path.getsize(p) for p in glob.glob(os.path.join(낼곳, '*.json.gz')))
    print(f'구움: site/edu.html ({os.path.getsize(길)/1024:,.0f} KB)')
    print(f'  서비스 {len(서비스본것):,}종 · {줄수합:,}줄 · 회계연도 {해범위}')
    print(f'  덩이 {len(조각)}개 · {덩이/1024:,.0f} KB → site/data/edu/')


if __name__ == '__main__':
    main()
