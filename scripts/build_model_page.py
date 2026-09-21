# 화면을 굽는다. site/model.template.html 에 자치단체 목록을 끼워 site/index.html 을 낸다.
#
#   python scripts/build_model_page.py
#
# 페이지에 박히는 것은 **목록뿐**이다(243곳의 코드·이름·시도·갈래·인구, 23KB).
# 고른 곳의 지표는 site/data/loc/<코드>.json 을, 진행 중인 사업은
# site/data/ongoing/<코드>.json 을 화면이 그때그때 받아 온다.
# 목록은 build_model_data.py 가 먼저 만들어 둔다.
#
# 화면을 고칠 때는 template 쪽을 고치고 다시 구울 것. index.html 은 손대지 말 것.
# 깃허브 페이지가 site/ 를 통째로 올리므로 파일 이름이 index.html 이어야 한다.

import gzip
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
    idx_path = os.path.join(SITE, 'data', 'loc', 'index.json')
    if not os.path.exists(idx_path):
        raise SystemExit('site/data/loc/index.json 이 없다. 먼저: python scripts/build_model_data.py --all')
    index = json.load(open(idx_path, encoding='utf-8'))

    # ⚠️ 지표(2024 결산·2026 예산)와 진행 중인 사업(2026 일별)의 **구역이 다르다.**
    # 2026년에 광주·전남이 하나로 묶이고 인천 구역이 갈렸다. 지표에 없고 진행 자료만 있는
    # 곳도 고를 수 있어야 한다 — 「진행만」으로 꼬리표를 달아 목록에 끼워 넣는다.
    있는곳 = {x['cd'] for x in index['곳']}
    ongoing_dir = os.path.join(SITE, 'data', 'ongoing')
    새로 = []
    for name in sorted(os.listdir(ongoing_dir)) if os.path.isdir(ongoing_dir) else []:
        cd = name.split('.')[0]
        if not cd.isdigit() or cd in 있는곳:
            continue
        with gzip.open(os.path.join(ongoing_dir, name), 'rt', encoding='utf-8') as f:
            o = json.load(f)
        새로.append({'cd': cd, '이름': o['자치단체'], '시도': o['자치단체'][:2],
                    '갈래': '광역' if cd.endswith('00000') else '기초',
                    '인구': None, '진행만': 1})
    index['곳'] = index['곳'] + 새로
    index['진행만'] = [x['cd'] for x in 새로]

    tpl = open(os.path.join(SITE, 'model.template.html'), encoding='utf-8').read()
    if '__INDEX__' not in tpl:
        raise SystemExit('template 에 __INDEX__ 자리가 없다')

    out = tpl.replace('__INDEX__', json.dumps(index, ensure_ascii=False, separators=(',', ':')))
    path = os.path.join(SITE, 'index.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(out)

    광역 = sum(1 for x in index['곳'] if x['갈래'] == '광역')
    있는것 = len(os.listdir(os.path.join(SITE, 'data', 'ongoing'))) \
        if os.path.isdir(os.path.join(SITE, 'data', 'ongoing')) else 0
    print(f'구움: site/index.html ({os.path.getsize(path)/1024:,.0f} KB)')
    if 새로:
        print('  지표에 없고 진행 자료만 있는 곳 ' + str(len(새로)) + '곳 — '
              + ' · '.join(x['이름'] for x in 새로))
    print(f"  고를 수 있는 곳 {len(index['곳'])}곳 (광역 {광역} · 기초 {len(index['곳']) - 광역})")
    print(f'  진행 중인 사업이 준비된 곳 {있는것}곳')


if __name__ == '__main__':
    main()
