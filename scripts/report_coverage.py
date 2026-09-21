# 「무엇이 있고 누가 안 냈나」를 사람이 읽을 수 있게 줄여서 찍는다.
#
#   python scripts/report_coverage.py
#
# build_coverage.py 가 만든 data/coverage.json 을 읽는다. 원본은 크니 여기서 세어서만 말한다.
#
# ⚠️ **적게 나온다고 「안 낸 것」이 아니다.** 광역만 내는 자료, 그해에 해당이 없는 자료
#    (청사를 안 지었으면 청사신축원가가 없다)가 섞여 있다. 투명성 지표로 쓰려면
#    **내야 하는 자료가 무엇인지**부터 가려야 한다.

import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    d = json.load(open(os.path.join(ROOT, 'data', 'coverage.json'), encoding='utf-8'))['서비스']
    이름 = {}
    idx = os.path.join(ROOT, 'site', 'data', 'loc', 'index.json')
    if os.path.exists(idx):
        이름 = {x['cd']: x['이름'] for x in json.load(open(idx, encoding='utf-8'))['곳']}

    센것 = {k: v for k, v in d.items() if '곳수' in v}
    건너뜀 = {k: v for k, v in d.items() if '건너뜀' in v}
    print(f'146종 가운데 {len(센것)}종을 세었다. 못 센 {len(건너뜀)}종:')
    for k, v in 건너뜀.items():
        print(f'   {k} {v["이름"][:26]} — {v["건너뜀"]}')

    해 = {}
    for v in 센것.values():
        해[v['연도']] = 해.get(v['연도'], 0) + 1
    print('\n■ 자료가 어느 해까지 오나')
    for y in sorted(해, reverse=True):
        print(f'   {y}년 까지 … {해[y]}종')
    낡은 = sorted([v for v in 센것.values() if int(v['연도']) <= 2022], key=lambda v: v['연도'])
    print(f'   ▸ 2022년 이전에서 멈춘 {len(낡은)}종')
    for v in 낡은:
        print(f'     {v["연도"]}  {v["이름"][:40]}')

    단위 = {}
    for v in 센것.values():
        단위[v.get('단위', '?')] = 단위.get(v.get('단위', '?'), 0) + 1
    print('\n■ 어느 단위로 오나')
    for k, n in sorted(단위.items(), key=lambda kv: -kv[1]):
        print(f'   {k:<5} … {n}종')
    print('   ⚠️ 시도·없음으로 오는 것은 「안 냈다」가 아니라 원래 그 단위로만 나오는 자료다')

    단체것 = [v for v in 센것.values() if v.get('단위') == '자치단체']
    전수 = [v for v in 단체것 if v['곳수'] >= 243]
    일부 = sorted([v for v in 단체것 if v['곳수'] < 243], key=lambda v: v['곳수'])
    print(f'\n■ 자치단체 단위 {len(단체것)}종 — 243곳 다 담은 것 {len(전수)}종 · 일부만 {len(일부)}종')
    for v in 일부[:12]:
        print(f'     {v["곳수"]:>3}곳  {v["연도"]}  {v["이름"][:36]}')

    있 = {}
    for v in 단체것:
        for cd in v['곳']:
            있[cd] = 있.get(cd, 0) + 1
    if 이름:
        모두 = {cd: 있.get(cd, 0) for cd in 이름}
        낮은 = sorted(모두.items(), key=lambda kv: kv[1])
        print(f'\n■ 자치단체별 — 자치단체 단위 {len(단체것)}종 가운데 몇 종에 이름이 있나')
        print('   ⚠️ 적다고 「안 낸 것」이 아니다. 무엇을 내야 하는지부터 가려야 지표가 된다')
        for cd, n in 낮은[:8]:
            print(f'     {n:>3}종  {이름.get(cd, cd)}')
        print('     …')
        for cd, n in 낮은[-3:][::-1]:
            print(f'     {n:>3}종  {이름.get(cd, cd)}')
        vals = sorted(모두.values())
        print(f'   가운뎃값 {vals[len(vals)//2]}종 · 가장 적은 곳 {vals[0]}종 · 가장 많은 곳 {vals[-1]}종')


if __name__ == '__main__':
    main()
