# 예산안 공개 재기 — 「의회엔 냈는데 시민은 못 본다」(README 「숨기나」 표).
# 2026-10-28 사용자 「일단 안 보이는 것부터 재고 안 보이는 것은 내가 눈으로 볼게」.
#
#   python scripts/report_budget_proposal.py --긁기    243곳 예산서 게시판을 새로 긁고(한 시간 안팎) 가른다 — 11/24 쯤(시군구 제출 마감 11/21 뒤)
#   python scripts/report_budget_proposal.py --의회    의회 회의록 부록을 새로 훑고(몇 분) 게시판 긁은 것과 합쳐 가른다 — 12/15 쯤
#   python scripts/report_budget_proposal.py           긁어 둔 것으로 가르기만
#   python scripts/report_budget_proposal.py 2026 data/budget_docs.json --의회    작년치로 시험
#   python scripts/report_budget_proposal.py --selftest
#
# 보임 = ① 자치단체 예산서 게시판(지방재정365 BUDLK, check_budget_docs.js 가 긁는 곳) 글 제목에 그 해 본예산(안)이 있거나
#        ② 의회 회의록 「관련부록」에 그 해 예산안 책자(설명서·명세서·예산서, 또는 1MB 넘는 예산안 파일)가 붙었다.
#   ① 은 게시판 한 겹만 본다(「예산안 공개」 메뉴 안쪽·보도자료는 안 본다).
#   ② 는 마포 틀 회의록(/record/committeeThList.do 가 JSON)을 쓰는 의회만 — 2026-10-28 에 20곳. 나머지는 「안 봄」.
#      작년치: 책자 붙은 곳 보은 11/25·음성 12/2·마포 12/10·거창 12/12 — 그래서 의회 쪽은 12월 중순에 훑는다.
#   그래서 「안 보임」은 「자동으로 못 찾음」이다 → 안 보임 목록(html)을 사람이 열어 본다.
# 의회에 낸 날 = CLIK 에 그 해 예산안(시정연설·수정안 포함)이 처음 오른 날. CLIK 에 안 올라오는 의회가 80곳 남짓이라 빈칸 ≠ 안 냄.
#   ⚠️ 의회마다 ITNC_DE 가 접수일이기도 처리일이기도 하다(2026-10-28 작년치: 군산 12-19 「원안가결」) — 법정 기한 지켰나는 이걸로 못 가린다.
# 결과: data/budget_proposal.json · %LOCALAPPDATA%/local-finance-files/예산안_눈으로볼것.html
import gzip
import html
import http.cookiejar
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from build_clik import ROOT, compile_rows, load_places

밖 = Path(os.environ.get('LOCALAPPDATA', ROOT)) / 'local-finance-files'
OUT = ROOT / 'data' / 'budget_proposal.json'


def 예산안글(t, 해):
    """게시판 글 제목이 그 해 본예산(안)인가."""
    return bool(re.search(rf'{해}|{str(해)[2:]}년', t) and re.search(r'예산\s*\(\s*안\s*\)|예산안|\(안\)', t)
                and not re.search(r'추가경정|추경|결산|안내|기금|성과|성인지|기후|온실|의견|주민참여|설명회|공청회', t))


def 칸만(t):
    """해 없이 「예산안 공개」 같은 칸(메뉴)만 있는 것 — 안에 들어가야 보인다."""
    return bool(re.search(r'예산\s*\(\s*안\s*\)|예산안', t) and not re.search(r'20\d\d|\d\d년|안내|처리절차|주민참여|추가경정|추경', t))


def 의회예산안(t, 해):
    """CLIK 의안 제목이 그 해 본예산안인가(교육비특별회계·출연금 동의안 빼고)."""
    return bool(re.search(rf'{해}년도?', t) and re.search(r'예산\s*\(?안', t)
                and not re.search(r'추가경정|추경|동의|출연|기금|결산|교육', t))


def 부록갈래(t, 해):
    """회의록 부록 제목 → 책자 / 예산안(작으면 표지) / 검토·심사보고서 / 수정·삭감 / None."""
    if not re.search(rf'{해}|{str(해)[2:]}년', t) or '예산' not in t or re.search(r'추가경정|추경|결산|기금', t):
        return None
    if re.search(r'검토보고|심사보고', t):
        return '검토·심사보고서'
    if re.search(r'수정|삭감|계수조정', t):
        return '수정·삭감'
    return '책자' if re.search(r'설명서|명세서|예산서|사업예산', t) else '예산안'


def 고른대(대들, 해):
    """그 해 예산안을 심사한 대 — 시작이 전년 11월보다 늦지 않은 대 가운데 가장 늦은 것(2026 예산안 = 9대, 2027 = 10대)."""
    후보 = [t['th'] for t in 대들 if (m := re.search(r'\((\d{4}\.\d\d)', t.get('title', ''))) and m.group(1) <= f'{해 - 1}.11']
    return max(후보, default=None)


def 의회훑기(해):
    """마포 틀 회의록 의회: 전년 11~12월 예결특위·상임위 회의록의 그 해 예산안 부록 → {laf_cd: {주소, 찾음, 오류} | None(안 봄)}."""
    곳 = json.loads((ROOT / 'data/boards_council.json').read_text(encoding='utf-8'))['곳']
    H = {'User-Agent': 'Mozilla/5.0', 'X-Requested-With': 'XMLHttpRequest'}

    def 한곳(item):
        cd, v = item
        m = re.match(r'https?://[^/]+', v.get('첫화면') or '')
        if not m:
            return cd, None
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        글 = lambda B, p, **d: op.open(urllib.request.Request(B + p + ('?' + urllib.parse.urlencode(d) if d else ''), headers=H), timeout=60).read().decode('utf-8', 'replace')
        for B in dict.fromkeys([m.group(0).replace('http://', 'https://'), m.group(0)]):
            try:
                대E = json.loads(글(B, '/record/committeeThList.do', code='E'))
            except Exception:
                continue
            if 대E:   # 강동·군산·서초 등은 같은 틀인데 빈 목록([])을 준다(2026-10-28) — 못 훑음
                break
        else:
            return cd, None   # 마포 틀이 아니거나 목록이 비었다
        g = lambda p, **d: json.loads(글(B, p, **d))
        찾음, 오류 = [], ''
        try:
            cid, th = 대E[0]['councilId'], 고른대(대E, 해)
            회기 = [dict(s, code=s['code']) for s in g('/record/committeeSessionList.do', councilId=cid, th=th, code='E')]
            for c in g('/record/committeeCommitteeList.do', councilId=cid, th=th, code='C'):
                회기 += g('/record/committeeSessionList.do', councilId=cid, th=th, code=c['code'])
            for s in 회기:
                if not re.search(rf'{해 - 1}\.1[12]', s.get('title', '')):
                    continue
                for o in g('/record/orderList.do', councilId=cid, th=th, session=s['session'], code=s['code']):
                    mm = re.search(r"href=['\"]([^'\"]+)['\"].*?>([^<]+)</a>", o['title'], re.S)
                    if not mm:
                        continue
                    날 = (re.search(r'20\d\d\.\d\d\.\d\d', mm.group(2)) or [''])[0].replace('.', '-')
                    for key, ti in re.findall(r'appendixDownload\.do\?key=([0-9a-f]+)"[^>]*title="([^"]*)"', 글(B, mm.group(1))):
                        k = 부록갈래(ti, 해)
                        if not k:
                            continue
                        크기 = 0
                        if k in ('책자', '예산안'):   # 몸은 안 받고 머리의 크기만 — 표지(수십~수백 KB)와 책자를 가른다
                            with op.open(urllib.request.Request(B + '/record/appendixDownload.do?key=' + key, headers=H), timeout=60) as f:
                                크기 = int(f.headers.get('Content-Length') or 0)
                            if k == '예산안' and 크기 > 1_000_000:
                                k = '책자'
                        찾음.append([날, k, ti.strip()[:80], 크기])
        except Exception as e:
            오류 = str(e)[:80]
        return cd, {'주소': B, '찾음': 찾음, '오류': 오류}

    with ThreadPoolExecutor(5) as ex:
        return dict(ex.map(한곳, 곳.items()))


def 의회칸(회):
    if 회 is None:
        return '안 봄', ''
    책자날 = min((a[0] for a in 회['찾음'] if a[1] == '책자'), default='')
    if 책자날:
        return f'책자 {책자날}', 책자날
    if 회['오류'] and not 회['찾음']:
        return '오류', ''
    return ' · '.join(sorted({a[1] for a in 회['찾음']})) or '부록 없음', ''


def 시험():
    assert 부록갈래('1-2. 2026년도 사업예산안Ⅰ(사업설명서)', 2026) == '책자'
    assert 부록갈래('2026 본예산 명세서', 2026) == '책자'
    assert 부록갈래('1. 2026년도 서울특별시 마포구 예산안', 2026) == '예산안'
    assert 부록갈래('2026년도 예산안 검토보고서', 2026) == '검토·심사보고서'
    assert 부록갈래('7. 2026년 본예산 삭감조서(재정문화위원회)', 2026) == '수정·삭감'
    assert 부록갈래('2025년도 제3회 추가경정예산안', 2026) is None
    assert 부록갈래('2027년도 예산안', 2026) is None
    대 = [{'th': 10, 'title': '제10대(2026.07.01 ~ 2030.06.30 : 제352회 이후)'}, {'th': 9, 'title': '제9대(2022.07.01 ~ 2026.06.30 : 제313회 ~ 제351회)'}]
    assert 고른대(대, 2026) == 9 and 고른대(대, 2027) == 10
    assert 예산안글('2027년도 예산(안)', 2027)
    assert 예산안글('2027 본예산(안) 사업명세서', 2027)
    assert 예산안글('27년 예산안 공개', 2027)
    assert not 예산안글('2026년도 예산(안)', 2027)
    assert not 예산안글('2027년도 제1회 추가경정예산(안)', 2027)
    assert not 예산안글('2027년 예산안 편성 주민의견 수렴', 2027)
    assert 칸만('예산안 공개') and 칸만('본예산(안)')
    assert not 칸만('예산안내') and not 칸만('예산안 처리절차') and not 칸만('주민참여예산안내')
    assert 의회예산안('2027년도 서울특별시 마포구 예산안', 2027)
    assert 의회예산안('2027년도 일반 및 특별회계 세입·세출 예산안(시장제출)', 2027)
    assert not 의회예산안('2027년도 사천시 복지·청소년재단 출연금 예산편성 동의안', 2027)
    assert not 의회예산안('2027년도 대구광역시교육비특별회계 예산안', 2027)
    print('시험 통과')


def 화면(줄, 해, 긁은날, 의회날):
    a = lambda u, t: f'<a href="{html.escape(u)}" target="_blank">{html.escape(t)}</a>' if u else ''
    차례 = {'안 보임': 0, '못 봄': 1, '보임': 2}
    행 = ''.join(
        f'<tr class="{"ok" if r["판정"] == "보임" else ""}"><td>{html.escape(r["이름"])}</td><td>{r["판정"]}'
        f'{" · 예산안 칸 있음" if r["예산안칸"] else ""}</td><td>{r["의회에낸날"] or "-"}</td><td>{r["의회회의록"]}</td>'
        f'<td>{a(r["게시판"], "예산서 게시판")}</td><td>{a(r["의회"], "의회")}</td><td>{a(r["주소"], r["글"])}</td></tr>'
        for r in sorted(줄, key=lambda r: (차례[r['판정']], r['laf_cd'])))
    return (f'<!doctype html><meta charset="utf-8"><title>{해}년도 예산안 — 눈으로 볼 것</title>'
            '<style>body{font:14px sans-serif;margin:16px}table{border-collapse:collapse}td{border:1px solid #ccc;padding:4px 8px}'
            'tr.ok{color:#888}</style>'
            f'<h1>{해}년도 예산안 — 눈으로 볼 것</h1><p>게시판 긁은 날 {긁은날} · 의회 회의록 훑은 날 {의회날 or "-"}. '
            '「안 보임」= 예산서 게시판 글 제목에서도, 의회 회의록 부록에서도 책자를 자동으로 못 찾음. '
            '「예산안 칸 있음」= 게시판에 예산안 메뉴가 있는데 안에는 안 들어가 봄. 의회 회의록 「안 봄」= 그 의회는 자동으로 못 훑는 시스템. '
            '맨 아래 회색 「보임」은 맞게 잡았는지 훑어볼 것.</p>'
            f'<table><tr><td>곳</td><td>판정</td><td>CLIK에 처음 오른 날</td><td>의회 회의록 부록</td><td></td><td></td><td>잡힌 글</td></tr>{행}</table>')


def main():
    인자 = sys.argv[1:]
    if '--selftest' in 인자:
        return 시험()
    해 = next((int(a) for a in 인자 if re.fullmatch(r'20\d\d', a)), date.today().year + 1)
    원 = next((Path(a) for a in 인자 if a.endswith('.json')), 밖 / 'budget_proposal_raw.json')
    if '--긁기' in 인자:
        subprocess.run(['git', 'pull', '-q', '--rebase', '--autostash'], cwd=ROOT)   # 봇이 올린 CLIK 의안까지
        밖.mkdir(exist_ok=True)
        subprocess.run(['node', 'scripts/check_budget_docs.js', '--out', str(원)], cwd=ROOT, check=True)
    긁음 = json.loads(원.read_text(encoding='utf-8'))
    의회 = json.loads((ROOT / 'data/boards_council.json').read_text(encoding='utf-8'))['곳']
    회의록파일 = 밖 / f'budget_proposal_council_{해}.json'
    if '--의회' in 인자:
        밖.mkdir(exist_ok=True)
        회의록파일.write_text(json.dumps({'만든날': date.today().isoformat(), '곳': 의회훑기(해)}, ensure_ascii=False), encoding='utf-8')
    회의록 = json.loads(회의록파일.read_text(encoding='utf-8')) if 회의록파일.exists() else {'만든날': '', '곳': {}}

    의안 = []
    for p in sorted((ROOT / 'data/clik').glob('의안_*.json.gz')):
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            의안 += [r for r in json.load(f) if 의회예산안(r.get('BI_SJ', ''), 해)]
    clik, _ = compile_rows(load_places(), json.loads((ROOT / 'data/clik/의회목록.json').read_text(encoding='utf-8')), {'의안': 의안})

    줄 = []
    for x in 긁음['곳']:
        e = x.get('예산') or {}
        보임 = [g for g in e.get('목록글') or [] if 예산안글(g['글'], 해)]
        칸 = [g for g in e.get('목록글') or [] if 칸만(g['글'])]
        잡힘 = (보임 or 칸 or [{}])[0]
        회의록칸, 책자날 = 의회칸(회의록['곳'].get(x['laf_cd']))
        줄.append({'laf_cd': x['laf_cd'], '이름': x['이름'],
                   '판정': '보임' if 보임 or 책자날 else '못 봄' if not e.get('코드') or e.get('실패') else '안 보임',
                   '어디서': ' · '.join(k for k, v in (('게시판', 보임), ('의회 회의록', 책자날)) if v), '의회회의록': 회의록칸,
                   '예산안칸': bool(칸) and not 보임, '글': 잡힘.get('글', ''), '주소': 잡힘.get('주소', ''),
                   '게시판': e.get('주소') or '', '의회': 의회.get(x['laf_cd'], {}).get('첫화면', ''),
                   '의회에낸날': min((r['날짜'] for r in clik.get(x['laf_cd'], {}).get('의안', []) if r['날짜']), default='')})
    셈 = {k: sum(r['판정'] == k for r in 줄) for k in ('보임', '안 보임', '못 봄')}
    셈['의회에 냄(CLIK)'] = sum(bool(r['의회에낸날']) for r in 줄)
    셈['의회 회의록 훑음'] = sum(r['의회회의록'] != '안 봄' for r in 줄)
    셈['의회 회의록 책자'] = sum(r['의회회의록'].startswith('책자') for r in 줄)
    OUT.write_text(json.dumps({'만든날': date.today().isoformat(), '해': 해, '긁은날': 긁음.get('만든날'), '의회훑은날': 회의록['만든날'],
                               '셈': 셈, '곳': 줄}, ensure_ascii=False, indent=0), encoding='utf-8')
    밖.mkdir(exist_ok=True)
    (밖 / '예산안_눈으로볼것.html').write_text(화면(줄, 해, 긁음.get('만든날'), 회의록['만든날']), encoding='utf-8')
    print(해, 셈, '→', OUT, '·', 밖 / '예산안_눈으로볼것.html')


if __name__ == '__main__':
    main()
