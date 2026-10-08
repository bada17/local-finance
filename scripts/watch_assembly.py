# 국회 회의록 낱말 알림 — 22대 본회의·위원회 회의록 PDF 본문에서 낱말을 찾아 텔레그램으로 보낸다(내부용).
#
#   python scripts/watch_assembly.py              안 본 회의를 훑는다 (기본 300분에서 멈춘다)
#   python scripts/watch_assembly.py --분 10      10분만
#
# 왜 — 2026-10-06 사용자: 미래대응기금은 국회 회의록으로 봐야 한다. "22대, 올해 초부터 논의됐을 거야".
# ⚠️ 열린국회정보 API 는 **본문 검색이 없다**(회의명·안건명·날짜로만 거른다).
#    그래서 회의마다 PDF(1~2MB)를 받아 pdftotext 로 글자를 뽑아 찾는다. 한 회의에 몇 초.
#    처음 한 번은 2026년 치를 다 훑느라 몇 시간 걸리고, 그 뒤로는 날마다 새 회의 몇 건뿐이다.
# ⚠️ PDF 는 줄이 바뀌면서 낱말이 끊긴다(「위원\n장」) — 글자 사이 빈칸·줄바꿈을 허용해 찾는다.
# ⭐ 2026-10-08 사용자: "상임위나 국정감사에서 나온 내용은 안 나오나?" → 위원회 목록(상임위·특위·소위)에
#    **국정감사·국정조사·공청회·인사청문회 등 VCONF 목록**을 더했다(같은 PDF 번호면 한 번만 본다).
#    알림은 한 회의 한 줄 + **회의록 전문 화면 링크**만(사용자: 발언 요약은 길어서 별로, PDF 도 필요 없음 —
#    웹에서 찾기로 보는 게 빠르다).
#
# 열쇠 — ASSEMBLY_KEY(열린국회정보) · TELEGRAM_TOKEN · TELEGRAM_CHAT_ID. 공개 저장소라 값은 안 적는다.
# 텔레그램 열쇠가 없으면 찾은 것을 「안 보냄」으로 쌓아 두었다가 열쇠가 생기면 그때 보낸다.

import argparse
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

import keys
from watch_clik import 보내기

낱말들 = ['미래대응기금']
대수 = 22
첫해 = 2026        # 사용자 — "올해 초부터"
목록 = {'본회의': 'nzbyfwhwaoanttzje', '위원회': 'ncwgseseafwbuheph'}   # DAE_NUM + CONF_DATE(해)
# 대(ERACO)로만 거르는 회의록 목록 — 코드는 github.com/hollobit/assembly-api-mcp src/api/codes.ts 에서 찾았다.
VCONF = {'국정감사': 'VCONFAPIGCONFLIST', '국정조사': 'VCONFPIPCONFLIST', '공청회': 'VCONFPHCONFLIST',
         '인사청문회': 'VCONFCFRMCONFLIST', '청문회': 'VCONFCHCONFLIST', '소위원회': 'VCONFSUBCCONFLIST',
         '예결특위': 'VCONFBUDGETCONFLIST', '특별위원회': 'VCONFSPCCONFLIST', '연석회의': 'VCONFJMCONFLIST'}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
상태파일 = os.path.join(ROOT, 'data', 'assembly', '알림.json')
UA = {'User-Agent': 'Mozilla/5.0'}


def 받기(url, 초=120):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=초) as r:
        return r.read()


def 쪽들(갈래, 코드, 인자):
    쪽 = 1
    while True:
        q = urllib.parse.urlencode({**인자, 'Type': 'json', 'pIndex': 쪽, 'pSize': 1000})
        d = json.loads(받기(f'https://open.assembly.go.kr/portal/openapi/{코드}?{q}'))
        if 코드 not in d:       # INFO-200 = 더 없음. 다른 코드는 오류다.
            if d.get('RESULT', {}).get('CODE') != 'INFO-200':
                raise RuntimeError(f'{갈래} {쪽}쪽: {d.get("RESULT")}')
            return
        줄들 = d[코드][1]['row']
        yield from 줄들
        if len(줄들) < 1000:
            return
        쪽 += 1


def 회의목록(키):
    """PDF 번호(CONFER_NUM = pdf.do?id=) 하나가 회의 하나다(목록은 안건마다 한 줄이라 겹친다)."""
    회의 = {}
    for 갈래, 코드 in 목록.items():
        for 해 in range(첫해, int(time.strftime('%Y')) + 1):
            for r in 쪽들(갈래, 코드, {'KEY': 키, 'DAE_NUM': 대수, 'CONF_DATE': 해}):
                if r.get('PDF_LINK_URL') and str(r.get('CONF_DATE', '')).startswith(str(해)):
                    회의.setdefault(str(r['CONFER_NUM']), {
                        '갈래': 갈래, '날짜': r['CONF_DATE'], '제목': r['TITLE'],
                        'pdf': r['PDF_LINK_URL'], '보기': r.get('CONF_LINK_URL', '')})
    for 갈래, 코드 in VCONF.items():
        try:
            줄들 = list(쪽들(갈래, 코드, {'KEY': 키, 'ERACO': f'제{대수}대'}))
        except Exception as e:      # noqa: BLE001 — 덧붙인 목록 하나가 깨져도 나머지는 본다
            print(f'  {갈래} 목록 못 받음 — {e}')
            continue
        for r in 줄들:
            번호 = urllib.parse.parse_qs(urllib.parse.urlparse(r.get('DOWN_URL') or '').query).get('id', [''])[0]
            if 번호 and str(r.get('CONF_DT', '')) >= str(첫해):
                회의.setdefault(번호, {
                    '갈래': 갈래, '날짜': r['CONF_DT'],
                    '제목': f"제{대수}대 {r.get('SESS', '')} {r.get('DGR', '')} {r.get('CMIT_NM', '')} ({r.get('CONF_KND', '')})",
                    'pdf': r['DOWN_URL'],
                    '보기': f'https://record.assembly.go.kr/assembly/viewer/minutes/xml.do?id={번호}&type=summary'})
    return 회의


def 본문(pdf주소):
    with tempfile.TemporaryDirectory() as d:
        경로 = os.path.join(d, 'm.pdf')
        open(경로, 'wb').write(받기(pdf주소))
        글 = subprocess.run(['pdftotext', '-enc', 'UTF-8', 경로, '-'],
                           capture_output=True, check=True).stdout.decode('utf-8', 'replace')
    return re.sub(r'\s+', ' ', 글)


def 찾기(글, 낱말):
    return list(re.finditer(r'\s*'.join(map(re.escape, 낱말)), 글))


def 회의록(f):
    """회의록 전문 화면(웹에서 찾기로 낱말을 찾는다). 의안은 의안 화면."""
    if f['갈래'] == '의안':
        return f['보기']
    return f"https://record.assembly.go.kr/assembly/viewer/minutes/xml.do?id={f['번호']}&type=view"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--분', type=float, default=300)
    args = ap.parse_args()
    끝 = time.time() + args.분 * 60

    상태 = json.load(open(상태파일, encoding='utf-8')) if os.path.exists(상태파일) else {'본것': [], '찾은것': []}
    본것 = set(상태['본것'])
    회의 = 회의목록(keys.키읽기('ASSEMBLY_KEY'))
    남은 = sorted((n for n in 회의 if n not in 본것), key=lambda n: 회의[n]['날짜'], reverse=True)
    print(f'회의 {len(회의):,}건 · 안 본 것 {len(남은):,}건')

    def 적기():
        상태['본것'] = sorted(본것, key=int)
        os.makedirs(os.path.dirname(상태파일), exist_ok=True)
        json.dump(상태, open(상태파일, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

    for i, n in enumerate(남은):
        if time.time() > 끝:
            print(f'시간 다 됨 — {i:,}건 보고 멈춤, 다음에 이어서')
            break
        try:
            글 = 본문(회의[n]['pdf'])
        except Exception as e:      # noqa: BLE001 — 한 건이 깨져도 나머지는 본다. 본것에 안 넣으니 다음에 다시
            print(f'  {n} 못 읽음 — {e}')
            continue
        본것.add(n)
        for 낱말 in 낱말들:
            횟수 = len(찾기(글, 낱말))
            if 횟수:
                상태['찾은것'].append({**회의[n], '번호': n, '낱말': 낱말, '횟수': 횟수, '보냄': False})
                print(f'  ★ {회의[n]["날짜"]} {회의[n]["제목"]} — {낱말} {횟수}번')
        if i % 50 == 49:
            적기()

    # 의안 — 이름에 낱말이 든 것. 새로 생기거나 처리 단계(상정·의결 날짜, 계류/처리)가 바뀌면 알린다.
    의안 = 상태.setdefault('의안', {})
    for 낱말 in 낱말들:
        q = urllib.parse.urlencode({'KEY': keys.키읽기('ASSEMBLY_KEY'), 'Type': 'json', 'pIndex': 1,
                                    'pSize': 100, 'AGE': 대수, 'BILL_NAME': 낱말})
        d = json.loads(받기(f'https://open.assembly.go.kr/portal/openapi/TVBPMBILL11?{q}'))
        for r in (d['TVBPMBILL11'][1]['row'] if 'TVBPMBILL11' in d else []):
            단계 = ' · '.join(f'{이름} {r[칸]}' for 칸, 이름 in [
                ('PROPOSE_DT', '발의'), ('CMT_PRESENT_DT', '위원회 상정'), ('CMT_PROC_DT', '위원회 의결'),
                ('LAW_PROC_DT', '법사위'), ('PROC_DT', '본회의')] if r.get(칸))
            단계 += f" ({r.get('PROC_RESULT_CD') or r.get('PASS_GUBUN') or ''})"
            if 의안.get(r['BILL_ID'], {}).get('단계') != 단계:
                print(f"  ★ 의안 {r['BILL_NAME']} — {단계}")
                상태['찾은것'].append({'갈래': '의안', '날짜': time.strftime('%Y-%m-%d'), '번호': r['BILL_NO'],
                                     '제목': f"[의안] {r['BILL_NAME']} ({r['PROPOSER']}, {r.get('CURR_COMMITTEE') or ''}) — {단계}",
                                     '보기': r['LINK_URL'], '낱말': 낱말, '횟수': 1, '보냄': False})
                의안[r['BILL_ID']] = {'이름': r['BILL_NAME'], '단계': 단계}

    안보냄 = [f for f in 상태['찾은것'] if not f['보냄']]
    if 안보냄 and os.environ.get('TELEGRAM_TOKEN') and os.environ.get('TELEGRAM_CHAT_ID'):
        줄 = [f"{f['날짜']} <a href=\"{회의록(f)}\">{html.escape(f['제목'])}</a>"
             + ('' if f['갈래'] == '의안' else f" — {f['낱말']} {f['횟수']}번")
             for f in sorted(안보냄, key=lambda f: f['날짜'])]
        보내기(f"🏛 <b>국회 회의록 · {', '.join(낱말들)}</b> — 새로 {len(줄)}건\n" + '\n'.join(줄))
        for f in 안보냄:
            f['보냄'] = True
    적기()
    print(f'찾은 것 모두 {len(상태["찾은것"])}건 · 안 보낸 것 {sum(not f["보냄"] for f in 상태["찾은것"])}건')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
