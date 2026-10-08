# 국회 회의록 낱말 알림 — 22대 본회의·위원회 회의록 본문에서 낱말을 찾아 텔레그램으로 보낸다(내부용).
#
#   python scripts/watch_assembly.py              안 본 회의를 훑는다 (기본 300분에서 멈춘다)
#   python scripts/watch_assembly.py --분 10      10분만
#
# 왜 — 2026-10-06 사용자: 미래대응기금은 국회 회의록으로 봐야 한다. "22대, 올해 초부터 논의됐을 거야".
# ⚠️ 열린국회정보 API 는 **본문 검색이 없다**(회의명·안건명·날짜로만 거른다).
#    그래서 회의마다 회의록 전문 화면(HTML)을 받아 글자를 찾는다(2026-10-08 까지는 PDF — 발언을 놓쳐서 바꿈).
#    처음 한 번은 2026년 치를 다 훑느라 오래 걸리고, 그 뒤로는 날마다 새 회의 몇 건뿐이다.
# ⚠️ 줄이 바뀌면서 낱말이 끊길 수 있다(「위원\n장」) — 글자 사이 빈칸·줄바꿈을 허용해 찾는다.
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
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import keys
from watch_clik import 보내기, 보내는날

낱말들 = ['미래대응기금']
대수 = 22
첫해 = 2026        # 사용자 — "올해 초부터". 2024 로 넓히는 건 사용자가 접음(2026-10-08 — "넓혀도 안 나옴")
목록 = {'본회의': 'nzbyfwhwaoanttzje', '위원회': 'ncwgseseafwbuheph'}   # DAE_NUM + CONF_DATE(해)
# 대(ERACO)로만 거르는 회의록 목록 — 코드는 github.com/hollobit/assembly-api-mcp src/api/codes.ts 에서 찾았다.
VCONF = {'국정감사': 'VCONFAPIGCONFLIST', '국정조사': 'VCONFPIPCONFLIST', '공청회': 'VCONFPHCONFLIST',
         '인사청문회': 'VCONFCFRMCONFLIST', '청문회': 'VCONFCHCONFLIST', '소위원회': 'VCONFSUBCCONFLIST',
         '예결특위': 'VCONFBUDGETCONFLIST', '특별위원회': 'VCONFSPCCONFLIST', '연석회의': 'VCONFJMCONFLIST'}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
상태파일 = os.path.join(ROOT, 'data', 'assembly', '알림.json')
UA = {'User-Agent': 'Mozilla/5.0'}


def 받기(url, 초=120, 되풀이=4):
    """시간 초과·끊김·5xx 는 30·60·90초 쉬고 다시(2026-10-08 목록 받다 시간 초과로 못 보낸 일). 4xx 는 바로 낸다."""
    for n in range(되풀이):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=초) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code < 500 or n == 되풀이 - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if n == 되풀이 - 1:
                raise
        time.sleep(30 * (n + 1))


def 오늘():
    return time.strftime('%Y-%m-%d', time.gmtime(time.time() + 9 * 3600))   # 한국 날짜


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


def 본문(번호):
    """회의록 전문 화면(HTML)의 글자. ⚠️ PDF 는 쓰지 않는다 — 2026-10-08 확인: 9/14 본회의 대정부질문이
    웹 13번인데 PDF(pdftotext) 3번, 9/7 교섭단체 대표연설은 웹 4번 · PDF 1번. PDF 가 발언을 다 담지 않는다."""
    h = 받기(f'https://record.assembly.go.kr/assembly/viewer/minutes/xml.do?id={번호}&type=view').decode('utf-8', 'replace')
    h = re.sub(r'(?is)<(script|style)\b.*?</\1>', ' ', h)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h)))


def 찾기(글, 낱말):
    return list(re.finditer(r'\s*'.join(map(re.escape, 낱말)), 글))


def 회의록(f):
    """회의록은 전문 화면(웹에서 찾기로 낱말을 찾는다). 의안·자료는 그 화면."""
    if 'pdf' not in f:
        return f['보기']
    return f"https://record.assembly.go.kr/assembly/viewer/minutes/xml.do?id={f['번호']}&type=view"


# 제목으로 거르는 자료 — 2026-10-08 사용자: "미래대응기금은 나올 수 있는 거 다". 이름 · 코드 · 제목 칸 · 날짜 칸 · 링크 칸.
# 예산정책처·입법조사처는 그날 「미래대응」 0건이었다(나오면 알린다).
# 서면질의답변서는 제목 거르개가 안 먹어 전부(3천여 건) 받는다 — 아래에서 제목에 낱말이 있나 다시 본다.
#   본회의 회의록의 「1번」이 대개 이것(보고사항의 「미래대응기금에 관한 질문서에 대한 답변서」 한 줄)이다.
제목자료 = [('서면질의·답변서', 'VCONFATTQNALIST', 'FILE_CN', 'CONF_DT', 'DOWN_URL'),
          ('보도자료', 'ninnagrlaelvtzfnt', 'TITLE', 'WRITE_DATE', 'CONTENT_URL'),
          ('입법조사처', 'ALLNARSPBLM', 'MTR_TTL', 'WRT_DT', 'LINK_URL')] + [
    (f'예산정책처 {이름}', 코드, 'SUBJECT', 'REG_DATE', 'LINK_URL') for 이름, 코드 in [
        ('예산 분석', 'nxeytfqvawilyincp'), ('결산 분석', 'negjnychalvyrcifv'), ('비용추계', 'npsofwddayuhqhfgh'),
        ('재정동향', 'nsjmwljyauxvdodgh'), ('재정사업 평가', 'nzjvrirbauqmffblj'), ('Focus', 'npbizvcmabezbhcez'),
        ('경제정책', 'nlugechzaowgqlopk'), ('지방재정', 'naqdzohuagtisumcw'), ('예산춘추', 'nbxjdyrjaommhkiza')]]
갈래차례 = ['의안', '본회의', '위원회'] + list(VCONF) + [x[0] for x in 제목자료]


# 보도자료는 2026-10-01 부터만 — 사용자(2026-10-08).
보도부터 = '2026-10-01'


def 모으기(상태, 본것, 끝, 적기):
    """국회 서버에서 회의록·의안·제목자료를 훑어 상태['찾은것'] 에 더한다."""
    회의 = 회의목록(keys.키읽기('ASSEMBLY_KEY'))
    남은 = sorted((n for n in 회의 if n not in 본것), key=lambda n: 회의[n]['날짜'], reverse=True)
    print(f'회의 {len(회의):,}건 · 안 본 것 {len(남은):,}건')

    for i, n in enumerate(남은):
        if time.time() > 끝:
            print(f'시간 다 됨 — {i:,}건 보고 멈춤, 다음에 이어서')
            break
        try:
            글 = 본문(n)
        except Exception as e:      # noqa: BLE001 — 한 건이 깨져도 나머지는 본다. 본것에 안 넣으니 다음에 다시
            print(f'  {n} 못 읽음 — {e}')
            continue
        본것.add(n)
        for 낱말 in 낱말들:
            횟수 = len(찾기(글, 낱말))
            if 횟수:
                있던 = next((f for f in 상태['찾은것'] if f.get('번호') == n and f['낱말'] == 낱말), None)
                if 있던:
                    있던['횟수'] = 횟수
                    continue
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

    # 보도자료·보고서 — 제목에 낱말이 든 것. 링크로 한 번만.
    자료본것 = set(상태.setdefault('자료본것', []))
    for 이름, 코드, 제목칸, 날짜칸, 링크칸 in 제목자료:
        for 낱말 in 낱말들:
            try:
                줄들 = list(쪽들(이름, 코드, {'KEY': keys.키읽기('ASSEMBLY_KEY'), 제목칸: 낱말}))
            except Exception as e:      # noqa: BLE001
                print(f'  {이름} 못 받음 — {e}')
                continue
            for r in 줄들:
                if (r.get(링크칸) and r[링크칸] not in 자료본것 and 낱말 in (r.get(제목칸) or '')
                        and not (이름 == '보도자료' and str(r.get(날짜칸) or '')[:10] < 보도부터)):
                    자료본것.add(r[링크칸])
                    상태['찾은것'].append({'갈래': 이름, '날짜': str(r.get(날짜칸) or '')[:10], '번호': r[링크칸],
                                         '제목': html.unescape(r[제목칸]), '보기': r[링크칸],
                                         '낱말': 낱말, '횟수': 1, '보냄': False})
                    print(f"  ★ {이름} {r[제목칸]}")
    상태['자료본것'] = sorted(자료본것)



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--분', type=float, default=300)
    ap.add_argument('--다시보내기', action='store_true', help='찾은 것 전부를 다시 보낸다')
    ap.add_argument('--마지막시도', action='store_true',
                    help='낮 재시도 — 아침에 이미 됐으면 그냥 끝, 아니면 훑고 못 해도 「못 봤음」을 보낸다')
    args = ap.parse_args()
    끝 = time.time() + args.분 * 60

    상태 = json.load(open(상태파일, encoding='utf-8')) if os.path.exists(상태파일) else {'본것': [], '찾은것': []}
    if 상태.get('본문') != 'html':   # PDF 로 훑던 것은 한 번 처음부터 다시 본다(이미 찾은 회의는 횟수만 고친다)
        상태['본것'], 상태['본문'] = [], 'html'
    본것 = set(상태['본것'])

    def 적기():
        상태['본것'] = sorted(본것, key=int)
        os.makedirs(os.path.dirname(상태파일), exist_ok=True)
        json.dump(상태, open(상태파일, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

    if args.다시보내기:   # 보내기만 — 국회 서버를 부르지 않는다(2026-10-08 목록 받다 시간 초과로 못 보냄)
        for f in 상태['찾은것']:
            f['보냄'] = False
    # 아침에 못 하면 조용히 넘기고 낮(--마지막시도)에 한 번 더 — 「못 봤음」은 낮에도 안 될 때만(사용자: 서버 문제로 못 보는 일은 없어야).
    if args.마지막시도 and 상태.get('마지막성공') == 오늘():
        print('오늘 아침에 이미 됐다 — 낮 재시도 안 함')
        return
    오류 = None
    if not args.다시보내기:
        try:
            모으기(상태, 본것, 끝, 적기)
            상태['마지막성공'] = 오늘()
        except Exception as e:      # noqa: BLE001
            오류 = e
            print(f'  훑다 멈춤 — {e}')
            if not args.마지막시도:
                적기()
                print('낮에 다시 본다 — 지금은 보내지 않는다')
                return
    상태['찾은것'] = [f for f in 상태['찾은것'] if not (f['갈래'] == '보도자료' and f['날짜'] < 보도부터)]
    if not args.다시보내기 and not 보내는날():
        적기()   # 찾은 것은 「안 보냄」으로 남아 다음 평일에 간다
        print('쉬는 날 — 안 보낸다(다음 평일에 몰아서)')
        return
    안보냄 = [f for f in 상태['찾은것'] if not f['보냄']]
    머리 = f"🏛 <b>국회 · {', '.join(낱말들)}</b>"
    꼬리 = f"\n⚠️ 국회 서버가 응답하지 않아 다 못 훑었습니다 — 내일 이어서 봅니다." if 오류 else ''
    열쇠있음 = os.environ.get('TELEGRAM_TOKEN') and os.environ.get('TELEGRAM_CHAT_ID')
    if not 안보냄 and 열쇠있음:   # 2026-10-08 사용자: 새것이 없으면 없다고 보낸다
        보내기(f"{머리} — ⚠️ 오늘은 국회 서버가 응답하지 않아 못 봤습니다. 내일 다시 봅니다." if 오류
             else f"{머리} — 오늘 새로 걸린 것 없음")
    if 안보냄 and 열쇠있음:
        글 = f"{머리} — 새로 {len(안보냄)}건{꼬리}"
        for 갈 in sorted({f['갈래'] for f in 안보냄}, key=lambda g: 갈래차례.index(g) if g in 갈래차례 else 99):
            묶 = sorted((f for f in 안보냄 if f['갈래'] == 갈), key=lambda f: f['날짜'], reverse=True)
            글 += f"\n\n<b>{html.escape(갈)}</b> {len(묶)}건\n" + '\n'.join(
                f"{f['날짜']} <a href=\"{회의록(f)}\">{html.escape(f['제목'])}</a>"
                + (f" — {f['횟수']}번" if 'pdf' in f else '') for f in 묶)
        보내기(글)
        for f in 안보냄:
            f['보냄'] = True
    적기()
    print(f'찾은 것 모두 {len(상태["찾은것"])}건 · 안 보낸 것 {sum(not f["보냄"] for f in 상태["찾은것"])}건')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
