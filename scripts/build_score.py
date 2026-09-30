# 「공개 평가」 화면을 굽는다 — 함께하는 시민행동이 정한 평가안(정량 14 · 정성 2)을 243곳에 대 본다.
#
#   node scripts/check_budget_docs.js       (예산서·결산서 게시판을 크롬으로 — 한 시간 안팎)
#   python scripts/build_score.py           → data/score.json · site/score.html
#
# 근거를 모으는 곳 넷 —
#   ① data/budget_docs.json   예산서·결산서 게시판의 글 제목·붙은 파일(check_budget_docs.js)
#   ② data/disclosure_dom.json 재정공시 글에 붙은 파일(recheck_disclosure.js) — 공시 의무 항목에
#      성인지 예결산서·중기지방재정계획·주민의견서가 들어 있다(지방재정법 제60조, 시행령)
#   ③ 지방재정365 API — 중기계획(FDHHH)·성인지 예산(BQBRB)·성인지 결산(DIZFMP). 숫자가 올라왔다는 뜻이지
#      자치단체가 문서를 공개했다는 뜻은 아니다 — 판정에는 안 쓰고 곁에 적기만 한다
#   ④ data/score_hand.json    사람이 확인한 것(자동보다 앞선다). 정성 2항목 점수도 여기 적는다
#
# ⭐ 판정은 셋이다. ○ 찾았다 · ? 못 찾았다(없다는 뜻이 아니다) · × 본 것으로는 아니다(파일 형식 두 항목만).
#    「못 찾았다」를 「없다」로 쓰지 않는다 — 자동이 못 들어간 게시판이 섞여 있다.
# ⭐ 잣대(무슨 글자가 보이면 ○ 인가)는 아래 항목표에 모았다. 잣대를 바꾸면 다시 긁지 않고 이것만 다시 돌린다.

import json
import os
import re
import sys
from datetime import date
from urllib.parse import urlparse

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, 'site')

# 공청회·공론장 — 자동으로 찾을 수 없는 까닭(2026-09-30 조사). 화면에 그대로 싣는다
공청회까닭 = [
    '전국을 모은 곳이 없다 — 행정절차법 제38조는 공청회 14일 전에 관보·공보·누리집·신문 <b>가운데 하나</b>로 알리게 할 뿐이라, '
    '공고가 243곳 누리집의 고시·공고 게시판에 흩어진다.',
    '지방재정법 시행령 제46조는 공청회를 주민참여 방법 <b>가운데 하나</b>로 둘 뿐이고, 수렴한 의견은 예산에 「반영할 수 있다」에 그친다 — 공개할 의무가 없다.',
    '행정안전부 「지방재정 투자심사 및 타당성조사 운영기준」(2025) 은 심사에서 「주민·전문가 의견수렴 이행 여부 ★ '
    '(기피시설은 공청회 등 의견수렴 절차 여부 반드시 확인)」을 본다. 그러나 그것이 적힌 <b>심사 의뢰서는 공개되지 않고</b>, '
    '공개되는 결과표(우리가 받은 26개 파일, 2,011건)에는 사업명·사업비·판정만 있다 — 「공청회」·「주민의견」 0건.',
    '지방의회 회의록 목록(CLIK, 2022-07 이후 135,627건)의 회의 이름에도 「공청회」는 0건이다. 의회가 연 것이 아니면 의회 기록에 남지 않는다.',
    '일부만 모아 둔 곳 — 환경영향평가 대상 사업의 주민설명회·공청회는 환경영향평가정보지원시스템(eiass.go.kr)에 모인다. '
    '큰 사업 일부만 해당된다.',
]

# 항목표 — [키, 갈래, 이름, 어디를 보나, 잣대(정규식) 또는 None(자동 판정 안 함)]
항목 = [
    # 「이월명세서」·「반납명세서」(결산 부속)는 빼려고 사업·세부·예산 명세서만 본다. 「예산서」만 보이면 아래에서 따로 ○(근거에 밝힘)
    ('명세서', '예결산안 공개', '예산세부명세서', '예산', r'사업\s*별?\s*명세서|세부\s*명세서|예산\s*명세서'),
    # 「용인사용설명서」 같은 누리집 안내, 「기금운용계획 변경내용 설명서」는 뺀다
    ('설명서', '예결산안 공개', '예산설명서', '예산', r'사업\s*별?\s*설명서|예산\s*(사업)?\s*설명서'),
    ('결산서', '예결산안 공개', '결산서', '결산', r'결산서|세입\s*[·ㆍ.]?\s*세출\s*결산'),
    ('성인지', '예결산안 공개', '성인지 예결산서', '둘+공시', r'성인지'),
    ('중기', '예결산안 공개', '중기지방재정계획', '둘+공시', r'중기\s*(지방)?\s*재정\s*계획|중기재정'),
    ('일일', '예산안 공개방식', '일일 예산집행 공개', None, None),
    ('별도', '예산안 공개방식', '자체 예산 사이트 운영', '주소', None),
    ('예산형식', '예산안 공개방식', '예산서 파일이 활용 가능한 형식인가', '예산', None),
    ('결산형식', '예산안 공개방식', '결산서 파일이 활용 가능한 형식인가', '결산', None),
    ('공청회', '시민참여', '큰 사업 전 주민공청회', None, None),
    ('전체명세', '시민참여', '의회에 낸 예산안에 명세서 전체가 들었나', None, None),
    # 「결산검사의견서」는 주민 의견서가 아니다
    ('의견서', '시민참여', '주민참여예산 주민의견서 공개', '예산+공시', r'주민\s*(참여\s*예산\s*)?의견서|참여\s*예산\s*(사업\s*)?(주민\s*)?의견서'),
    ('기후', '예산안의 ESG', '기후예산서 제출', '둘', r'기후\s*(대응|변화)?\s*(적응)?\s*예산|온실가스\s*감축\s*인지|탄소\s*인지|기후\s*예산'),
    ('공론장', '예산안의 ESG', '대규모 사업 공론장 운영', None, None),
]
정성 = [
    ('연례설명', '예결산안 공개', '예산설명서 — 연례사업 설명서가 모두 공개되나'),
    ('사전공개', '예결산안 공개', '예산안 — 의회를 통해 시민에게 충분히 미리 공개되나'),
]
못함 = {
    '일일': '자치단체 누리집의 일일 집행 공개는 자동으로 가리지 못했다. 지방재정365 는 243곳 모두의 세부사업별 집행을 날마다 싣는다'
           '(이 사이트의 「진행 중인 사업」) — 전국 공통이라 자치단체를 가르는 잣대가 되지 않는다. 사람이 누리집에서 확인할 칸.',
    '공청회': '자동으로 찾을 수 없다 — 아래 「공청회·공론장을 못 찾는 까닭」.',
    '공론장': '자동으로 찾을 수 없다 — 아래 「공청회·공론장을 못 찾는 까닭」.',
    '전체명세': '의회에 낸 예산안과 공개된 예산서를 한 장씩 맞대 봐야 한다. 사람이 볼 칸.',
}
엑셀 = re.compile(r'\.(xlsx?|csv)(\W|$)', re.I)
문서 = re.compile(r'\.(pdf|hwpx?|zip|docx?)(\W|$)', re.I)
별도주소 = re.compile(r'budget|finance|openfinance|jaejung|jaejeong|money|fiscal|openbudget|예산', re.I)


def 글자들(판):
    """한 판(예산 또는 결산)에서 근거가 될 글자 — (글자, 어디서, 주소)"""
    if not 판:
        return []
    out = [(g['글'], '목록 글', g.get('주소') or 판.get('주소', '')) for g in 판.get('목록글', [])]
    out += [(f['이름'], '붙은 파일', f.get('주소') or 판.get('끝주소') or 판.get('주소', '')) for f in 판.get('파일', [])]
    for g in 판.get('들어간글', []):
        out += [(f['이름'], f"「{g['글'][:40]}」에 붙은 파일", g.get('주소', '')) for f in g.get('파일', [])]
    return out


def 형식(판):
    """본 파일의 형식 — 엑셀·CSV 가 하나라도 있으면 ○, 문서(PDF·한글·압축)만 보였으면 ×, 파일을 못 봤으면 ?"""
    파일 = [(f.get('이름', '') + ' ' + f.get('주소', '')) for f in (판 or {}).get('파일', [])]
    for g in (판 or {}).get('들어간글', []):
        파일 += [(f.get('이름', '') + ' ' + f.get('주소', '')) for f in g.get('파일', [])]
    확 = sorted({m.group(1).lower() for s in 파일 for m in re.finditer(r'\.(xlsx?|csv|pdf|hwpx?|zip|docx?)(?:\W|$)', s, re.I)})
    if any(엑셀.search(s) for s in 파일):
        return 'O', f"엑셀·CSV 가 있다 (본 형식: {', '.join(확)})"
    if 확:
        return 'X', f"본 파일은 {', '.join(확)} 뿐이다 — 표를 그대로 옮겨 쓰기 어렵다. 들어가 본 글 밖에 엑셀이 있을 수는 있다"
    return '?', '파일 형식을 읽지 못했다(이름에 확장자가 없거나 파일을 못 잡았다)'


def api표():
    """지방재정365 에 숫자가 올라왔나 — 곁에 적을 참고. 키가 없으면 받아 둔 것을 쓴다"""
    path = os.path.join(ROOT, 'data', 'score_api.json')
    try:
        from fetch_lofin import fetch, load_key
        key = load_key()
        if not key:
            raise RuntimeError('키 없음')
        out = {}
        for code, 이름, 해 in (('FDHHH', '중기계획', None), ('BQBRB', '성인지예산', None), ('DIZFMP', '성인지결산', None)):
            for y in [str(date.today().year - k) for k in range(0, 4)]:
                try:
                    rows, _ = fetch(code, {'fyr': y}, key)
                except SystemExit:
                    continue
                if rows:
                    out[이름] = {'해': y, '곳': sorted({r['laf_cd'] for r in rows})}
                    break
        json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False)
        return out
    except Exception as e:  # noqa: BLE001 — 참고칸이라 못 받아도 굽는다
        print(f'  (지방재정365 참고 — 새로 못 받음: {e}. 받아 둔 것을 쓴다)')
        return json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}


def main():
    bd = json.load(open(os.path.join(ROOT, 'data', 'budget_docs.json'), encoding='utf-8'))
    dom = {r['laf_cd']: r for r in json.load(open(os.path.join(ROOT, 'data', 'disclosure_dom.json'), encoding='utf-8'))['곳']}
    손path = os.path.join(ROOT, 'data', 'score_hand.json')
    손 = json.load(open(손path, encoding='utf-8')) if os.path.exists(손path) else {}
    손 = {k: v for k, v in 손.items() if not k.startswith('_')}
    api = api표()
    목록 = {x['cd']: x for x in json.load(open(os.path.join(SITE, 'data', 'loc', 'index.json'), encoding='utf-8'))['곳']}

    곳들 = []
    for r in bd['곳']:
        cd = r['laf_cd']
        예, 결 = r.get('예산') or {}, r.get('결산') or {}
        공시 = [(f['이름'], '재정공시 파일', dom.get(cd, {}).get('끝주소', '')) for f in dom.get(cd, {}).get('파일', [])]
        글 = {'예산': 글자들(예), '결산': 글자들(결), '공시': 공시}
        판 = {}
        for 키, _, _, 어디, 잣대 in 항목:
            if 키 in 못함:
                판[키] = {'값': '?', '근거': 못함[키]}
                continue
            if 키 == '별도':
                u = 예.get('끝주소') or 예.get('주소') or ''
                host = urlparse(u).hostname or ''
                판[키] = ({'값': 'O', '근거': f'예산서가 따로 둔 재정 누리집에 있다 ({host})', '주소': u}
                         if 별도주소.search(host) else
                         {'값': '?', '근거': f'예산서가 일반 누리집({host or "주소 없음"}) 안에 있다. 따로 둔 재정 사이트가 있는지는 사람이 볼 칸'})
                continue
            if 키 in ('예산형식', '결산형식'):
                v, 근 = 형식(예 if 키 == '예산형식' else 결)
                판[키] = {'값': v, '근거': 근, '주소': (예 if 키 == '예산형식' else 결).get('주소', '')}
                continue
            볼 = {'예산': 글['예산'], '결산': 글['결산'], '둘+공시': 글['예산'] + 글['결산'] + 글['공시'],
                  '예산+공시': 글['예산'] + 글['공시'], '둘': 글['예산'] + 글['결산']}[어디]
            걸 = next(((t, 곳, u) for t, 곳, u in 볼 if re.search(잣대, t)), None)
            if not 걸 and 키 == '명세서':   # 「사업명세서」라는 이름은 없어도 예산서 책이 올라와 있으면 — 명세서는 보통 그 안에 든다
                예서 = next(((t, 곳, u) for t, 곳, u in 볼 if re.search(r'예산서', t) and not re.search(r'성인지|기후|온실', t)), None)
                if 예서:
                    판[키] = {'값': 'O', '근거': f'{예서[1]} — 「{예서[0][:70]}」. 「사업명세서」라는 이름은 못 봤지만 예산서가 올라와 있다'
                                              '(명세서는 보통 예산서 안에 든다)', '주소': 예서[2]}
                    continue
            if 걸:
                판[키] = {'값': 'O', '근거': f'{걸[1]} — 「{걸[0][:70]}」', '주소': 걸[2]}
            else:
                본곳 = {'예산': '예산서 게시판', '결산': '결산서 게시판', '둘+공시': '예산서·결산서 게시판과 재정공시',
                       '예산+공시': '예산서 게시판과 재정공시', '둘': '예산서·결산서 게시판'}[어디]
                막힘 = (예 if '예산' in 어디 or 어디.startswith('둘') else 결).get('실패')
                판[키] = {'값': '?', '근거': f'{본곳}에서 이 이름을 못 찾았다' + (f' (게시판이 안 열림: {막힘})' if 막힘 else '')
                        + ' — 없다는 뜻은 아니다'}
        # 지방재정365 참고(판정에는 안 씀)
        for 키, api이름 in (('중기', '중기계획'), ('성인지', '성인지예산')):
            a = api.get(api이름)
            if a and cd in a['곳']:
                판[키]['참고'] = f"지방재정365 에는 {a['해']}년 {api이름} 숫자가 올라와 있다(문서 공개와는 다르다)"
        # 사람이 본 것이 앞선다
        for 키, v in 손.get(cd, {}).items():
            if isinstance(v, dict):
                판[키] = {**v, '손': 1}
        정성점 = {k: 손.get(cd, {}).get(k, {}).get('점수') if isinstance(손.get(cd, {}).get(k), dict) else None for k, *_ in 정성}
        m = 목록.get(cd, {})
        곳들.append({'cd': cd, '이름': r['이름'], '시도': m.get('시도', ''), '갈래': m.get('갈래', ''),
                    '예산주소': 예.get('주소', ''), '결산주소': 결.get('주소', ''),
                    '판': 판, '정성': 정성점, 'O': sum(1 for v in 판.values() if v['값'] == 'O')})

    out = {'만든날': date.today().isoformat(), '긁은날': bd['만든날'],
           '항목': [{'키': k, '갈래': g, '이름': n, '자동': k not in 못함} for k, g, n, *_ in 항목],
           '정성': [{'키': k, '갈래': g, '이름': n} for k, g, n in 정성],
           '공청회까닭': 공청회까닭, '곳': 곳들}
    json.dump(out, open(os.path.join(ROOT, 'data', 'score.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

    tpl = open(os.path.join(SITE, 'score.template.html'), encoding='utf-8').read()
    # 남의 누리집에서 긁은 글자가 들어간다 — 「</script>」가 섞여도 스크립트 밖으로 새지 않게
    page = tpl.replace('__DATA__', json.dumps(out, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/'))
    open(os.path.join(SITE, 'score.html'), 'w', encoding='utf-8').write(page)

    print(f'구움: site/score.html · {len(곳들)}곳 · 긁은날 {bd["만든날"]}')
    for k, _, n, *_ in 항목:
        c = {v: sum(1 for x in 곳들 if x['판'][k]['값'] == v) for v in 'OX?'}
        print(f"  {n[:22]:24} ○{c['O']:4}  ×{c['X']:4}  ?{c['?']:4}")


if __name__ == '__main__':
    main()
