# 국회 회의록 낱말 알림 — 22대 본회의·위원회 회의록 PDF 본문에서 낱말을 찾아 텔레그램으로 보낸다(내부용).
#
#   python scripts/watch_assembly.py              안 본 회의를 훑는다 (기본 300분에서 멈춘다)
#   python scripts/watch_assembly.py --분 10      10분만
#
# 왜 — 2026-10-06 사용자: 미래대응기금은 국회 회의록으로 봐야 한다. "22대, 올해 초부터 논의됐을 거야".
# ⚠️ 열린국회정보 API 는 **본문 검색이 없다**(회의명·안건명·날짜로만 거른다).
#    그래서 회의마다 PDF(1~2MB)를 받아 pdftotext 로 글자를 뽑아 찾는다. 한 회의에 몇 초.
#    처음 한 번은 2026년 치를 다 훑느라 몇 시간 걸리고, 그 뒤로는 날마다 새 회의 몇 건뿐이다.
# ⚠️ PDF 는 줄이 바뀌면서 낱말이 끊긴다(「위원\n장」) — 빈칸·줄바꿈을 다 지우고 찾는다.
#
# 열쇠 — ASSEMBLY_KEY(열린국회정보) · TELEGRAM_TOKEN · TELEGRAM_CHAT_ID. 공개 저장소라 값은 안 적는다.
# 텔레그램 열쇠가 없으면 찾은 것을 「안 보냄」으로 쌓아 두었다가 열쇠가 생기면 그때 보낸다.

import argparse
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
목록 = {'본회의': 'nzbyfwhwaoanttzje', '위원회': 'ncwgseseafwbuheph'}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
상태파일 = os.path.join(ROOT, 'data', 'assembly', '알림.json')
UA = {'User-Agent': 'Mozilla/5.0'}


def 받기(url, 초=120):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=초) as r:
        return r.read()


def 회의목록(키):
    """CONFER_NUM 하나가 회의 하나다(목록은 안건마다 한 줄이라 겹친다)."""
    회의 = {}
    for 갈래, 코드 in 목록.items():
        for 해 in range(첫해, int(time.strftime('%Y')) + 1):
            쪽 = 1
            while True:
                q = urllib.parse.urlencode({'KEY': 키, 'Type': 'json', 'pIndex': 쪽, 'pSize': 1000,
                                            'DAE_NUM': 대수, 'CONF_DATE': 해})
                d = json.loads(받기(f'https://open.assembly.go.kr/portal/openapi/{코드}?{q}'))
                if 코드 not in d:       # INFO-200 = 더 없음. 다른 코드는 오류다.
                    if d.get('RESULT', {}).get('CODE') != 'INFO-200':
                        raise RuntimeError(f'{갈래} {해} {쪽}쪽: {d.get("RESULT")}')
                    break
                줄들 = d[코드][1]['row']
                for r in 줄들:
                    if r.get('PDF_LINK_URL') and str(r.get('CONF_DATE', '')).startswith(str(해)):
                        회의.setdefault(str(r['CONFER_NUM']), {
                            '갈래': 갈래, '날짜': r['CONF_DATE'], '제목': r['TITLE'],
                            'pdf': r['PDF_LINK_URL'], '보기': r.get('CONF_LINK_URL', '')})
                if len(줄들) < 1000:
                    break
                쪽 += 1
    return 회의


def 본문(pdf주소):
    with tempfile.TemporaryDirectory() as d:
        경로 = os.path.join(d, 'm.pdf')
        open(경로, 'wb').write(받기(pdf주소))
        글 = subprocess.run(['pdftotext', '-enc', 'UTF-8', 경로, '-'],
                           capture_output=True, check=True).stdout.decode('utf-8', 'replace')
    return re.sub(r'\s+', '', 글)


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
            if 글.count(낱말):
                상태['찾은것'].append({**회의[n], '번호': n, '낱말': 낱말, '횟수': 글.count(낱말), '보냄': False})
                print(f'  ★ {회의[n]["날짜"]} {회의[n]["제목"]} — {낱말} {글.count(낱말)}번')
        if i % 50 == 49:
            적기()

    안보냄 = [f for f in 상태['찾은것'] if not f['보냄']]
    if 안보냄 and os.environ.get('TELEGRAM_TOKEN') and os.environ.get('TELEGRAM_CHAT_ID'):
        줄 = [f"{f['날짜']} <a href=\"{f['보기']}\">{f['제목']}</a> — {f['낱말']} {f['횟수']}번"
             for f in sorted(안보냄, key=lambda f: f['날짜'])]
        보내기(f"🏛 <b>국회 회의록 · {', '.join(낱말들)}</b> — 새로 {len(줄)}건\n" + '\n'.join(줄))
        for f in 안보냄:
            f['보냄'] = True
    적기()
    print(f'찾은 것 모두 {len(상태["찾은것"])}건 · 안 보낸 것 {sum(not f["보냄"] for f in 상태["찾은것"])}건')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
