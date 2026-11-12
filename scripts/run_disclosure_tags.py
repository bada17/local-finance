# 재정공시 꼬리표 — 못 찾은 것만 다시 찾고, 받아 열고, 꼬리표를 다시 단다. 사람·봇 누구나 인자 없이 돌린다.
#   python scripts/run_disclosure_tags.py          (크롬 포트는 CDP_PORT, 없으면 9450)
#
#   ① tag_disclosure.py --묶음일감 --검색일감  → 아직 못 찾은 곳·말만 일감으로
#   ② find_settle_page.js   결산(예산)기준 공시 화면 링크 찾기 → data/disclosure_settle.json (앞 결과와 합침)
#   ③ search_disclosure_items.js   누리집 통합검색(글 링크도 적음) → data/disclosure_search.json (앞 결과와 합침)
#   ④ open_search_posts.js   검색에 걸린 글로 들어가 첨부 목록 → data/disclosure_posts.json
#   ④′ read_disclosure_files.py <②④ 곳들>  파일 받아 열기 → data/disclosure_files.json (그 곳만 갈아 끼움, 받은 것은 캐시)
#   ⑤ tag_disclosure.py → disclosure_tags_곳·항목·파일.csv
#   ⑥ build_score.py --문서일감 → find_score_docs.js(투명성 지표 문서를 별도로 올렸나, 꼬리표: 방법·클릭·쪽·형식·해) → build_score.py → site/score.html
#   ⑦ make_review_xlsx.py → 검토 엑셀
# 화면에는 단계마다 한두 줄만 남긴다(긴 기록은 %TEMP%/lf-disclosure-tags-*.log) — 대화창·봇 기록을 작게.
# ⚠️ 국내 누리집이 해외 서버를 막는다(pc_disclosure.ps1 머리말) — 봇으로 돌리면 이 PC 작업 스케줄러에서.
import json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = tempfile.gettempdir()
env = {**os.environ, 'CDP_PORT': os.environ.get('CDP_PORT', '9450'), 'PYTHONIOENCODING': 'utf-8'}


def 돌려(이름, *명령):
    log = os.path.join(T, f'lf-disclosure-tags-{이름}.log')
    with open(log, 'w', encoding='utf-8') as fp:
        p = subprocess.run(명령, cwd=ROOT, env=env, stdout=fp, stderr=subprocess.STDOUT)
    끝 = open(log, encoding='utf-8', errors='replace').read().strip().splitlines()[-2:]
    print(f'[{이름}] {"됨" if p.returncode == 0 else "틀림 " + str(p.returncode)} — ' + ' / '.join(s[:160] for s in 끝), flush=True)
    if p.returncode:
        sys.exit(p.returncode)


py = [sys.executable, '-X', 'utf8']
묶음, 검색 = os.path.join(T, 'lf-settle-job.json'), os.path.join(T, 'lf-search-job.json')
돌려('일감', *py, 'scripts/tag_disclosure.py', '--묶음일감', 묶음, '--검색일감', 검색)
if json.load(open(묶음, encoding='utf-8')):
    돌려('링크', 'node', 'scripts/find_settle_page.js', 묶음)
if json.load(open(검색, encoding='utf-8')):
    돌려('검색', 'node', 'scripts/search_disclosure_items.js', 검색)
돌려('글열기', 'node', 'scripts/open_search_posts.js')
곳들 = set()
for 이름 in ('disclosure_settle.json', 'disclosure_posts.json'):
    p = os.path.join(ROOT, 'data', 이름)
    if os.path.exists(p):
        곳들 |= {k.split('|')[0] for k in json.load(open(p, encoding='utf-8'))['곳']}
돌려('열기', *py, 'scripts/read_disclosure_files.py', *sorted(곳들))
돌려('꼬리표', *py, 'scripts/tag_disclosure.py')
# 투명성 지표 문서 항목 — 별도 문서로 올렸나 끝까지 찾기(find_score_docs.js), 그다음 화면 굽기
문서 = os.path.join(T, 'lf-scoredocs-job.json')
돌려('문서일감', *py, 'scripts/build_score.py', '--문서일감', 문서)
if json.load(open(문서, encoding='utf-8')):
    돌려('문서찾기', 'node', 'scripts/find_score_docs.js', 문서)
돌려('화면', *py, 'scripts/build_score.py')
돌려('엑셀', *py, 'scripts/make_review_xlsx.py', '.', 'data/disclosure_tags_검토.xlsx')
