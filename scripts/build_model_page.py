# 모델 화면을 굽는다. site/model.template.html 에 데이터를 끼워 site/index.html 을 낸다.
#
#   python scripts/build_model_page.py 2600000 4373000
#
# 데이터는 build_model_data.py 가 미리 만들어 둔 data/model/<코드>.json 을 쓴다.
# 화면을 고칠 때는 template 쪽을 고치고 다시 구울 것. index.html 은 손대지 말 것.
# 깃허브 페이지가 site/ 를 통째로 올리므로 파일 이름이 index.html 이어야 한다.

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
    codes = sys.argv[1:] or ['2600000', '4373000']
    data = {}
    for cd in codes:
        with open(os.path.join(ROOT, 'data', 'model', f'{cd}.json'), encoding='utf-8') as f:
            data[cd] = json.load(f)

    tpl = open(os.path.join(SITE, 'model.template.html'), encoding='utf-8').read()
    if '__DATA__' not in tpl:
        raise SystemExit('template 에 __DATA__ 자리가 없다')

    out = tpl.replace('__DATA__', json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    path = os.path.join(SITE, 'index.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(out)

    print(f'구움: site/index.html ({os.path.getsize(path)/1024:,.0f} KB)')
    for cd, d in data.items():
        print(f"  {d['이름']} · 지표 {len(d['지표'])}개 · 견줄 곳 {d['견줄곳수']}")


if __name__ == '__main__':
    main()
