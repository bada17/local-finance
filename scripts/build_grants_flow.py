# 국고보조 돈길 세 칸 — 기초 226곳(2026-11-09 사용자 「기초는 의외로 잘 맞는데」 → 기초부터 굽기)
#
#   python scripts/build_grants_flow.py 2024
#
# 칸 ① 교부세 등(지방교부세+지방소멸대응기금)·조정교부금 — 지방재정365 세입결산(FIACRV) 2단계. 결산서 원문과 원 단위까지 같음(마포·태백·순창·대구 확인)
#    ② 국고보조금 — 같은 세입결산 51000. 사업별은 지방재정365 세부사업 세출(QWGJK) 국비 칸(bdg_ntep, 예산현액)
#    ③ 단체가 받은 국고보조 — e나라도움 보조사업자 공시(R2 국고보조/), 받은 곳 주소가 이 곳인 줄. 줄마다 거친 곳 하나만:
#       ⓐ 공시 지자체부담금 0. 실제 교부기관은 별도 증빙으로 확인
#       ⓑ 이 지자체 가계부의 같은 이름 사업 = 이 지자체를 거침(② 안에 든 돈 — 더하지 않는다)
#       ⓒ 광역 가계부의 같은 이름 사업 = 광역을 거침(광역 몫 — 이 곳 합계에 넣지 않는다)
#       ⓓ 못 이음(다른 지역 돈·이름이 다른 사업) · 학교 = 교육청(따로 본다)
#    받은 곳 이름이 광역 기관(서울시·시립 등)이면 광역부터 본다(마포에서 구청에 잘못 붙던 5줄).
# 검사 — ⓑ 를 사업마다 모아 「공시 국비 합 > 가계부 국비」면 뻥튀기 의심으로 센다.
# ⚠️ 받은 곳 이름은 찍지 않는다(로그가 공개). 사업명·건수·금액만.
# 결과: data/grants_flow_<해>.json (곳마다 요약)
import gzip, json, os, re, sys, unicodedata
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
해 = sys.argv[1] if len(sys.argv) > 1 else '2024'
f = lambda x, k: float(x.get(k) or 0)

시도이름 = {'서울': ['서울특별시'], '부산': ['부산광역시'], '대구': ['대구광역시'], '인천': ['인천광역시'], '광주': ['전남광주통합특별시', '광주광역시'],
          '대전': ['대전광역시'], '울산': ['울산광역시'], '세종': ['세종특별자치시'], '경기': ['경기도'], '강원': ['강원특별자치도', '강원도'],
          '충북': ['충청북도'], '충남': ['충청남도'], '전북': ['전북특별자치도', '전라북도'], '전남': ['전남광주통합특별시', '전라남도'],
          '경북': ['경상북도'], '경남': ['경상남도'], '제주': ['제주특별자치도']}
광역기관 = {k: '|'.join(v + [k + '시', k + '도', '시립', '도립']) for k, v in 시도이름.items()}

곳 = json.load(open(os.path.join(ROOT, 'site', 'data', 'loc', 'index.json'), encoding='utf-8'))['곳']
광역코드 = {x['시도']: x['cd'] for x in 곳 if x['갈래'] == '광역'}
기초 = [x for x in 곳 if x['갈래'] == '기초']
# 주소가 지금 행정구역 이름으로 와서 옛 이름 곳이 비는 경우 — {코드: [주소 둘째 낱말들]}. 한 낱말을 두 곳에 주면 두 번 센다(주의)
# 인천은 2026-07 개편 이름으로 온다(2024 결산은 옛 이름) — 서구 → 서해구·검단구, 중구 → 영종구. 제물포구는 옛 중구 내륙+동구라 갈라 못 한다 → 어느 곳에도 안 준다(동구는 빈다)
옛이름 = {'2818000': ['서구', '서해구', '검단구'], '2811000': ['중구', '영종구'], '2812000': ['동구']}

# 사업 이름에 다른 지역 이름이 들면(「통합문화이용권 - 고양시」「알뜰교통카드(서울특별시)」) 그 지역 돈이다 — 주소만 이 곳
지역낱말 = sorted({x['이름'][len(x['시도']):] for x in 기초 if len(x['이름']) - len(x['시도']) >= 3} | {w for v in 시도이름.values() for w in v}, key=len, reverse=True)
지역식 = re.compile('|'.join(map(re.escape, 지역낱말)))

# ── 못 이음(ⓓ) 다시 잇기 — 2026-11-11 사용자 「못 이음은 금액으로」「공모로 뽑힌 법인이 받아도 지방정부 사업의 일환」「다른 방법을 찾아」
#   첫 대조(이름 같음)에서 남은 ⓓ 를 아래 차례로 다시 본다. 이은 줄은 ⓑ2(이 곳 장부)·ⓒ2(광역 장부)·ⓓ다른지역2 에 **따로** 담고
#   「대조」에 방법별로 센다(첫 대조 칸 ⓑ·ⓒ 는 그대로 — 화면 글 「이름이 맞는 공시」가 틀리지 않게).
#   ① 짧은 지명 —「충남어촌…」「(전남 순천)」「서귀포시」. 보통 낱말과 같은 지명(예산·영양·경기…)은 안 본다(「전국체육대회 경기운영비」)
#   ② 국비·지방비가 원 단위까지 같은 장부 사업 + 이름 조각이 겹침(이 곳 → 광역). 금액만 같으면 8개 중 3개가 엉뚱했다
#   ③ 같은 부처 사업 줄을 합쳐, 이름이 가장 많이 겹치는 장부 줄(들)의 금액 안에 들면 — 공모로 뽑힌 여러 곳이 한 사업을 나눠 받음.
#      장부 줄이 여럿(노인일자리 공익형·시장형…)이면 「어느 줄」은 안 정하고 「그 장부를 거침」까지만
#   ④ ③을 줄 하나씩(묶음 합이 넘칠 때). 광역은 세 조각 이상 — 두 조각이면 「체육대회」로 엉뚱하게 붙었다
#   ⑤ 이름이 네 조각 이상 겹치면 금액 없이(이월·추경으로 금액이 어긋남 —「청정위판장」)
#   ⑥ 전국 장부에서 금액·이름이 맞는 곳이 한 곳이고 그 지명이 공시 글에 나오면 그곳 돈(「7호선 부천구간」)
#   ⑦ 낱말 앞머리 지명이 하나(「보령향교」)
#   버린 것(표본이 거의 틀림): 같은 시도·전국 장부에서 이름만으로(대학일자리플러스센터가 제주 본청에 붙음), 사업 내용 칸의 지명.
흔한말 = re.compile('지방자치단체|자치단체|지원사업|지원|사업|운영|경상|자본|보조금|보조|민간|국비|도비|시비|군비|구비|직접|균특|기금|지자체|설치|관리|육성|활성화|조성|센터|프로그램|추진|위탁|대행|공모|시범|개선|확충|강화|기반|구축|확대|지정|년도|년|이월금|이월|생활체육|체육대회|대축전|현대화|문화유산|국가유산|보수정비|기념행사|행사')
조각 = lambda s: {w[i:i + 3] for w in re.findall(r'[가-힣]+', 흔한말.sub(' ', s or '')) for i in range(len(w) - 2)}
낱말같은지명 = set('예산 영양 고령 장수 음성 상주 동해 부여 완주 화성 공주 진도 영광 광명 태안 하남 구리 과천 광주 고성 신안 보은 성주 청도 양구 진안 무안 안성 정선 곡성 남해 서천 의령 함안 강진 군위 달성 옥천 영동 단양 증평 계룡 금산 청양 홍성 양산 김해 사천 거제 통영 밀양 창녕 하동 산청 함양 거창 합천 부산 중구 동구 서구 남구 북구 강서 강남 강북 남동 서산 동래 수영 연수 부평 계양 광산 유성 대덕 울주 달서 수성 송파 양천 관악 성동 성북 도봉 노원 은평 마포 금천 영등포 동작 서초 중랑 광진 용산 종로 강화 진주 수원 구미 안산 장성 인제 보성 의성 영월 광양'.split())
줄기수 = Counter(re.sub(r'(시|군|구)$', '', x['이름'][len(x['시도']):]) for x in 기초)
홑줄기 = sorted(k for k, v in 줄기수.items() if v == 1 and len(k) >= 2 and k not in 낱말같은지명)
def 짧은지명(글, 시도, 내줄기):
    t = ' ' + (글 or '')
    for s in 시도이름:
        if s not in (시도, '경기') and re.search(r'(?<![가-힣])' + s + r'(?!(도|시|권|형|산|원|주|대|남|북))', t): return s
    if 시도 != '제주' and re.search(r'서귀포|제주시', t): return '제주'
    for k in 홑줄기:
        if k != 내줄기 and re.search(r'(?<![가-힣])' + k + r'(시|군|구)?(?![가-힣])', t): return k
def 앞머리지명(글, 내줄기):
    m = [k for k in 홑줄기 if k != 내줄기 and re.search(r'(?<![가-힣])' + k, 글 or '')]
    return m[0] if len(m) == 1 else None
def 대표경로(표):
    전체 = sum(표.values())
    if 전체 >= 10:
        for 경로 in ('ⓑ', 'ⓒ'):
            if 표.get(경로, 0) * 5 >= 전체 * 4:
                return 경로

def 마지막경로(기초점, 광역점):
    if 기초점 > 광역점:
        return 'ⓑ3', '약 — 이름 일부'
    if 광역점 > 기초점:
        return 'ⓒ3', '약 — 이름 일부'
    return 'ⓓ지역모름3', '모름 — 장부 근거 없음'

def 체전종류(해, 부처사업, 세부사업, 내용=''):
    if 해 != '2024':
        return None
    제목 = re.sub(r'[\s()]', '', 세부사업)
    근거 = 제목 + ' ' + re.sub(r'[\s()]', '', 내용)
    if 부처사업 == '전국체전 지원' and re.search(r'105회.*전국체(?:전|육대회)', 제목):
        if re.search(r'경기운영|운영비|운영요원|심판|경기방식|개[·ㆍ]?폐회식|개회식|폐회식|대회운영|도핑|D-100일', 근거):
            return '전국체전'
    if 부처사업.startswith('장애인전국체전 및 국제대회지원') and re.search(r'44회.*전국장애인체(?:전|육대회)', 제목):
        if re.search(r'경기운영|운영비|운영요원|심판|프레대회|사전대회|행정보조', 근거):
            return '전국장애인체전'

def 이름정규화(이름):
    return re.sub(r'[^가-힣a-z0-9]', '', unicodedata.normalize('NFKC', 이름 or '').casefold())

법인표기 = re.compile(
    r'^\s*(?:\((?:주|사|재)\)|사단법인|재단법인|사회복지법인|학교법인|의료법인|주식회사|유한회사|농업회사법인|영농조합법인)\s*'
    r'|\s*(?:\((?:주|사|재)\)|주식회사|유한회사)\s*$'
)

def 수령인이름표기(이름):
    원문 = unicodedata.normalize('NFKC', 이름 or '')
    return {이름정규화(원문), 이름정규화(법인표기.sub('', 원문))} - {''}

if '--selftest' in sys.argv:
    assert 짧은지명('2024년 충남어촌특화지원센터 운영', '서울', '금천') == '충남'
    assert 짧은지명('제105회 전국체육대회 경기운영비', '경남', '창원') is None
    assert 짧은지명('농촌집고쳐주기(전남 순천)', '전남', '나주') == '순천'
    assert 짧은지명('예산 문화유산 야행', '서울', '금천') is None
    assert 짧은지명('2022년 서귀포시 어촌뉴딜사업', '서울', '금천') == '제주'
    assert 앞머리지명('2024 선비의 배움터 여주향교', '중') == '여주'
    assert 짧은지명('2024년 충남 일자리사업 역량 강화 지원', '충남', '예산') is None
    assert len(조각('노인일자리 및 사회활동지원') & 조각('노인일자리사업')) >= 2
    assert not 조각('장애인 집합 정보화교육') & 조각('자치단체 명예축산물위생감시원 운영 수당')
    assert 대표경로(Counter({'ⓑ': 8, 'ⓒ': 1, 'ⓓ다른지역': 1})) == 'ⓑ'
    assert 대표경로(Counter({'ⓑ': 7, 'ⓒ': 1, 'ⓓ다른지역': 2})) is None
    assert 대표경로(Counter({'ⓒ': 9})) is None
    assert 마지막경로(0, 1) == ('ⓒ3', '약 — 이름 일부')
    assert 마지막경로(2, 1) == ('ⓑ3', '약 — 이름 일부')
    assert 마지막경로(2, 2) == ('ⓓ지역모름3', '모름 — 장부 근거 없음')
    assert 체전종류('2024', '전국체전 지원', '제105회 전국체육대회 경기운영비') == '전국체전'
    assert 체전종류('2024', '장애인전국체전 및 국제대회지원(자치단체경상보조)', '제44회 전국장애인체육대회 심판 피복비') == '전국장애인체전'
    assert 체전종류('2024', '전국체전 지원', '제105회 전국체육대회 선수단 참가비') is None
    assert 체전종류('2025', '전국체전 지원', '제105회 전국체육대회 경기운영비') is None
    assert 이름정규화('㈜예시') == 이름정규화('(주)예시')
    assert 수령인이름표기('㈜가상기관') == {'주가상기관', '가상기관'}
    assert 수령인이름표기('사단법인 가상기관') == {'사단법인가상기관', '가상기관'}
    print('selftest ok'); sys.exit()

# 세입결산
세입 = defaultdict(dict)
for x in json.load(gzip.open(os.path.join(ROOT, 'data', 'revenue', 'FIACRV.json.gz'), 'rt', encoding='utf-8')):
    if str(x['_해']) == 해 and x['lvl_no'] in ('1', '2', '3'):
        세입[x['laf_cd']][x['armk_cd']] = x['tott_sum_amt']

# 가계부(세부사업) — 전국 한 파일
p = os.path.join(ROOT, 'data', 'raw', f'QWGJK__exe_ymd-{해}1231_fyr-{해}.json')
rows = json.load(open(p, encoding='utf-8'))
rows = rows if isinstance(rows, list) else rows['rows']
가 = defaultdict(list)
for y in rows:
    if f(y, 'bdg_ntep') > 0: 가[y['laf_cd']].append(y)

# 공시
D = os.path.join(ROOT, 'data', 'national_grants')
줄 = json.load(gzip.open(f'{D}/{해}.json.gz', 'rt', encoding='utf-8'))['줄']
상 = json.load(gzip.open(f'{D}/상세_{해}.json.gz', 'rt', encoding='utf-8'))
열쇠 = lambda x: '|'.join(str(x.get(k, '')) for k in ('bsnsyear', 'excInsttId', 'ddtlbzId', 'dtlbzId', 'hwipnBassId'))
주소별 = defaultdict(list)
for x in 줄:
    d = 상.get(열쇠(x)) or {}
    w = (d.get('주소') or '').split()
    if len(w) >= 2:
        주소별[(w[0], w[1])].append({**x, **{f'상세_{k}': v for k, v in d.items()}})

n = lambda s: re.sub(r'\(.*?\)|\d{4}년?도?|[^가-힣A-Za-z0-9]', '', s or '')
# 가계부에 이름이 같은 사업이 여러 줄이면(회계·국비/시비 갈래) 한 묶음으로 국비를 합쳐 본다(마포 가족센터·고양 방과후아카데미)
묶음 = {}
def 사업묶음(laf):
    if laf not in 묶음:
        d = defaultdict(float)
        for y in 가[laf]: d[n(y['dbiz_nm'])] += f(y, 'bdg_ntep')
        묶음[laf] = {k: v for k, v in d.items() if k}
    return 묶음[laf]
def 짝(x, laf):
    m = 사업묶음(laf)
    for a in (x.get('dtlbzNm'), x.get('ddtlbzNm')):
        na = n(a)
        if len(na) < 4: continue
        for nb in m:
            if na == nb or (na in nb or nb in na) and min(len(na), len(nb)) >= 4: return nb

장부조각 = {cd: [(조각(y['dbiz_nm']), y) for y in rows] for cd, rows in 가.items()}
짝표 = defaultdict(list)   # (국비, 지방비) → 장부 줄. 지방비 = 시도비 + 시군구비
for cd, rows in 가.items():
    for y in rows: 짝표[(round(f(y, 'bdg_ntep')), round(f(y, 'capep') + f(y, 'sggep')))].append((cd, y))
곳이름 = {x['cd']: x['이름'] for x in 곳}
지방비 = lambda y: f(y, 'capep') + f(y, 'sggep')

def 다시잇기(c, 광, rows):
    """첫 대조에서 남은 줄 → {칸: [(줄, 방법)]}. 칸은 ⓑ2·ⓒ2·ⓓ다른지역2·ⓓ"""
    내줄기 = re.sub(r'(시|군|구)$', '', c['이름'][len(c['시도']):])
    글 = lambda x: (x.get('ddtlbzNm') or '') + ' ' + (x.get('dtlbzNm') or '')
    def 최고(cd, 이름):
        z = 조각(이름)   # 짧은 쪽 이름의 절반 이상이 겹쳐야 — 「인삼 생산시설 현대화」가 「과수고품질시설현대화」에 붙던 것
        점 = [(len(z & g) if z and g and len(z & g) * 2 >= min(len(z), len(g)) else 0, y) for g, y in 장부조각.get(cd, ())]
        b = max([p for p, _ in 점] or [0]); return b, [y for p, y in 점 if p == b and p > 0]
    칸 = lambda 장부: 'ⓑ2' if 장부 == c['cd'] else 'ⓒ2'
    out = defaultdict(list); 짝 = {}; 남 = []
    for x in rows:   # ①②
        if 짧은지명(글(x), c['시도'], 내줄기): out['ⓓ다른지역2'].append((x, '① 짧은 지명')); 짝[id(x)] = 짧은지명(글(x), c['시도'], 내줄기); continue
        hit = [(cd, y) for cd, y in 짝표.get((round(f(x, '상세_gsamt')), round(f(x, '상세_lsamt'))), ())
               if cd in (c['cd'], 광) and 조각(y['dbiz_nm']) & 조각(글(x))]
        if len(hit) == 1: out[칸(hit[0][0])].append((x, '② 국비·지방비 같음')); 짝[id(x)] = hit[0][1]['dbiz_nm']; continue
        남.append(x)
    묶음 = defaultdict(list)   # ③
    for x in 남: 묶음[x.get('dtlbzNm') or ''].append(x)
    남 = []
    for 부처사업, xs in 묶음.items():
        g = sum(f(x, '상세_gsamt') for x in xs); l = sum(f(x, '상세_lsamt') for x in xs)
        for 장부 in (c['cd'], 광):
            b, ys = 최고(장부, 부처사업)
            if b >= 2 and sum(f(y, 'bdg_ntep') for y in ys) >= g - 1 and sum(지방비(y) for y in ys) >= l - 1:
                out[칸(장부)] += [(x, '③ 합쳐서 장부 안') for x in xs]; 짝.update({id(x): ys[0]['dbiz_nm'] for x in xs}); break
        else: 남 += xs
    for x in 남:   # ④⑤⑥⑦
        for 장부, 문턱 in ((c['cd'], 2), (광, 3)):
            b, ys = 최고(장부, 글(x))
            if b >= 문턱 and sum(f(y, 'bdg_ntep') for y in ys) >= f(x, '상세_gsamt') - 1 and sum(지방비(y) for y in ys) >= f(x, '상세_lsamt') - 1:
                out[칸(장부)].append((x, '④ 줄 하나씩 장부 안')); 짝[id(x)] = ys[0]['dbiz_nm']; break
        else:
            b1, y1 = 최고(c['cd'], 글(x)); b2, y2 = 최고(광, 글(x))
            if max(b1, b2) >= 4 and b1 != b2: out[칸(c['cd'] if b1 > b2 else 광)].append((x, '⑤ 이름만(금액 어긋남)')); 짝[id(x)] = (y1 if b1 > b2 else y2)[0]['dbiz_nm']; continue
            본문 = 글(x) + ' ' + ' '.join(x.get(k) or '' for k in ('상세_bsnsCn', '상세_bsnsTrgetCn', '상세_bsnsPurpsCn'))
            h = [cd for cd, y in 짝표.get((round(f(x, '상세_gsamt')), round(f(x, '상세_lsamt'))), ()) if len(조각(y['dbiz_nm']) & 조각(글(x))) >= 2]
            nm = 곳이름.get(h[0], '') if len(set(h)) == 1 else ''
            열쇠 = nm[2:]; 열쇠 = nm[:2] if 열쇠 == '본청' else 열쇠[:-1]
            if nm and h[0] != c['cd'] and len(열쇠) >= 2 and 열쇠 in 본문 and 열쇠 not in c['이름']: out['ⓓ다른지역2'].append((x, '⑥ 전국 장부 + 지명')); 짝[id(x)] = nm; continue
            if 앞머리지명(글(x), 내줄기): out['ⓓ다른지역2'].append((x, '⑦ 낱말 앞 지명')); 짝[id(x)] = 앞머리지명(글(x), 내줄기); continue
            out['ⓓ'].append((x, None))
    return out, 짝


# 2024년 일곱 방법 뒤의 미해결분만 다시 본다. 기존 칸의 판정은 경로 집계에만 쓴다.
비교경로 = {'ⓑ': 'ⓑ', 'ⓑ2': 'ⓑ', 'ⓒ': 'ⓒ', 'ⓒ2': 'ⓒ', 'ⓓ다른지역': 'ⓓ다른지역', 'ⓓ다른지역2': 'ⓓ다른지역'}
부처경로 = defaultdict(Counter)
시도부처경로 = defaultdict(Counter)
미해결 = {}
교부경로미확인 = 'ⓓ교부경로미확인3'

def 부처사업키(x):
    return x.get('jrsdCode'), x.get('dtlbzNm')

def 이름근거(장부목록, 조각들, 조건=None):
    최고점, 장부 = 0, None
    for 낱말, y in 장부목록:
        if 조건 is None or 조건(y):
            점 = len(낱말 & 조각들)
            if 점 > 최고점:
                최고점, 장부 = 점, y
    return 최고점, 장부

# 마지막 이름 대조에서는 지명과 여러 분야에 공통인 표현을 점수에서 뺀다.
공통사업말 = re.compile('사회적|스마트|맞춤형|서비스|문화재|종합정비|정비|보수|보험료|보상비|인건비|대표|시설|지방자치|고도화|네트워크|수산물|교육훈련|글로벌|아카데미|우리마을|유적지|지역|디지털|대한민국|국제|축산분야|통합돌봄|긴급돌봄|찾아가는|공공사회복지|요양보호사|지방의료원|생활폐기물')
def 마지막이름조각(이름):
    이름 = re.sub(r'(?:동|서|남|북)(?:서울|부산|대구|인천|광주|대전|울산|제주)', ' ', 이름)
    이름 = 흔한말.sub(' ', 공통사업말.sub(' ', 지역식.sub(' ', 이름)))
    return {낱말[i:i + 5] for 낱말 in re.findall(r'[가-힣]+', 이름) for i in range(len(낱말) - 4)}

마지막장부조각 = {
    cd: [(마지막이름조각(y['dbiz_nm']), y) for y in ys]
    for cd, ys in 가.items()
} if 해 == '2024' else {}

def 집행장소(세부사업, 본문):
    장소들 = re.findall(r'(?:사업\s*(?:장소|대상지|위치)|사업장\s*소재지|위\s*치)\s*[:：]\s*([^\r\n]{1,100})', 본문)
    # 시·도와 시·군·구가 붙은 소재지만 쓴다. 두 곳 이상이면 하나로 정하지 않는다.
    # 정식 시·도+시군구가 붙은 사업명도 장소 단서로 쓴다.
    장소들 = [n(장소) for 장소 in 장소들]
    사업지명 = n(세부사업)
    지역들 = set()
    for p in 기초:
        시도 = p['시도']
        시군구 = p['이름'][len(시도):]
        주소들 = [n(s + 시군구) for s in [시도, *시도이름[시도]]]
        if any(주소 in 사업지명 for 주소 in 주소들):
            지역들.add(p['cd'])
        if len(시군구) >= 3 and 줄기수[시군구[:-1]] == 1:
            주소들.append(시군구)
        if any(주소 in 장소 for 주소 in 주소들 for 장소 in 장소들):
            지역들.add(p['cd'])
    return next(iter(지역들)) if len(지역들) == 1 else None

def _마저잇기(c, 광, x):
    cd = c['cd']
    부처사업, 세부사업 = x.get('dtlbzNm') or '', x.get('ddtlbzNm') or ''
    제목조각 = 조각(세부사업 + ' ' + 부처사업)
    내용 = x.get('상세_bsnsCn') or ''
    받은곳 = x.get('excInsttNm') or ''
    칸 = lambda 대상: 'ⓑ3' if 대상 == cd else 'ⓒ3' if 대상 == 광 else 'ⓓ다른지역3'

    종류 = 체전종류(해, 부처사업, 세부사업, 내용)
    # 공시 제목의 106회와 달리 본문 및 사업기간은 2024년 제105회에 해당한다.
    회차차이 = (부처사업 == '전국체전 지원' and '106회' in 세부사업 and '105회' in 내용
              and re.findall(r'\d{4}', x.get('상세_bsnsDe') or '') == ['2024', '2024'])
    if 회차차이:
        종류 = '전국체전'
    if 종류:
        # 개최지와 주관은 공식 대회 기록에서 확인된다. 교부 경로는 별도 증빙이 필요하다.
        if 회차차이:
            방법 = '약 — 전국체전 공시 회차 상충'
        elif 종류 == '전국장애인체전':
            방법 = '약 — 제44회 전국장애인체전 교부 경로 미확인'
        else:
            방법 = '약 — 제105회 전국체전 교부 경로 미확인'
        return 교부경로미확인, 방법, 종류 + ' · 경남 개최 기록'

    if 부처사업.startswith('문화재보수정비'):
        보수 = re.compile(r'보수|정비|보존|수장고|보호')
        국가 = re.compile(r'국가\s*지정|국보|보물|사적|천연기념물|국가민속문화')
        시도 = re.compile(r'시[·ㆍ]?도\s*지정|도\s*지정|시\s*지정|유형문화재|문화재자료')
        본문 = 세부사업 + ' ' + (x.get('상세_bsnsCn') or '') + ' ' + (x.get('상세_bsnsPurpsCn') or '')
        국가등급, 시도등급 = bool(국가.search(본문)), bool(시도.search(본문))
        등급 = (국가 if 국가등급 else 시도) if 국가등급 != 시도등급 else None
        대상조각 = 조각(re.sub(r'문화재|보수|정비|보존|설계|건립|공사', ' ', 세부사업))
        def 보수장부(y):
            제목 = y['dbiz_nm']
            등급일치 = 등급 is None or 등급.search(제목) or not (국가.search(제목) or 시도.search(제목))
            return bool(보수.search(제목)) and 등급일치
        후보 = [(대상, 이름근거(장부조각.get(대상, ()), 대상조각, 보수장부))
              for 대상 in (cd, 광)]
        후보.sort(key=lambda v: -v[1][0])
        대상, (점, 장부) = 후보[0]
        if (점 >= 2 and 점 > 후보[1][1][0]
                and f(장부, 'bdg_ntep') >= f(x, '상세_gsamt') and 지방비(장부) >= f(x, '상세_lsamt')):
            return 칸(대상), '중 — 문화재 대상·등급과 보수 장부', 장부['dbiz_nm']
        if 등급:
            등급장부 = [(대상, y) for 대상 in (cd, 광) for y in 가[대상]
                    if 등급.search(y['dbiz_nm']) and 보수.search(y['dbiz_nm'])
                    and f(y, 'bdg_ntep') >= f(x, '상세_gsamt') and 지방비(y) >= f(x, '상세_lsamt')]
            if len({대상 for 대상, _ in 등급장부}) == 1:
                대상, 장부 = 등급장부[0]
                return 칸(대상), '중 — 문화재 대상·등급과 보수 장부', 장부['dbiz_nm']

    if 부처사업 in ('새일센터 지정운영', '가족센터 운영'):
        중심 = '새일|여성새로일하기' if 부처사업.startswith('새일') else '가족센터|건강가정.*다문화가족'
        범위 = n(받은곳 + ' ' + 세부사업)
        광역명 = '|'.join(map(re.escape, [c['시도'], *(n(s) for s in 시도이름[c['시도']])]))
        시군구 = n(c['이름'][len(c['시도']):])
        기초명 = re.escape(시군구[:-1]) + '(?:시|군|구)?' if len(시군구) >= 3 else re.escape(시군구)
        광역거점 = re.search(rf'(?:광역(?:거점)?|(?:{광역명}))(?:{중심})', 범위)
        기초센터 = re.search(rf'{기초명}(?:{중심})', 범위)
        if bool(광역거점) != bool(기초센터):
            대상 = 광 if 광역거점 else cd
            장부 = [y for y in 가[대상] if re.search(중심, n(y['dbiz_nm']))]
            if 장부:
                y = max(장부, key=lambda y: len(조각(y['dbiz_nm']) & 제목조각))
                return 칸(대상), '중 — 센터 관할과 장부', y['dbiz_nm']
        if not (광역거점 and 기초센터):
            # 센터 이름에 시군구가 있어도 같은 사업이 기초 장부에 없으면 시도 경로를 확인한다.
            # 앞의 이름 단서를 뒷받침하는 장부가 없을 때만 기존 교부 패턴과 두 재원을 대조한다.
            시도센터경로 = 대표경로(시도부처경로[c['시도'], 부처사업키(x)])
            if 시도센터경로:
                대상 = cd if 시도센터경로 == 'ⓑ' else 광
                장부 = [y for y in 가[대상] if re.search(중심, n(y['dbiz_nm']))
                        and f(y, 'bdg_ntep') >= f(x, '상세_gsamt') and 지방비(y) >= f(x, '상세_lsamt')]
                if 장부:
                    y = max(장부, key=lambda y: len(조각(y['dbiz_nm']) & 제목조각))
                    return 칸(대상), '중 — 센터 관할과 장부', y['dbiz_nm']

    # 국회예산정책처 2023 결산 분석에서 확인한 이월사업의 마지막 간접보조 지자체.
    # https://www.nabo.go.kr/board/file/down.do?fid=33318084
    if 부처사업 == '천연물안전관리원 구축' and '양산시' in 내용 and '천연물안전관리원' in 세부사업:
        양산 = next(p['cd'] for p in 기초 if p['이름'] == '경남양산시')
        return 칸(양산), '중 — 전년도 결산서의 교부 경로', '2023회계연도 결산 · 경남양산시'

    # 문화체육관광부의 스마트 관광도시 선정과 대회 주최 측의 2024년 개최 요강.
    # https://mcst.go.kr/servlets/eduport/front/upload/UplDownloadFile?pPath=0302000000&pRealName=20230308091113924783.pdf
    # https://www.kbaduk.or.kr/bbs/view/competition/domestic/982/www.kbaduk.or.kr
    if 부처사업 == '스마트관광 기반 조성' and '통영스마트관광' in n(세부사업):
        return 교부경로미확인, '약 — 공모 선정·개최지 확인', '경남통영시 스마트관광도시 공모 선정'
    if 부처사업.startswith('지역스포츠산업지원') and '제3회1004섬신안전국아마바둑대회' in re.sub(r'\s+', '', 세부사업):
        return 교부경로미확인, '약 — 공모 선정·개최지 확인', '전남신안군 전국 아마바둑대회 개최'

    if re.search(r'공단|공사|협회|진흥원', 받은곳) or '급식관리지원센터' in 부처사업:
        대상 = 집행장소(세부사업, 내용)
        if 대상 and 대상 != cd:
            점, 장부 = 이름근거(장부조각.get(대상, ()), 제목조각)
            if 점 >= 2 and f(장부, 'bdg_ntep') >= f(x, '상세_gsamt') and 지방비(장부) >= f(x, '상세_lsamt'):
                return 칸(대상), '중 — 공시 사업장소와 장부', 장부['dbiz_nm']

    # 공시의 업무와 장부 항목이 같은 표현으로 확인되고 두 재원 모두 수용 가능한 곳.
    이름변형 = {
        '청소년지도사 배치지원': (r'청소년지도사', r'청소년.*지도사'),
        '청소년상담복지센터 운영지원': (r'청소년안전망|청소년상담복지센터', r'청소년안전망|청소년상담복지센터'),
        '생활체육지도자 활동 지원': (r'생활체육지도자|일반지도자|어르신지도자', r'생활체육지도자|체육지도자'),
        '학교 밖 청소년 급식지원': (r'급식', r'학교밖청소년.*급식'),
    }
    if (부처사업 == '생활체육지도자 활동 지원' and c['시도'] == '서울'
            and re.search(r'서울시민(?:체육)?대축전', n(세부사업))
            and any(n(y['dbiz_nm']) == '서울시민체육대축전운영' for y in 가[광])):
        return 칸(광), '중 — 세부 업무와 장부 항목', '서울시민 체육대축전 운영'
    if 부처사업 in 이름변형:
        공시식, 장부식 = 이름변형[부처사업]
        if re.search(공시식, n(세부사업 + ' ' + 내용)):
            후보 = [(대상, y) for 대상 in (cd, 광) for y in 가[대상]
                    if re.search(장부식, n(y['dbiz_nm']))
                    and f(y, 'bdg_ntep') >= f(x, '상세_gsamt') and 지방비(y) >= f(x, '상세_lsamt')]
            if len({대상 for 대상, _ in 후보}) == 1:
                대상, 장부 = 후보[0]
                return 칸(대상), '중 — 세부 업무와 장부 항목', 장부['dbiz_nm']

    기관, 사업 = 부처사업키(x)
    경로 = 대표경로(부처경로[(기관, 사업)]) if 기관 and 사업 else None
    시도표 = 시도부처경로[c['시도'], (기관, 사업)]
    시도일치 = 경로 and 시도표[경로] > 0 and 시도표[경로] * 2 >= sum(시도표.values())
    # 이 사업은 광역 공모 근거와 2024년 공시의 압도적인 광역 비중이 함께 있다.
    # https://www.moel.go.kr/local/jeonju/news/notice/noticeView.do?bbs_seq=20231201048
    광역공모 = False
    if 경로 == 'ⓒ' and 부처사업 == '지역산업맞춤형 자치단체 지원 사업(경상보조)':
        광역정식명 = '|'.join(map(re.escape, 시도이름[c['시도']]))
        공동재원 = re.search(rf'고용노동부[^\n]{{0,24}}(?:{광역정식명})|(?:{광역정식명})[^\n]{{0,24}}고용노동부', 내용)
        # 울산시의 자동차·석유화학 상생협약 선정과 세부 지원사업 모집 공고.
        # https://www.bizinfo.go.kr/sii/siia/selectSIIA200Detail.do?pblancId=PBLN_000000000099628
        # https://www.ulsan.go.kr/u/rep/bbs/view.do?bbsId=BBS_0000000000000027&dataId=164326&mId=001004003001000000
        울산상생 = (c['시도'] == '울산' and '울산' in 내용
                   and re.search(r'(자동차부품|석유화학)업종.*(일자리채움|도약장려금|복지|계속고용)', n(세부사업)))
        광역공모 = 공동재원 or 울산상생 or re.search(r'지역혁신프로젝트|지역주도이중구조|지역체감형일자리', n(세부사업))
    기초경로충돌 = 경로 == 'ⓑ' and re.search(r'^(시도형|광역형)', n(세부사업))
    if (시도일치 or 광역공모) and not 기초경로충돌:
        대상 = cd if 경로 == 'ⓑ' else 광
        # 대상은 받은 곳 주소로 고른 곳이라, 그 장부에 이름이 맞는 사업이 있을 때만 잇는다(금액은 마저잇기 가 본다)
        점, 장부 = 이름근거(장부조각.get(대상, ()), 제목조각)
        if 점 >= 2:
            return 칸(대상), '중 — 같은 부처 사업의 주된 경로', 장부['dbiz_nm']

    조각들 = 마지막이름조각(세부사업 + ' ' + 부처사업)
    기초점, 기초장부 = 이름근거(마지막장부조각.get(cd, ()), 조각들)
    광역점, 광역장부 = 이름근거(마지막장부조각.get(광, ()), 조각들)
    경로, 방법 = 마지막경로(기초점, 광역점)
    if 방법 == '약 — 이름 일부':
        장부 = 기초장부 if 경로 == 'ⓑ3' else 광역장부
        return 경로, 방법, 장부['dbiz_nm']
    return 경로, 방법, '장부 근거 없음'

# 보탬e(지자체가 단체에 준 보조금 공시)에 같은 받은 곳·같은 사업이 한 지자체에만 있으면 그 지자체를 거친 것으로 본다.
# 주소로 지자체를 고르지 않고 전국 보탬e 에서 찾는다(11-11 사용자 「주소로는 어느 지역 사업인지 확인할 수 없다」).
# 원본은 R2 돈길/botem_<해>.json.gz → data/raw/(받은 곳 이름이 있어 저장소에 안 둠) — 없으면 건너뛴다.
보탬e = defaultdict(list)
_p = os.path.join(ROOT, 'data', 'raw', f'botem_{해}.json.gz')
if os.path.exists(_p):
    _줄임 = {full: s for s, fulls in 시도이름.items() for full in fulls}
    _역 = {v: k for k, v in 곳이름.items()}
    for r in json.load(gzip.open(_p, 'rt', encoding='utf-8')):
        _곳 = _줄임.get(r['_광역'], r['_광역']) + ('본청' if r['_곳'] == r['_광역'] else r['_곳'])
        r['_cd'] = _역.get({'인천서해구': '인천서구'}.get(_곳, _곳))
        보탬e[이름정규화(법인표기.sub('', r.get('pfmInstNm') or ''))].append(r)
else:
    print(f'botem_{해}.json.gz 없음 — 보탬e 잇기 건너뜀')

def 보탬e잇기(c, 광, x):
    z = 조각((x.get('ddtlbzNm') or '') + ' ' + (x.get('dtlbzNm') or ''))
    맞 = [r for r in 보탬e.get(이름정규화(법인표기.sub('', x.get('excInsttNm') or '')), ())
         if r['_cd'] and len(조각(r.get('pfmBizNm') or '') & z) >= 2]
    곳들 = {r['_cd'] for r in 맞}
    if len(곳들) != 1:
        return None   # 없거나 여러 곳이면 모른다
    대상 = 곳들.pop()
    교부 = sum(float(r.get('bizctSbatAmt') or 0) for r in 맞)
    방법 = '중 — 보탬e 같은 받은 곳·사업' if 교부 >= f(x, '상세_gsamt') - 1 else '약 — 보탬e 같은 받은 곳·사업(교부액이 국비보다 작음)'
    return ('ⓑ3' if 대상 == c['cd'] else 'ⓒ3' if 대상 == 광 else 'ⓓ다른지역3'), 방법, f'보탬e · {곳이름[대상]}'

# 장부 사업 하나(같은 이름 묶음)에 붙인 공시 국비가 그 장부 국비를 넘으면 붙이지 않고 주소 추정으로 돌린다.
# 앞 단계(ⓑ·ⓒ·ⓑ2·ⓒ2)가 같은 장부에 먼저 붙인 돈도 센다 — 광역 장부는 그 시·도 기초 모두가 나눠 쓴다.
붙인국비 = Counter()
def 마저잇기(c, 광, x):
    경로, 방법, 근거 = _마저잇기(c, 광, x)
    대상 = {'ⓑ3': c['cd'], 'ⓒ3': 광}.get(경로)
    열쇠 = (대상, n(근거))
    한도 = 사업묶음(대상).get(열쇠[1]) if 대상 in 가 else None
    if 한도:
        if 붙인국비[열쇠] + f(x, '상세_gsamt') > 한도 + 1e6:
            경로, 방법, 근거 = 'ⓓ지역모름3', '모름 — 장부 금액 넘침', '장부 근거 없음'
        else:
            붙인국비[열쇠] += f(x, '상세_gsamt')
    if 경로 == 'ⓓ지역모름3':
        return 보탬e잇기(c, 광, x) or (경로, 방법, 근거)
    return 경로, 방법, 근거

받은곳이름 = set()
for x in 줄:
    받은곳이름.update(수령인이름표기(x.get('excInsttNm')))
for d in 상.values():
    if d:
        for 필드 in ('excInsttNm', 'insttNm'):
            받은곳이름.update(수령인이름표기(d.get(필드)))
이름길이 = sorted({len(이름) for 이름 in 받은곳이름 if len(이름) >= 3})

def 이름포함(글):
    글 = unicodedata.normalize('NFKC', 글).casefold()
    이름 = 이름정규화(글)
    if 이름 in 받은곳이름 or any(낱말 in 받은곳이름 for 낱말 in re.findall(r'[가-힣a-z0-9]+', 글)):
        return True
    return any(
        이름[i:i + 길이] in 받은곳이름
        for 길이 in 이름길이 if 길이 <= len(이름)
        for i in range(len(이름) - 길이 + 1)
    )

def 공개예(글, x, 길이=40):
    글 = str(글 or '')
    이름 = 이름정규화(글)
    수령인 = set().union(*(수령인이름표기(x.get(k)) for k in ('excInsttNm', '상세_excInsttNm', '상세_insttNm')))
    표시 = 글[:길이]
    if (any(이름값 in 이름 for 이름값 in 수령인) or 이름포함(글)
            or (표시 != 글 and 이름포함(표시))):
        return '[비공개]'
    return 표시

def 빈집계():
    return {'줄': 0, '국비': 0, '지방비': 0}

def 집계기록(집계, x):
    집계['줄'] += 1
    집계['국비'] += round(f(x, '상세_gsamt'))
    집계['지방비'] += round(f(x, '상세_lsamt'))

def 대조기록(대조, x, 방법, 근거, 경로=None):
    d = 대조.setdefault(방법, {**빈집계(), '예': []})
    집계기록(d, x)
    if 경로:
        경로집계 = d.setdefault('경로', {}).setdefault(경로, 빈집계())
        집계기록(경로집계, x)
    if len(d['예']) < 3:
        예 = [공개예(x.get('ddtlbzNm'), x), 공개예(근거, x)]
        if 경로:
            예.append(경로)
        d['예'].append(예)

결과 = {}
for c in 기초:
    시도, 이름 = c['시도'], c['이름'][len(c['시도']):]
    g = [x for 앞 in 시도이름[시도] for 뒤 in 옛이름.get(c['cd'], [이름]) for x in 주소별.get((앞, 뒤), [])]
    광 = 광역코드[시도]
    줄기 = re.sub(r'(시|군|구)$', '', 이름)
    묶 = defaultdict(list); 후보 = defaultdict(list)
    for x in g:
        if f(x, '상세_lsamt') == 0: 묶['ⓐ'].append((x, None)); continue
        받은곳 = x.get('excInsttNm') or ''
        if re.search(r'(초등|중|고등|공업고등|마이스터고등|특수)?학교$', 받은곳) and '대학교' not in 받은곳: 묶['교육청'].append((x, None)); continue
        남 = set(지역식.findall((x.get('dtlbzNm') or '') + ' ' + (x.get('ddtlbzNm') or ''))) - {이름} - set(시도이름[시도])
        if 남: 묶['ⓓ다른지역'].append((x, None)); continue
        광기관 = re.search(광역기관[시도], 받은곳)
        k = None if 광기관 else 짝(x, c['cd'])
        if k: 후보[k].append(x); continue
        k = 짝(x, 광)
        if k: 묶['ⓒ'].append((x, k)); continue
        묶['ⓓ'].append((x, None))
    # ⭐ 뻥튀기 막기(2026-11-09 사용자 「금액 뻥튀기 안되게」) — 한 사업에 붙은 공시 국비가 가계부 국비를 넘으면
    #    넘치는 줄은 광역으로 옮긴다(광역 사업을 기초에 붙인 것 — 새일센터·통합문화이용권). 받은 곳 이름에 이 곳 이름이 든 줄을 먼저 담는다.
    판 = Counter(); 넘침 = []
    for k, xs in 후보.items():
        한도 = 사업묶음(c['cd'])[k] + 1e6
        담 = 0
        for x in sorted(xs, key=lambda x: (줄기 not in (x.get('excInsttNm') or ''), f(x, '상세_gsamt'))):
            if 담 + f(x, '상세_gsamt') <= 한도:
                담 += f(x, '상세_gsamt'); 묶['ⓑ'].append((x, k))
            else:
                k2 = 짝(x, 광)
                묶['ⓒ' if k2 else 'ⓓ'].append((x, k2)); 넘침.append(x)
        판['같음' if abs(담 - 사업묶음(c['cd'])[k]) < 1e6 else '작음'] += 1
    사업 = 후보
    큰 = [[공개예(x.get('ddtlbzNm'), x), round(f(x, '상세_gsamt'))] for x in sorted(넘침, key=lambda x: -f(x, '상세_gsamt'))]
    판['넘쳐 옮긴 줄'] = len(넘침); 판['넘친 국비'] = round(sum(f(x, '상세_gsamt') for x in 넘침))
    다시, 짝들 = 다시잇기(c, 광, [x for x, _ in 묶.pop('ⓓ', [])])
    대조 = {}
    for k, v in 다시.items():
        묶[k] += v
        for x, 방법 in v:
            if 방법:
                대조기록(대조, x, 방법, 짝들.get(id(x)))
    if 해 == '2024':
        if 묶.get('ⓓ'):
            미해결[c['cd']] = [x for x, _ in 묶['ⓓ']]
        for 칸, 장부 in (('ⓑ', c['cd']), ('ⓒ', 광), ('ⓑ2', c['cd']), ('ⓒ2', 광)):
            for x, k in 묶.get(칸, ()):
                k = k if 칸 in ('ⓑ', 'ⓒ') else n(짝들.get(id(x)))
                if k: 붙인국비[장부, k] += f(x, '상세_gsamt')
        for 칸, 경로 in 비교경로.items():
            for x, _ in 묶.get(칸, ()):
                키 = 부처사업키(x)
                부처경로[키][경로] += 1
                시도부처경로[c['시도'], 키][경로] += 1
    세 = 세입.get(c['cd'], {})
    결과[c['cd']] = {
        '이름': c['이름'], '시도': 시도,
        '①': {'교부세등': 세.get('30000', 0), '조정교부금등': 세.get('40000', 0)},
        '②': {'국고보조금등': 세.get('51000', 0), '가계부국비': round(sum(f(y, 'bdg_ntep') for y in 가[c['cd']])), '가계부국비사업수': len(가[c['cd']])},
        '③': {k: {'줄': len(v), '국비': round(sum(f(x, '상세_gsamt') for x, _ in v)), '지방비': round(sum(f(x, '상세_lsamt') for x, _ in v))} for k, v in 묶.items()},
        '검사': {'사업': len(사업), **판, '넘친줄예': 큰[:5]},
        '대조': dict(대조),
        '주소줄': len(g),
    }

if 해 == '2024':
    for c in 기초:
        cd, 광 = c['cd'], 광역코드[c['시도']]
        if cd not in 미해결:
            continue
        곳결과 = 결과[cd]
        곳결과['③'].pop('ⓓ')
        for x in 미해결[cd]:
            경로, 방법, 근거 = 마저잇기(c, 광, x)
            대조기록(곳결과['대조'], x, 방법, 근거, 경로)
            집계기록(곳결과['③'].setdefault(경로, 빈집계()), x)

공시결과 = {'해': 해, '곳': 결과}
if 해 == '2024':
    공시결과['③금액기준'] = 'e나라도움 교부신청서 총사업비의 국고보조금·지자체부담금'
    공시결과['③경로기준'] = {
        'ⓐ': '교부신청서의 지자체부담금 0',
        교부경로미확인: '개최·선정 근거 확인, 교부 경로 미확인',
        'ⓓ지역모름3': '어느 지역 사업인지 모름 — 받은 곳 주소로만 이 곳 밑에 둠(지자체 몫에 더하지 않는다)',
    }
json.dump(공시결과, open(os.path.join(ROOT, 'data', f'grants_flow_{해}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# 요약
억 = lambda v: f'{v / 1e8:,.0f}'
print(f'기초 {len(결과)}곳 · {해}')
print('주소 줄이 0인 곳:', [v['이름'] for v in 결과.values() if not v['주소줄']])
세입빈 = [v['이름'] for v in 결과.values() if not v['②']['국고보조금등']]
print('세입결산이 빈 곳:', 세입빈)
합 = Counter(); 줄합 = Counter()
for v in 결과.values():
    for k, w in v['③'].items(): 합[k] += w['국비']; 줄합[k] += w['줄']
print('③ 전체:', {k: f'{줄합[k]:,}줄 {억(합[k])}억' for k in sorted(합)})
대합 = defaultdict(Counter)
for v in 결과.values():
    for k, w in v['대조'].items(): 대합[k].update({a: b for a, b in w.items() if a in ('줄', '국비', '지방비')})
print('못 이음 다시 잇기:', {k: f"{w['줄']:,}줄 국비+지방비 {억(w['국비'] + w['지방비'])}억" for k, w in sorted(대합.items())})
검 = Counter()
for v in 결과.values():
    for k in ('같음', '작음', '넘쳐 옮긴 줄', '넘친 국비'): 검[k] += v['검사'].get(k, 0)
print('ⓑ 사업 검사 전체:', {k: (f'{w / 1e8:,.0f}억' if k == '넘친 국비' else w) for k, w in 검.items()}, f"· 같음 비율 {검['같음'] / max(1, 검['같음'] + 검['작음']):.0%}")
나쁜 = sorted(결과.values(), key=lambda v: -v['검사'].get('넘친 국비', 0))[:12]
print('넘친 국비가 큰 곳:')
for v in 나쁜:
    b = v['③'].get('ⓑ', {'줄': 0})
    print(f"  {v['이름']}: ⓑ {b['줄']}줄 · 사업 {v['검사']['사업']} · 같음 {v['검사'].get('같음', 0)} · 넘친 줄 {v['검사'].get('넘쳐 옮긴 줄', 0)} ({v['검사'].get('넘친 국비', 0) / 1e8:,.1f}억) · 예 {v['검사']['넘친줄예'][:2]}")
비율순 = sorted(결과.values(), key=lambda v: v['③'].get('ⓑ', {'국비': 0})['국비'] / max(1, v['②']['국고보조금등']))
print('② 대비 ⓑ 비율(낮은/높은 곳):', [(v['이름'], f"{v['③'].get('ⓑ', {'국비': 0})['국비'] / max(1, v['②']['국고보조금등']):.1%}") for v in 비율순[:3] + 비율순[-3:]])
