# e나라도움 국고보조금 보조사업자 정보공시 수집기 — **국비로 누가 얼마 받았나**(보탬e 는 지방비 보조뿐이다)
#
#   python scripts/fetch_national_grants.py               최근 5년(올해-5 ~ 올해-1) 목록 + 상세
#   python scripts/fetch_national_grants.py 2024          그 해만
#   python scripts/fetch_national_grants.py --목록만       상세(주소·국비/지방비/자부담)는 안 부른다
#   python scripts/fetch_national_grants.py --시간 300     300분까지만 부르고 멈춘다(다음에 부르면 이어 받는다 — 봇이 날마다 이렇게 돈다)
#
# 창구 — e나라도움 대민 누리집 bojo.go.kr 의 「보조사업자 정보공시」 화면이 부르는 것을 그대로 부른다. 열쇠 없음(2026-10-26 찾음).
#   목록  POST /ea/retrieveInfoPblntfTrgetMngList.do  — 부처(jrsdCode)마다, 50줄씩(100줄부터 「조회 범위 초과」)
#         ⚠️ ifpbntSysSeCode=001 을 꼭 보낸다 — 없으면 「공시구분을 선택해주십시오」. selectedMultiSysSeCode 는 보내지 않는다(보내면 그 구분만 남는다)
#   상세  ① /ea/retrieveInfoPblntfDelvryReqstdoc.do → 과제번호(taskNo) ② 같은 값 + taskNo 로 /ea/retrieveInfoPblntfDelvryReqstdoc2.do
#         → 주소·총사업비·국고보조금·지자체부담금·자기부담금. ②를 taskNo 없이 부르면 오류 화면이 온다(10-26 한참 헤맴).
#         손으로 적은 공시(hwipnBassId 있음)는 ①을 건너뛰고 ②만.
# ⚠️ 목록엔 「어느 지자체」 칸이 없다 — 상세의 주소로 시·도·시·군·구를 붙인다(받은 곳이 있는 곳이지, 돈을 댄 지자체와 다를 수 있다).
# ⚠️ 상세엔 대표자·전화·이메일·담당자 이름·접속 IP 가 온다 — **담지 않는다.** 주소는 시·군·구까지만(개인 농가면 집 주소다).
# ⭐ 원자료는 통째로 담는다(빈 칸·세션 칸만 뺀다) — 필요한 건 나중에 뽑는다.
# ⭐ 공시는 해가 지나도 계속 확정된다(2024 사업이 2026-09 에 확정) — 올해-2 뒤의 목록은 7일 지나면 다시 받는다. 상세는 한 번 받으면 다시 안 부른다.
#    목록 한 해 ≈ 1시간(50줄에 3.6초), 상세 한 줄 ≈ 0.4초 — 5년치 상세는 이틀 넘게 걸린다.
# 결과: data/national_grants/<해>.json.gz (목록) · data/national_grants/상세_<해>.json.gz ({열쇠: 상세})

import gzip, http.cookiejar, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import date

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'national_grants')
B = 'https://bojo.go.kr'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
쪽 = 50
뺄칸 = {'registIp', 'updtIp', 'registerId', 'updusrId', 'rprsntvNm', 'telno', 'email', 'userNm', 'reqstManId', 'reqstManNm',
       'opetrId', 'opetrNm', 'currentPageNum', 'countPerPageNum', 'totalNum'}

op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def 부르기(길, 몸, 되풀이=4):
    끝 = None
    for n in range(되풀이):
        try:
            req = urllib.request.Request(B + 길, data=urllib.parse.urlencode(몸).encode(),
                                         headers={'User-Agent': UA, 'X-Requested-With': 'XMLHttpRequest', 'Referer': B + '/ea/getEA001201View.do',
                                                  'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})
            s = op.open(req, timeout=120).read().decode('utf-8', 'replace')
            if s.lstrip().startswith('{'):
                return json.loads(s)
            끝 = '오류 화면'
        except Exception as e:
            끝 = e
        time.sleep(5 * (n + 1))
        세션()
    print(f'   ⚠️ {길} 네 번 다 실패: {끝!r}', flush=True)
    return None


def 세션():
    op.open(urllib.request.Request(B + '/ea/getEA001201View.do', headers={'User-Agent': UA}), timeout=60).read()


def 다듬기(x):
    return {k: v.strip() if isinstance(v, str) else v for k, v in x.items()
            if v not in (None, '') and not k.startswith('ss') and k not in 뺄칸}


def 시군구(주소):
    # 「경기도 수원시 장안구 정조로」 → 경기도 수원시 장안구. 시·도·시·군·구 낱말까지만 남긴다
    남김 = []
    for w in (주소 or '').split():
        if len(남김) < 3 and re.search(r'(도|시|군|구)$', w) and not re.search(r'(로|길)$', w):
            남김.append(w)
        else:
            break
    return ' '.join(남김)


def 읽기(path, 기본):
    return json.load(gzip.open(path, 'rt', encoding='utf-8')) if os.path.exists(path) else 기본


def 쓰기(path, d):
    tmp = path + '.tmp'
    with gzip.open(tmp, 'wt', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, separators=(',', ':'))
    os.replace(tmp, path)


def 목록(해):
    부처 = (부르기('/zz/retrieveJrsdJrsdSearch2.do', {'fsyr': 해}) or {}).get('codeList') or []
    줄 = []
    for b in 부처:
        n = 1
        while True:
            d = 부르기('/ea/retrieveInfoPblntfTrgetMngList.do', {
                'basisCode': 1, 'bsnsyear': 해, 'fsyr': 해, 'fiscalyear': 해, 'jrsdCode': b['code'],
                'currentPageNum': n, 'countPerPageNum': 쪽, 'sortOrder': 0, 'searchFilterYn': 'N', 'ifpbntSysSeCode': '001'})
            r = (d or {}).get('RESULT_KEY') or []
            if d is None:
                raise SystemExit(f'{해} {b["codeNm"]} {n}쪽을 못 받았다 — 목록이 반쪽이 되니 멈춘다')
            줄 += [다듬기(x) for x in r]
            모두 = int(r[0]['totalNum']) if r else 0
            if n * 쪽 >= 모두:
                break
            n += 1
        print(f'   {해} {b["codeNm"]}: {모두:,}줄', flush=True)
    return 줄


def 열쇠(x):
    return '|'.join(str(x.get(k, '')) for k in ('bsnsyear', 'excInsttId', 'ddtlbzId', 'dtlbzId', 'hwipnBassId'))


def 상세(x):
    몸 = {'callType': 'C', 'basisCode': 1, 'bsnsyear': x['bsnsyear'], 'fiscalyear': x.get('fiscalyear', x['bsnsyear']),
          'excInsttId': x.get('excInsttId', ''), 'ddtlbzId': x.get('ddtlbzId', ''), 'dtlbzId': x.get('dtlbzId', ''),
          'jrsdCode': x.get('jrsdCode', ''), 'hwipnBassId': x.get('hwipnBassId', '')}
    if not x.get('hwipnBassId'):
        d = 부르기('/ea/retrieveInfoPblntfDelvryReqstdoc.do', 몸)
        if d is None:
            return None
        if not d.get('result'):
            return {'없음': '과제번호 없음'}
        몸['taskNo'] = d['result'][0].get('taskNo', '')
    d = 부르기('/ea/retrieveInfoPblntfDelvryReqstdoc2.do', 몸)
    if d is None:
        return None
    v = d.get('detailVO') or {}
    out = 다듬기({k: val for k, val in v.items() if k not in ('rdnmDetailAdres', 'bsnsPlaceAdres')})
    out['주소'] = 시군구(v.get('rdnmDetailAdres'))
    if v.get('bsnsPlaceAdres'):
        out['사업장소'] = 시군구(v['bsnsPlaceAdres'])
    return out or {'없음': '상세 빔'}


def main():
    os.makedirs(OUT, exist_ok=True)
    인자 = sys.argv[1:]
    해들 = [int(a) for a in 인자 if re.fullmatch(r'20\d\d', a)] or list(range(date.today().year - 1, date.today().year - 6, -1))   # 「--시간 290」의 290 을 해로 읽었다(10-26 첫 실행)
    분 = float(인자[인자.index('--시간') + 1]) if '--시간' in 인자 else None
    끝시각 = time.time() + 분 * 60 if 분 else None
    세션()

    for 해 in 해들:
        path = os.path.join(OUT, f'{해}.json.gz')
        if os.path.exists(path):
            지난날 = (date.today() - date.fromisoformat(읽기(path, {})['만든날'])).days
            if 해 < date.today().year - 2 or 지난날 < 7:
                print(f'{해} 목록은 받아 둔 것을 쓴다({지난날}일 전)', flush=True)
                continue
        if 끝시각 and 끝시각 - time.time() < 90 * 60:   # 한 해 목록이 한 시간쯤 — 중간에 잘리면 그 해를 통째로 날린다
            print(f'{해} 목록은 시간이 모자라 다음에 받는다', flush=True)
            continue
        print(f'{해} 목록 받기', flush=True)
        줄 = 목록(해)
        쓰기(path, {'만든날': date.today().isoformat(), '해': 해, '출처': 'e나라도움 보조사업자 정보공시(bojo.go.kr) 국고', '줄': 줄})
        print(f'{해} 목록 {len(줄):,}줄 → {path}', flush=True)

    if '--목록만' in 인자:
        return
    # 상세 — 주소를 먼저 넓게: 아직 주소를 모르는 받은 곳부터, 새 해부터
    상세들 = {해: 읽기(os.path.join(OUT, f'상세_{해}.json.gz'), {}) for 해 in 해들}
    아는곳 = {k.split('|')[1] for d in 상세들.values() for k, v in d.items() if v.get('주소')}
    할일 = []
    for 해 in 해들:
        for x in 읽기(os.path.join(OUT, f'{해}.json.gz'), {'줄': []})['줄']:   # 목록을 아직 못 받은 해는 빈다
            if 열쇠(x) not in 상세들[해]:
                할일.append((x.get('excInsttId') in 아는곳, 해, x))
    할일.sort(key=lambda t: t[0])   # 주소 모르는 곳 먼저(안정 정렬이라 해 차례는 그대로)
    print(f'상세 남은 것 {len(할일):,}건', flush=True)
    for n, (_, 해, x) in enumerate(할일):
        if 끝시각 and time.time() > 끝시각:
            print('시간이 다 돼 멈춘다 — 다시 부르면 이어 받는다', flush=True)
            break
        d = 상세(x)
        if d is None:
            continue
        상세들[해][열쇠(x)] = d
        if d.get('주소'):
            아는곳.add(x.get('excInsttId'))
        if n % 200 == 199:
            for h, dd in 상세들.items():
                쓰기(os.path.join(OUT, f'상세_{h}.json.gz'), dd)
            print(f'   상세 {n + 1:,}/{len(할일):,} · 주소 아는 곳 {len(아는곳):,}', flush=True)
        time.sleep(0.2)
    for h, dd in 상세들.items():
        쓰기(os.path.join(OUT, f'상세_{h}.json.gz'), dd)
    print('끝', {h: len(dd) for h, dd in 상세들.items()}, flush=True)


if __name__ == '__main__':
    main()
