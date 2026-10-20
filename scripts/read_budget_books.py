# 예산서 읽는 봇 — 곳마다 「사업예산서」 PDF 를 받아 세부사업별 통계목(행사운영비·업무추진비 …) 금액을 뽑는다.
#   (2026-10-20 사용자 「예산서 읽는 봇을 만들어 놓고 고민하자」)
#
#   python scripts/read_budget_books.py               고를 수 있는 곳 전부 (받은 파일은 다시 안 받음)
#   python scripts/read_budget_books.py 1111000 ...   그 곳만
#
# 어디서 — data/budget_docs.json(check_budget_docs.js) 에 적힌 파일 가운데 이름에 「사업예산·세부사업·사업별·사업명세」가 든 것.
#   올해 본예산을 먼저, 없으면 추경. 주소가 자바스크립트(누르는 단추)인 곳은 아직 못 받는다 — 「누르기 필요」로 적는다.
# 읽기 — pymupdf 로 글자를 뽑아 parse_budget_doc.py 와 같은 규칙으로: 「편성목(3자리)」 밑 「통계목(2자리) + 숫자 셋」의 첫 숫자(올해 예산, 천원).
# 맞나 — 행사·축제경비 통계목 넷의 합을 지방재정365 공식(YCEHF, 일반회계)과 견준다. 차이가 크면 양식이 다른 곳이다.
#
# 결과: data/예산서/<코드>.json.gz(세부사업 전부, 깃 무시) · data/budget_books.json(곳마다 요약, 저장소)
# 원본 PDF 는 캐시(%LOCALAPPDATA%\local-finance-files\예산서)에만.
# ⚠️ 국내 PC 에서 돌린다 — 지자체 누리집은 해외(깃허브 러너)를 막는 곳이 많다.
import gzip, hashlib, json, os, re, subprocess, sys, collections, datetime, urllib.request, urllib.parse
import pymupdf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
캐시 = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'local-finance-files', '예산서')
OUT = os.path.join(ROOT, 'data', '예산서')
요약파일 = os.path.join(ROOT, 'data', 'budget_books.json')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36'
뜻 = re.compile(r'사업예산|세부사업|사업별|사업명세')
행사 = {'201-03': '행사운영비', '301-11': '행사실비지원금', '307-04': '민간행사사업보조', '401-04': '행사관련시설비'}


def 고르기(곳, 해):
    # 이름이 「사업예산서」가 아니어도 후보로 — 통째 예산서(「2026년 예산서」·「전체 파일」), 장으로 쪼갠 곳의 「일반회계」 장.
    #   어느 것이 맞는지는 읽어 보고 공식 숫자와 견줘 고른다(main)
    e = 곳.get('예산') or {}
    후보 = [(f, e.get('끝주소') or e.get('주소')) for f in e.get('파일', [])]
    후보 += [(f, g.get('주소') or e.get('주소')) for g in e.get('들어간글', []) for f in g.get('파일', [])]
    def 점수(f):
        t = f['이름']
        if re.search(r'성인지|기금|성과|결산|중기|의견서|주민참여|총칙|규모|총괄|세입|리플릿|안내|점자|음성', t):
            return -1
        s = 30 if 뜻.search(t) else 20 if re.search(r'세부내역|전체|예산서', t) else 10 if re.search(r'일반회계|세출', t) else -1
        return s + (str(해) in t) * 2 + (not re.search(r'추경|추가경정|제\s*\d\s*회', t))
    return [fb for fb in sorted(후보, key=lambda fb: -점수(fb[0])) if 점수(fb[0]) > 0]


def 누를것(f):
    주소 = f['주소']
    return not 주소 or 주소.lower().startswith('javascript') or 주소.startswith('#') or not re.match(r'^(https?:)?/|^[\w./-]+(\?|$)', 주소)


def 누른자리(cd, f, 바탕):
    return os.path.join(캐시, f'{cd}_c{hashlib.sha1((바탕 + f["주소"]).encode()).hexdigest()[:10]}.pdf')


def 받기(cd, f, 바탕):
    if 누를것(f):
        자리 = 누른자리(cd, f, 바탕)
        if not os.path.exists(자리):
            return None, '누르기 필요'
        if not open(자리, 'rb').read(4).startswith(b'%PDF'):
            return None, '피디에프 아님(누름)'
        return 자리, ''
    주소 = f['주소']
    # 주소에 한글·띄어쓰기가 그대로 든 곳이 있다 — 이미 %인 것은 두고 나머지만 바꾼다
    주소 = urllib.parse.quote(urllib.parse.urljoin(바탕, 주소).strip(), safe=":/?&=%#;,+@!$'()*~[]")
    os.makedirs(캐시, exist_ok=True)
    자리 = os.path.join(캐시, f'{cd}_{hashlib.sha1(주소.encode()).hexdigest()[:10]}.pdf')
    if os.path.exists(자리):
        return 자리, ''
    try:
        req = urllib.request.Request(주소, headers={'User-Agent': UA, 'Referer': 바탕})
        with urllib.request.urlopen(req, timeout=180) as r:
            몸 = r.read()
    except Exception as e:
        return None, f'못 받음 {str(e)[:60]}'
    if not 몸.startswith(b'%PDF'):
        return None, '피디에프 아님(' + ('웹 화면' if b'<html' in 몸[:2000].lower() else 몸[:8].hex()) + ')'
    open(자리, 'wb').write(몸)
    return 자리, ''


def 읽기(자리):
    # 쪽마다 글자 줄을 이어 붙여 parse_budget_doc.py 와 같은 규칙으로 읽는다 — 통계목은 전부 담는다
    L = []
    for i, p in enumerate(pymupdf.open(자리), 1):
        L.append(f'=====쪽 {i}')
        L += [x.strip() for x in p.get_text().splitlines()]
    수 = re.compile(r'^△?[\d,]+$')
    n = lambda s: (-1 if s.startswith('△') else 1) * int(s.lstrip('△').replace(',', ''))
    세부 = 편성 = None
    결과 = collections.OrderedDict()
    쪽 = 0
    for i, s in enumerate(L):
        if s.startswith('=====쪽'):
            쪽 = int(s.split()[-1]); continue
        if not (i + 3 < len(L) and all(수.match(L[i + k]) for k in (1, 2, 3))):
            continue
        m = re.match(r'^(\d{3}) (\S.*)$', s)
        if m:
            편성 = m.group(1); continue
        m = re.match(r'^(\d{2}) (\S.*)$', s)
        if m:
            if 세부 and 편성:
                칸 = 결과.setdefault(세부, {'쪽': 쪽, '목': collections.Counter()})
                칸['목'][f'{편성}-{m.group(1)}'] += n(L[i + 1])
            continue
        if not s.startswith(('○', '―', '-', '=')) and not 수.match(s):
            세부 = (s, 쪽)
    return len(L), [{'이름': k[0], '쪽': v['쪽'], '목': dict(v['목'])} for k, v in 결과.items()]


def 공식표():
    # YCEHF: 행사·축제경비 편성(일반회계, 원). smy_cntt_amt2 가 행사·축제경비
    d = json.load(gzip.open(os.path.join(ROOT, 'data', 'items', 'YCEHF.json.gz'), 'rt', encoding='utf-8'))
    return {(r['laf_cd'], r['fyr']): r.get('smy_cntt_amt2') for r in d['행']}


def main():
    곳들 = json.load(open(os.path.join(ROOT, 'data', 'budget_docs.json'), encoding='utf-8'))['곳']
    if sys.argv[1:]:
        곳들 = [x for x in 곳들 if x['laf_cd'] in sys.argv[1:]]
    요약 = json.load(open(요약파일, encoding='utf-8'))['곳'] if os.path.exists(요약파일) else {}
    공식 = 공식표()
    해 = datetime.date.today().year
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(캐시, exist_ok=True)
    # 올해 것을 공식과 1% 안으로 읽은 곳은 건너뛴다(곳을 콕 집으면 다시)
    if not sys.argv[1:]:
        곳들 = [x for x in 곳들 if not (요약.get(x['laf_cd'], {}).get('해') == 해 and abs(요약[x['laf_cd']].get('차이') or 100) < 1)]
    # 누르는 단추 파일은 크롬으로 한꺼번에 먼저 받는다(click_budget_books.js)
    일감 = [{'바탕': b, '이름': f['이름'], '주소': f['주소'], '자리': 누른자리(x['laf_cd'], f, b)}
            for x in 곳들 for f, b in 고르기(x, 해)[:5] if 누를것(f) and b and not os.path.exists(누른자리(x['laf_cd'], f, b))]
    if 일감:
        일감파일 = os.path.join(캐시, '일감.json')
        json.dump(일감, open(일감파일, 'w', encoding='utf-8'), ensure_ascii=False)
        print(f'누르기 {len(일감)}개 — 크롬으로 받는다', flush=True)
        subprocess.run(['node', os.path.join(ROOT, 'scripts', 'click_budget_books.js'), 일감파일])
    for 곳 in 곳들:
        cd, 줄 = 곳['laf_cd'], {'이름': 곳['이름'], '해': 해}
        후보 = 고르기(곳, 해)
        if not 후보:
            줄['까닭'] = '사업예산서를 이름으로 못 고름'
        맞 = 공식.get((cd, str(해)))
        가장 = None   # (어긋남, 줄, 사업, 파일이름) — 후보를 차례로 읽어 공식과 가장 가까운 것
        # ponytail: 후보 다섯까지만 받는다 — 장으로 쪼갠 곳은 「일반회계」 장이 뒤에 있으면 놓친다
        for f, 바탕 in 후보[:5]:
            자리, 까닭 = 받기(cd, f, 바탕)
            if not 자리:
                if not 가장: 줄.update(파일=f['이름'][:80], 까닭=까닭)
                continue
            try:
                _, 사업 = 읽기(자리)
            except Exception as e:
                if not 가장: 줄.update(파일=f['이름'][:80], 까닭=f'못 읽음 {str(e)[:60]}')
                continue
            합 = sum(v for x in 사업 for k, v in x['목'].items() if k in 행사)
            차이 = round((합 * 1000 - 맞) / 맞 * 100, 2) if 맞 else None
            어긋남 = abs(차이) if 차이 is not None else (0 if len(사업) >= 100 else 100)
            if 사업 and (not 가장 or 어긋남 < 가장[0]):
                가장 = (어긋남, dict(파일=f['이름'][:80], 까닭='', 세부사업=len(사업), 행사축제_천원=합,
                                    공식_천원=round(맞 / 1000) if 맞 else None, 차이=차이), 사업, f['이름'])
            if 가장 and 가장[0] < 1:
                break
        if 가장:
            줄.update(가장[1])
            json.dump({'해': 해, '파일': 가장[3], '사업': 가장[2]}, gzip.open(os.path.join(OUT, f'{cd}.json.gz'), 'wt', encoding='utf-8'), ensure_ascii=False)
        요약[cd] = 줄
        print(cd, json.dumps(줄, ensure_ascii=False), flush=True)
    json.dump({'만든날': str(datetime.date.today()), '곳': 요약}, open(요약파일, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    셈 = collections.Counter('읽음' if x.get('세부사업') else (x.get('까닭') or '?').split('(')[0].split(' ')[0] for x in 요약.values())
    맞음 = sum(1 for x in 요약.values() if x.get('차이') is not None and abs(x['차이']) < 1)
    print('\n', dict(셈), f'· 공식과 1% 안 {맞음}곳')


if __name__ == '__main__':
    main()
