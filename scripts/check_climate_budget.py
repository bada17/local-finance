# 기후예산서(온실가스감축인지 예산서) 봇 — 243곳마다 「공개했나」를 근거와 함께 가린다. 「없음」도 어디를 보고 없다고 했는지 적는다.
#   (2026-10-20 사용자 「없음으로 나와도 없음임을 확인하는 게 필요해. 그것도 봇으로」)
#
#   python scripts/check_climate_budget.py            안 본 곳만 (끊겨도 이어 한다)
#   python scripts/check_climate_budget.py --다시     처음부터
#   python scripts/check_climate_budget.py 2915000    그 곳만
#
# ⚠️ 법: 탄소중립기본법 24조는 「관계 법률에서 정하는 바에 따라」인데 지방재정법·시행령·지방회계법엔 조항이 없다(10-20 원문 확인).
#    그래서 「만들었나」가 아니라 **「누리집에 공개했나」**를 본다. 서울시처럼 만든다는 곳도 안 올렸을 수 있다.
# 보는 곳 둘:
#   ① 예산서 게시판 — data/budget_docs.json(check_budget_docs.js)의 글 제목·파일 이름
#   ② 웹 검색 — 「site:그 누리집 온실가스감축인지 예산서」를 DuckDuckGo·네이버 둘 다에(10-26). DuckDuckGo 는 잇달아 부르면
#      202 로 막혀 10-20 에 12곳에서 멈췄다 — 둘 중 하나만 열려도 본 것으로 친다. 결과는 합친다(둘이 잡는 문서가 다르다)
# 가름: 있음(올해) · 있음(지난해만) · 있음(해 모름) · 관련 글만 · 없음(①을 끝까지 봤고 ②가 0건) · 못 봄(①을 못 봤거나 ②가 둘 다 막힘)
#   「있음」은 제목에 「예산서」가 있을 때만 — 네이버 본문 조각엔 국가재정법 27조(「온실가스감축인지 예산서의 작성」)가 자주 걸린다
# 있음이면 내려받기 주소가 바로인 것은 받아 둔다(캐시 local-finance-files/기후예산서).
# 결과: data/climate_budget.json
import html, json, os, re, sys, time, datetime, urllib.request, urllib.parse

# UA·캐시 자리는 read_budget_books.py 와 같게 — 가져오면 pymupdf 까지 불러와서(그게 깨지면 이 봇도 못 돈다, 10-26) 따로 적는다
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'climate_budget.json')
캐시 = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'local-finance-files', '기후예산서')
기후 = re.compile(r'온실가스\s*감축\s*인지|기후\s*(변화)?\s*(대응)?\s*(영향)?\s*예산|탄소\s*인지\s*예산|기후\s*재정')
해 = datetime.date.today().year
# 「있음」은 예산서 그 자체일 때만 — 서울시는 「시범 운영계획」 결재문서만 걸렸다(10-20 시험). 그런 건 「관련 글만」
#   네이버는 「기후 예산서 작성지침」·「기후 예산서 작성 과정」 같은 글도 걸어 온다(10-26 서울) — 책 이름이 있고 딴 말이 없을 때만
예산서 = re.compile(r'(온실가스\s*감축\s*인지|기후)\s*(예산|결산)\s*서')
딴말 = re.compile(r'지침|과정|교육|계획|용역|조례|보고|연구|안내|공고|제도|도입|운영|평가|토론|회의')


def 누리집(곳):
    # 예산서 게시판 주소에서 누리집 이름을 뗀다 — news.seoul.go.kr → seoul.go.kr, www.namgu.gwangju.kr → namgu.gwangju.kr
    h = urllib.parse.urlparse((곳.get('예산') or {}).get('주소') or '').hostname or ''
    h = re.sub(r'^www\d?\.', '', h)
    return '.'.join(h.split('.')[-3:]) if h.endswith('.go.kr') else h


def 게시판(곳):
    e = 곳.get('예산') or {}
    이름 = [f['이름'] for f in e.get('파일', [])] + [f['이름'] for g in e.get('들어간글', []) for f in g.get('파일', [])]
    이름 += [g['글'] for g in e.get('목록글', [])]
    찾음 = [n for n in 이름 if 기후.search(n)]
    # 끝까지 봤다 = 게시판이 열렸고, 올해 본예산 글에 들어가 파일을 읽었거나 목록에서 파일을 셋 넘게 읽었다
    봄 = e.get('코드') == 200 and (any(str(해) in g['글'] and g.get('파일') for g in e.get('들어간글', [])) or len(e.get('파일', [])) >= 3)
    return 찾음, 봄


def 열기(주소, 맞나):
    for n in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(주소, headers={'User-Agent': UA, 'Accept-Language': 'ko'}), timeout=40) as r:
                s = r.read().decode('utf-8', 'replace')
                if r.status == 200 and 맞나(s):
                    return s
        except Exception:
            pass
        time.sleep(30)
    return None


def 검색(누리):
    q = urllib.parse.quote(f'site:{누리} 온실가스감축인지 예산서')
    out, 열림 = [], 0
    s = 열기('https://html.duckduckgo.com/html/?q=' + q, lambda s: 'result' in s)
    if s is not None:
        열림 += 1
        for m in re.finditer(r'class="result__a" href="([^"]+)"[^>]*>(.*?)</a>', s, re.S):
            주소 = urllib.parse.unquote(re.sub(r'^.*?uddg=|&amp;rut=.*$', '', m.group(1)))
            제목 = html.unescape(re.sub(r'<[^>]+>|\s+', ' ', m.group(2))).strip()
            if 누리 in 주소 and 기후.search(제목 + ' ' + 주소):
                out.append({'제목': 제목[:100], '주소': 주소[:300], '곳': 'DDG'})
    # 네이버 — 제목 고리는 글 끝에 「새 창 열림」이 붙는다. 본문 조각 고리는 같은 주소라 제목만 쓴다
    s = 열기('https://search.naver.com/search.naver?where=web&query=' + q, lambda s: 'search.naver' in s)
    if s is not None:
        열림 += 1
        for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', s, re.S):
            주소 = html.unescape(m.group(1))
            제목 = html.unescape(re.sub(r'<[^>]+>|\s+', ' ', m.group(2))).strip()
            if not 제목.endswith('새 창 열림') or not (urllib.parse.urlparse(주소).hostname or '').endswith(누리):
                continue
            제목 = 제목[:-len('새 창 열림')].strip()
            if 제목 and 기후.search(제목) and all(x['주소'] != 주소[:300] for x in out):
                out.append({'제목': 제목[:100], '주소': 주소[:300], '곳': '네이버'})
    return out if 열림 else None   # 둘 다 막힘


def 받기(cd, 주소):
    if not re.search(r'download|filedown|\.pdf|\.hwp|atchfile', 주소, re.I):
        return ''
    os.makedirs(캐시, exist_ok=True)
    try:
        with urllib.request.urlopen(urllib.request.Request(주소, headers={'User-Agent': UA}), timeout=120) as r:
            몸 = r.read()
    except Exception:
        return ''
    if b'<html' in 몸[:2000].lower():
        return ''
    자리 = os.path.join(캐시, f'{cd}_{len(os.listdir(캐시))}' + ('.pdf' if 몸.startswith(b'%PDF') else '.bin'))
    open(자리, 'wb').write(몸)
    return os.path.basename(자리)


def main():
    곳들 = json.load(open(os.path.join(ROOT, 'data', 'budget_docs.json'), encoding='utf-8'))['곳']
    인자 = [a for a in sys.argv[1:] if a != '--다시']
    결과 = {} if '--다시' in sys.argv or not os.path.exists(OUT) else json.load(open(OUT, encoding='utf-8'))['곳']
    if 인자:
        곳들 = [x for x in 곳들 if x['laf_cd'] in 인자]
    else:
        곳들 = [x for x in 곳들 if x['laf_cd'] not in 결과 or 결과[x['laf_cd']]['가름'] == '못 봄']
    for k, 곳 in enumerate(곳들):
        cd, 누리 = 곳['laf_cd'], 누리집(곳)
        판찾음, 판봄 = 게시판(곳)
        웹 = 검색(누리) if 누리 else None
        책 = [w for w in (웹 or []) if 예산서.search(w['제목']) and not 딴말.search(w['제목']) and len(w['제목']) <= 60]
        근거 = 판찾음 + [w['제목'] + ' ' + w['주소'] for w in 책]
        올해 = [n for n in 근거 if re.search(rf'(?<!\d){해}(?!\d)', n)]   # 주소의 긴 번호(dataSid=306204522) 속 「2045」를 해로 읽었다(10-26 거제)
        # 이름에 해가 없으면 언제 것인지 모른다(거제 「온실가스 감축인지 예산서」) — 「지난해만」이라 하지 않는다
        가름 = ('있음(올해)' if 올해 else '있음(지난해만)' if any(re.search(r'(?<!\d)20[12]\d(?!\d)', n) for n in 근거) else '있음(해 모름)' if 근거 else
               '관련 글만' if 웹 else
               '없음' if 판봄 and 웹 is not None else '못 봄')
        받음 = [f for w in 책 if str(해) in w['제목'] + w['주소'] for f in [받기(cd, w['주소'])] if f]
        결과[cd] = {'이름': 곳['이름'], '가름': 가름, '누리집': 누리, '게시판_봄': 판봄, '게시판_찾음': 판찾음[:5],
                   '검색': '막힘' if 웹 is None else 웹[:5], '받은파일': 받음, '본날': str(datetime.date.today())}
        print(k + 1, len(곳들), cd, 곳['이름'], 가름, flush=True)
        json.dump({'만든날': str(datetime.date.today()), '곳': 결과}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        time.sleep(30)   # DuckDuckGo 는 잇달아 부르면 202 로 한동안 막는다(10-20) — 네이버가 받쳐서 반으로 줄임
    셈 = {}
    for x in 결과.values():
        셈[x['가름']] = 셈.get(x['가름'], 0) + 1
    print('\n', 셈)


if __name__ == '__main__':
    main()
