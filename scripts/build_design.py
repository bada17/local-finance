"""여섯 화면을 기존 빌더로 굽되, 디자인 작업으로 원자료/압축파일/공시 이력을 바꾸지 않는다.

python scripts/build_design.py
CLIK 원본을 새로 받았으면 먼저 python scripts/build_clik.py
"""
from pathlib import Path
import shutil
import tempfile
import build_model_page
import build_board
import build_transparency
import build_catalog_page
import build_edu_page
import build_datamap
import build_review_page


def main():
    with tempfile.TemporaryDirectory(prefix='finance-design-') as folder:
        tmp = Path(folder)
        # 빌더가 화면 외에 쓰는 파일만 임시 경로로 돌린다. 자료를 세는 코드는 원래 것을 쓴다.
        old_board, old_edu, old_history = build_board.OUT, build_edu_page.낼곳, build_transparency.발자취
        build_board.OUT = str(tmp/'board.json.gz')
        build_edu_page.낼곳 = str(tmp/'edu')
        build_transparency.발자취 = str(tmp/'disclosure_history.json')
        if Path(old_history).exists():
            shutil.copyfile(old_history, build_transparency.발자취)
        try:
            for module in (build_model_page, build_board, build_transparency, build_catalog_page, build_edu_page, build_datamap, build_review_page):
                module.main()
        finally:
            build_board.OUT, build_edu_page.낼곳, build_transparency.발자취 = old_board, old_edu, old_history


if __name__ == '__main__':
    main()
