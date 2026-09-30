# 중앙투자심사 한글 원본(site/review/*.hwpx)을 PDF 로 뽑는다 — 휴대폰에서도 원문을 열 수 있게.
#
#   python scripts/review_pdf.py
#
# ⚠️ 한컴오피스가 깔린 윈도 PC 에서만 돈다(한글 COM 자동화, pip install pywin32). 봇은 못 돌린다.
#    PDF 가 없는 회차는 화면이 한글 파일만 건다. 새 회차가 붙으면 이 PC 에서 한 번 돌려 올릴 것.
# 이미 있는 PDF 는 건너뛴다.

import glob
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'site', 'review')


def 쪽수():
    """PDF 마다 「사업명(빈칸 뺀 것) → 처음 나오는 쪽」 — 화면이 줄마다 file.pdf#page=N 으로 건다.
    site/review/pages.json. 사업명이 쪽을 넘어가 끊기면 못 찾는다 — 그 줄은 첫 쪽으로 열린다."""
    import pymupdf
    D = json.load(open(os.path.join(ROOT, 'data', 'review.json'), encoding='utf-8'))
    이름들 = {}
    for x in D['사업']:
        이름들.setdefault(f"{x['dtsSnum']}_{os.path.basename(x['파일'])}"[:-5], set()).add(
            re.sub(r'\s+', '', x['사업명']))
    out = {}
    for f in sorted(glob.glob(os.path.join(SRC, '*.pdf'))):
        k = os.path.basename(f)[:-4]
        쪽 = [re.sub(r'\s+', '', p.get_text()) for p in pymupdf.open(f)]
        out[k] = {n: i + 1 for n in 이름들.get(k, ()) for i in [next((i for i, t in enumerate(쪽) if n in t), 0)] if i}
    json.dump(out, open(os.path.join(SRC, 'pages.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"쪽 찾음: {sum(len(v) for v in out.values())} / {sum(len(v) for v in 이름들.values())}")


def main():
    할것 = [f for f in sorted(glob.glob(os.path.join(SRC, '*.hwpx')))
           if not os.path.exists(f[:-5] + '.pdf')]
    if not 할것:
        print('뽑을 것 없음')
        return 쪽수()
    import win32com.client
    hwp = win32com.client.gencache.EnsureDispatch('HWPFrame.HwpObject')
    hwp.XHwpWindows.Item(0).Visible = False
    # 파일 접근 보안 창을 안 띄우려면 보안 모듈 등록이 필요하다 — 없으면 창이 뜨고 눌러 줘야 한다
    try:
        hwp.RegisterModule('FilePathCheckDLL', 'FilePathCheckerModule')
    except Exception:
        pass
    try:
        for f in 할것:
            hwp.Open(os.path.abspath(f), 'HWPX', 'forceopen:true')
            hwp.SaveAs(os.path.abspath(f[:-5] + '.pdf'), 'PDF', '')
            print('  ' + os.path.basename(f)[:-5] + '.pdf')
    finally:
        hwp.Quit()
    print(f'뽑음: {len(할것)}개')
    쪽수()


if __name__ == '__main__':
    main()
