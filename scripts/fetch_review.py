# 지방재정 중앙투자심사 결과 수집기 — **큰 사업을 누가 통과시켰나 · 반려했나**가 여기 있다.
#
#   python scripts/fetch_review.py                   2022-07-01 뒤로 올라온 회차 전부
#   python scripts/fetch_review.py --부터 2014-01-01  더 옛날까지
#
# 어디서 — 지방재정365 「통합자료실 > 성과/평가 > 중앙투자심사결과」 게시판(분류 FSL414).
#   공공데이터포털 15051377 은 이 게시판을 가리키는 **링크형**이고 그 링크는 죽었다(404, 2026-09-30).
#   API 가 아니라 **회차마다 한글(hwpx) 파일 하나**다. 파일 안의 표 하나에
#   「광역명(시군명) · 사업명 · 사업기간 · 사업량 · 사업비(억원) · 심사 결과」가 줄마다 들어 있다.
# ⭐ 회차가 몇 개 안 돼(한 해 4~8회) **돌 때마다 전부 다시 받는다.** 새 회차는 저절로 붙는다.
# ⚠️ 목록 JSON 은 목록 화면 HTML 안에 박혀 온다(`[{"brdDvId"...`). 한 쪽 10건.
# ⚠️ 목록의 첨부 이름은 믿지 말 것 — 2022 수시 글은 목록엔 `secutest.jpg` 로 나온다.
#    첨부는 글 상세(`retvItgRfrmDts.do`)에서 `brdFileUnqSnum=…,ognFileNm=…` 로 읽는다.
# ⚠️ 표에 **합친 칸**이 있다(한 곳의 사업 여러 줄에 곳 이름 한 칸). 칸 주소(cellAddr)로 격자를 맞추고
#    빈 칸은 위 줄 값을 이어 받는다.

import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import zipfile

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRD = 'https://www.lofin365.go.kr/lf/prtcCmct/brd/itgRfrmSvi/'
OUT = os.path.join(ROOT, 'data', 'review.json')
# 받은 한글 원본 — 화면이 줄마다 여기로 링크한다. 같은 이름의 .pdf 가 있으면 그것을 앞에 세운다
# (PDF 는 한컴오피스가 있는 PC 에서 scripts/review_pdf.py 로 뽑는다. 봇은 못 뽑는다)
SRC = os.path.join(ROOT, 'site', 'review')
os.makedirs(SRC, exist_ok=True)


def 원본이름(dts, 이름):
    """「654898_2022-3차 중앙투자심사 결과.hwpx」 — zip 안 경로는 떼고, 글 번호로 겹침을 막는다."""
    return f'{dts}_{os.path.basename(이름)}'


def post(url, **form):
    req = urllib.request.Request(url, urllib.parse.urlencode(form).encode(),
                                 headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def 글목록():
    글 = {}
    for 쪽 in range(1, 100):
        s = post(BRD + 'retvLstItgRfrm.do', menuParaCn='RFRM', menuId='LF8310000',
                 ntcaClsDvCd='FSL414', curPage=쪽).decode('utf-8', 'replace')
        i = s.rfind('[{"brdDvId"')
        rows = json.JSONDecoder().raw_decode(s[i:])[0] if i >= 0 else []
        새것 = [x for x in rows if x['dtsSnum'] not in 글]
        if not 새것:
            break
        글.update((x['dtsSnum'], x) for x in 새것)
    return sorted(글.values(), key=lambda x: x['frstRgstrDd'])


def 첨부(dts):
    s = post(BRD + 'retvItgRfrmDts.do', menuParaCn='RFRM', menuId='LF8310100',
             dtsSnum=dts).decode('utf-8', 'replace')
    return dict(re.findall(r'brdFileUnqSnum=(\d+)\s*,.*?ognFileNm=([^,\]]+?\.\w+)', s))


def hwpx들(이름, 몸):
    """hwpx 는 그대로, zip 은 안의 hwpx 를 꺼낸다. 나머지(jpg·pdf)는 버린다."""
    if 이름.lower().endswith('.hwpx'):
        yield 이름, 몸
    elif 이름.lower().endswith('.zip'):
        z = zipfile.ZipFile(io.BytesIO(몸))
        for n in z.namelist():
            if n.lower().endswith('.hwpx'):
                yield n, z.read(n)


def 표들(몸):
    z = zipfile.ZipFile(io.BytesIO(몸))
    for n in sorted(x for x in z.namelist() if re.match(r'Contents/section\d+\.xml$', x)):
        x = z.read(n).decode('utf-8')
        for t in re.findall(r'<hp:tbl\b.*?</hp:tbl>', x, flags=re.S):
            칸 = {}
            for tc in re.findall(r'<hp:tc\b.*?</hp:tc>', t, flags=re.S):
                a = re.search(r'<hp:cellAddr colAddr="(\d+)" rowAddr="(\d+)"', tc)
                sp = re.search(r'<hp:cellSpan colSpan="(\d+)" rowSpan="(\d+)"', tc)
                if not a:
                    continue
                c, r = int(a[1]), int(a[2])
                cs, rs = (int(sp[1]), int(sp[2])) if sp else (1, 1)
                # <hp:t> 안에 <hp:lineBreak/> 가 끼어 온다 — 태그는 빈칸으로
                글자 = ' '.join(''.join(re.sub(r'<[^>]+>', ' ', s)
                                       for s in re.findall(r'<hp:t\b[^>]*>(.*?)</hp:t>', p, flags=re.S))
                              for p in re.findall(r'<hp:p\b.*?</hp:p>', tc, flags=re.S)).strip()
                글자 = re.sub(r'\s+', ' ', 글자)
                for dr in range(rs):          # 합친 칸은 덮는 자리마다 같은 값을 채운다
                    for dc in range(cs):
                        칸[(r + dr, c + dc)] = 글자
            if 칸:
                nr = max(r for r, _ in 칸) + 1
                nc = max(c for _, c in 칸) + 1
                yield [[칸.get((r, c), '') for c in range(nc)] for r in range(nr)]


def 사업줄(표):
    """머리줄(「사업명」이 든 줄)을 찾아 그 아래를 사전으로. 심사결과 표가 아니면 빈 목록."""
    for h, row in enumerate(표):
        if any('사업명' in c for c in row) and any('결과' in c for c in row):
            break
    else:
        return []
    머리 = [re.sub(r'\s+', '', c) for c in 표[h]]
    줄 = []
    for row in 표[h + 1:]:
        d = {k: v for k, v in zip(머리, row) if k}
        if not any(v for k, v in d.items() if '사업명' in k):
            continue
        if list(d.values()).count(d.get(머리[0], '')) == len(d):   # 「소계」처럼 한 칸이 줄 전체를 덮은 줄
            continue
        줄.append(d)
    return 줄


def main():
    부터 = sys.argv[sys.argv.index('--부터') + 1] if '--부터' in sys.argv else '2022-07-01'
    회차, 사업 = [], []
    for g in 글목록():
        제목 = g['ntcaTitCn'].strip()
        if g['frstRgstrDd'] < 부터 or '결과' not in 제목:
            continue
        받은 = 0
        for fsn, 파일 in 첨부(g['dtsSnum']).items():
            몸 = post(BRD + 'fileDown.do', dtsSnum=g['dtsSnum'], fileSnum=fsn,
                     menuId='LF8310000', menuParaCn='RFRM')
            for 이름, h in hwpx들(파일, 몸):
                줄 = [x for t in 표들(h) for x in 사업줄(t)]
                if 줄:   # 원본을 사이트에 둔다 — 지방재정365 글은 POST 로만 열려 링크를 걸 수 없다
                    with open(os.path.join(SRC, 원본이름(g['dtsSnum'], 이름)), 'wb') as f:
                        f.write(h)
                for x in 줄:
                    사업.append({'글': 제목, '올린날': g['frstRgstrDd'], '파일': 이름,
                               'dtsSnum': g['dtsSnum'], **x})
                받은 += len(줄)
                print(f"  {g['frstRgstrDd']} {이름} — {len(줄)}줄")
        회차.append({'글': 제목, '올린날': g['frstRgstrDd'], 'dtsSnum': g['dtsSnum'], '사업수': 받은})
        if not 받은:
            print(f"  ⚠️ {제목} — 표를 못 읽었다")
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump({'원본': '지방재정365 통합자료실 > 중앙투자심사결과 (FSL414)', '부터': 부터,
                   '회차': 회차, '사업': 사업}, f, ensure_ascii=False, indent=1)
    print(f'낸 곳: data/review.json — 회차 {len(회차)} · 사업 {len(사업)}줄')


if __name__ == '__main__':
    main()
