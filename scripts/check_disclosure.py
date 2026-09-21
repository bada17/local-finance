# 재정공시가 「진짜로」 올라와 있는지 본다 — API 말고 자치단체 홈페이지를.
#
#   python scripts/check_disclosure.py            243곳 링크가 살아 있나
#   python scripts/check_disclosure.py --files 30 앞 30곳은 붙은 파일 이름까지 긁는다
#
# ⚠️ **API 에 없다고 「공개 안 했다」가 아니다.** 공시는 한글·엑셀 파일로 홈페이지에 올라간다.
#    지방재정365 `FINLK` 가 자치단체별 재정공시 페이지 주소를 주니, 거기를 직접 눌러 본다.
#
# 세 가지를 가른다 —
#   ① 링크가 아예 없다        → 지방재정365에 주소조차 안 낸 곳
#   ② 링크가 죽었다(4xx/5xx)  → 냈는데 안 열린다. 제60조 제2항 위반 소지
#   ③ 열린다                  → 그다음은 무슨 파일이 붙었나를 본다
#
# 결과: data/disclosure.json

import datetime
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lofin import fetch, load_key  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'disclosure.json')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')
첨부 = re.compile(r'[\w가-힣()\[\]\-. ]{4,60}\.(hwpx?|xlsx?|pdf|docx?|zip)', re.I)


def 눌러보기(one):
    cd, nm, url = one
    out = {'laf_cd': cd, '이름': nm, '주소': url}
    if not url:
        out['상태'] = '주소 없음'
        return out
    if not url.startswith('http'):
        url = 'https://' + url.lstrip('/')     # 스킴을 빼먹고 낸 곳이 있다
        out['주소'] = url
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(400_000)
            out['코드'] = r.status
            out['끝주소'] = r.url
            try:
                글 = body.decode('utf-8')
            except UnicodeDecodeError:
                글 = body.decode('euc-kr', errors='replace')
            out['상태'] = '열림'
            t = re.search(r'<title[^>]*>(.*?)</title>', 글, re.S | re.I)
            out['제목'] = re.sub(r'\s+', ' ', t.group(1)).strip()[:60] if t else ''
            이름들 = [m.group(0).strip() for m in 첨부.finditer(글)]
            본것 = list(dict.fromkeys(이름들))      # 같은 파일이 여러 번 나온다
            out['파일'] = 본것[:40]
            out['파일수'] = len(본것)
    except Exception as e:
        out['상태'] = '안 열림'
        out['까닭'] = str(e)[:70]
    return out


def main():
    파일까지 = None
    if '--files' in sys.argv:
        i = sys.argv.index('--files')
        파일까지 = int(sys.argv[i + 1]) if len(sys.argv) > i + 1 else 243

    # ⚠️ 해를 박아 두지 않는다. 공시는 해마다 새로 올라오므로 **새 해부터 거슬러** 찾는다.
    #    `python scripts/check_disclosure.py --해 2026` 으로 못박을 수도 있다.
    key = load_key()
    해목록 = ([sys.argv[sys.argv.index('--해') + 1]] if '--해' in sys.argv
             else [str(datetime.date.today().year - n) for n in range(0, 3)])
    rows, 쓴해 = [], ''
    for 해 in 해목록:
        rows, _ = fetch('FINLK', {'fyr': 해}, key)
        if rows:
            쓴해 = 해
            break
    if not rows:
        raise SystemExit(f'FINLK 에서 공시 링크를 못 받았다 (해본 해: {해목록})')
    링크 = [(r['laf_cd'], r.get('laf_hg_nm', ''), r.get('lnk_url_nm') or '') for r in rows]
    print(f'재정공시 링크 {len(링크)}곳 (지방재정365 FINLK {쓴해})')

    볼것 = 링크[:파일까지] if 파일까지 else 링크
    결과 = []
    시각 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        for i, r in enumerate(ex.map(눌러보기, 볼것), 1):
            결과.append(r)
            if i % 40 == 0:
                print(f'  {i}/{len(볼것)} · {(time.time()-시각)/60:.0f}분')

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump({'만든날': time.strftime('%Y-%m-%d'), '곳': 결과}, f,
                  ensure_ascii=False, separators=(',', ':'))

    셈 = {}
    for r in 결과:
        셈[r['상태']] = 셈.get(r['상태'], 0) + 1
    print('\n■ 재정공시 링크')
    for k, v in sorted(셈.items(), key=lambda kv: -kv[1]):
        print(f'   {k:<8} {v:>3}곳')
    붙은 = [r for r in 결과 if r.get('파일수')]
    if 붙은:
        print(f'   파일이 잡힌 곳 {len(붙은)}곳 · 한 곳 평균 {sum(r["파일수"] for r in 붙은)/len(붙은):.0f}개')
    print(f'{(time.time()-시각)/60:.1f}분 · data/disclosure.json')


if __name__ == '__main__':
    main()
