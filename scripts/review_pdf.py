# 중앙투자심사 한글 원본(site/review/*.hwpx)을 PDF 로 뽑는다 — 휴대폰에서도 원문을 열 수 있게.
#
#   python scripts/review_pdf.py
#
# ⚠️ 한컴오피스가 깔린 윈도 PC 에서만 돈다(한글 COM 자동화, pip install pywin32). 봇은 못 돌린다.
#    PDF 가 없는 회차는 화면이 한글 파일만 건다. 새 회차가 붙으면 이 PC 에서 한 번 돌려 올릴 것.
# 이미 있는 PDF 는 건너뛴다.

import glob
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'site', 'review')


def main():
    할것 = [f for f in sorted(glob.glob(os.path.join(SRC, '*.hwpx')))
           if not os.path.exists(f[:-5] + '.pdf')]
    if not 할것:
        print('뽑을 것 없음')
        return
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


if __name__ == '__main__':
    main()
