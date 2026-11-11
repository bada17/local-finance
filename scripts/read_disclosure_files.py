# 재정공시 화면에 붙은 파일을 **받아서 안의 글자를 뽑는다** — 항목이 파일 안에 있나를 이름이 아니라 내용으로 보려고.
#   (2026-11-11 사용자 「짐작하지 말고 명확하게」 — 묶음 파일 안에 무엇이 들었는지 열어 본다)
#
#   python scripts/read_disclosure_files.py            받기(바로 받기 → 안 되면 크롬으로 누르기) + 글자 뽑기
#   python scripts/read_disclosure_files.py 1111000    그 곳만(시험)
#
# 어디서 — data/disclosure_dom.json(recheck_disclosure.js)의 파일 목록. 이름에 적힌 해가 옛 것(기준해 앞)이면 안 받는다.
# 받기 — read_budget_books.py 처럼 urllib(Referer=그 화면) 먼저, 자바스크립트 단추·실패는 click_budget_books.js 로 누른다.
#   30MB 넘는 것은 안 받는다(예산서 책이 대부분) — 「30MB 넘음」으로 적는다.
# 읽기 — pdf 는 쪽마다, hwp·hwpx 는 문단, 엑셀은 칸. **못 읽은 것은 못 읽은 까닭을 적는다**(그림 pdf·배포용 hwp …).
#
# 결과: data/disclosure_files.json — 파일마다 {곳, 이름, 주소, 바탕, 꼴, 쪽수, 글자수, 까닭}
#   뽑은 글자는 캐시(%LOCALAPPDATA%\local-finance-files\공시\<열쇠>.txt, 쪽 사이 \f)에 — 크고 많아 저장소에 안 넣는다.
import concurrent.futures as cf, hashlib, io, json, os, re, struct, subprocess, sys, urllib.error, urllib.parse, urllib.request, zipfile, zlib

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_transparency as B   # noqa: E402  요즘것·기준해 잣대를 같이 쓴다
import read_post_files as R      # noqa: E402  표꺼내기·한글 글자 풀기

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
캐시 = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'local-finance-files', '공시')
OUT = os.path.join(ROOT, 'data', 'disclosure_files.json')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
한도 = 30_000_000
기준해 = __import__('datetime').date.today().year - 2


def 누를것(주소):
    return not 주소 or 주소.lower().startswith('javascript') or 주소.startswith('#') or not re.match(r'^(https?:)?/|^[\w./-]+(\?|$)', 주소)


def 열쇠(cd, 바탕, f):
    return cd + '_' + hashlib.sha1((바탕 + f['주소'] + (f['이름'] if 누를것(f['주소']) else '')).encode()).hexdigest()[:12]


# ── 글자 뽑기: 쪽(또는 시트·구역)을 \f 로 가른 글 하나를 돌려준다 ──
def 글_pdf(몸):
    import pymupdf
    쪽들 = [p.get_text() for p in pymupdf.open(stream=몸, filetype='pdf')]
    if sum(len(s.strip()) for s in 쪽들) < 30:
        raise R.못읽음('그림 pdf(글자 없음)')
    return '\f'.join(쪽들)


def 글_hwpx(몸):
    z = zipfile.ZipFile(io.BytesIO(몸))
    구역 = []
    for n in sorted(x for x in z.namelist() if re.match(r'Contents/section\d+\.xml', x)):
        x = z.read(n).decode('utf-8', 'replace')
        구역.append('\n'.join(''.join(re.findall(r'<hp:t>([^<]*)</hp:t>', p)) for p in re.findall(r'<hp:p\b.*?</hp:p>', x, re.S)))
    return '\f'.join(구역)


def 글_hwp(몸):
    import olefile
    ole = olefile.OleFileIO(io.BytesIO(몸))
    깃 = struct.unpack('<I', ole.openstream('FileHeader').read()[36:40])[0]
    if 깃 & 2:
        raise R.못읽음('암호 걸린 hwp')
    if 깃 & 4:
        raise R.못읽음('배포용 hwp(복사 막음)')
    구역 = []
    for s in sorted((s for s in ole.listdir() if s[0] == 'BodyText'), key=lambda s: int(re.sub(r'\D', '', s[1]) or 0)):
        b = ole.openstream(s).read()
        if 깃 & 1:
            b = zlib.decompress(b, -15)
        줄, i = [], 0
        while i + 4 <= len(b):   # 레코드 머리(태그·수준·크기)를 따라가며 문단 글자(0x43)만
            h = struct.unpack('<I', b[i:i + 4])[0]
            tag, sz = h & 0x3FF, (h >> 20) & 0xFFF
            i += 4
            if sz == 0xFFF:
                sz = struct.unpack('<I', b[i:i + 4])[0]
                i += 4
            if tag == 0x43:
                줄.append(R._hwp_글(b[i:i + sz]))
            i += sz
        구역.append('\n'.join(줄))
    return '\f'.join(구역)


def 글뽑기(몸, 확장자=''):
    """(글, 꼴) — 확장자를 믿지 않고 앞머리로 가른다."""
    if 몸[:4] == b'PK\x03\x04':
        z = zipfile.ZipFile(io.BytesIO(몸))
        이름들 = z.namelist()
        if any(n.startswith('Contents/') for n in 이름들):
            return 글_hwpx(몸), 'hwpx'
        if any(n.startswith('xl/') for n in 이름들):
            return '\f'.join('\n'.join('\t'.join(r) for r in t) for t in R.표_xlsx(몸)), 'xlsx'
        글들 = []
        for n in 이름들:
            if not n.endswith('/'):
                try:
                    g, k = 글뽑기(z.read(n), os.path.splitext(n)[1][1:])
                    글들.append(g)
                except Exception:
                    pass
        return '\f'.join(글들), 'zip'
    if 몸[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
        import olefile
        if olefile.OleFileIO(io.BytesIO(몸)).exists('FileHeader'):
            return 글_hwp(몸), 'hwp'
        return '\f'.join('\n'.join('\t'.join(r) for r in t) for t in R.표_xls(몸)), 'xls'
    if 몸[:5] == b'%PDF-':
        return 글_pdf(몸), 'pdf'
    if 확장자 == 'csv':
        return '\n'.join('\t'.join(r) for r in R.표_csv(몸)[0]), 'csv'
    머리 = 몸[:600].lstrip(b'\xef\xbb\xbf \r\n\t')
    if 머리.startswith(b'<?xml') and b'<HWPML' in 머리:   # XML 한글(hwpml) — 문단 <P> 안의 <CHAR> 글자
        x = 몸.decode('utf-8', 'replace')
        return '\n'.join(''.join(re.findall(r'<CHAR[^>]*>([^<]*)</CHAR>', p)) for p in re.findall(r'<P\b.*?</P>', x, re.S)), 'hwpml'
    if not 몸.strip():
        raise R.못읽음('빈 파일')
    if 몸.startswith(b'HWP Document File V3'):
        raise R.못읽음('옛 한글(HWP 3.0) — 못 읽음')
    if 몸.startswith(b'EGGA'):
        raise R.못읽음('알집 EGG 압축 — 못 읽음')
    if 몸.startswith(b'PK\x05\x06'):
        raise R.못읽음('빈 압축 파일')
    if b'<html' in 몸[:3000].lower() or 몸.lstrip()[:1] == b'<':
        raise R.못읽음('파일이 아니라 웹 화면이 받아짐')
    if len(몸) < 2000:   # 서버가 파일 대신 짧은 글을 준 것 — 그 글을 그대로 적는다(「Error: The file does not exist.」·「파일이 존재하지 않습니다」)
        raise R.못읽음('서버가 파일 대신 글을 줌: 「' + 몸.decode('utf-8', 'replace').strip()[:40] + '」')
    raise R.못읽음(f'모르는 꼴({몸[:8].hex()})')


# 원본 파일이 아니라 화면으로 띄우는 뷰어·음성 읽기 링크 — 못 받아도 「못 받은 파일」로 세지 않는다
뷰어 = re.compile(r'docviewer|convert\.(jsp|do)|sn3hcv|synap|viewer|preview|바로듣기|미리\s*보기|바로\s*보기', re.I)


def 바로받기(일):
    주소 = urllib.parse.quote(urllib.parse.urljoin(일['바탕'], 일['주소']).strip(), safe=":/?&=%#;,+@!$'()*~[]")
    if 주소.startswith('//'):
        주소 = 'https:' + 주소
    req = urllib.request.Request(주소, headers={'User-Agent': UA, 'Referer': 일['바탕']})
    import ssl
    try:
        r = urllib.request.urlopen(req, timeout=120)
    except urllib.error.URLError as e:
        if 'CERTIFICATE' not in str(e).upper():
            raise
        # 인증서 사슬이 빠진 공공 누리집이 많다 — 크롬 점검처럼 경고를 무시하고 받되, 그렇게 받았다고 적는다
        r = urllib.request.urlopen(req, timeout=120, context=ssl._create_unverified_context())
        일['인증서무시'] = True
    with r:
        if int(r.headers.get('Content-Length') or 0) > 한도:
            raise R.못읽음('30MB 넘음')
        몸 = r.read(한도 + 1)
    if len(몸) > 한도:
        raise R.못읽음('30MB 넘음')
    return 몸


def 읽어두기(일, 몸):
    """받은 몸을 캐시에 두고 글자를 뽑아 일에 적는다."""
    open(일['자리'], 'wb').write(몸)
    일['크기'] = len(몸)
    try:
        글, 일['꼴'] = 글뽑기(몸, os.path.splitext(일['이름'])[1][1:].lower())
    except R.못읽음 as e:
        일['까닭'] = str(e)
        return
    except Exception as e:
        일['까닭'] = '못 읽음 ' + str(e)[:50]
        return
    open(일['자리'] + '.txt', 'w', encoding='utf-8', errors='replace').write(글)
    일['쪽수'] = 글.count('\f') + 1
    일['글자수'] = len(글)
    일['까닭'] = '' if 글.strip() else '글자 없음'


def main():
    os.makedirs(캐시, exist_ok=True)
    dom = json.load(open(os.path.join(ROOT, 'data', 'disclosure_dom.json'), encoding='utf-8'))
    고른곳 = {a for a in sys.argv[1:] if not a.startswith('--')}
    읽기만 = '--읽기만' in sys.argv   # 받기·누르기 없이 캐시만 다시 읽는다(읽는 법을 고쳤을 때). 캐시에 없는 것은 앞 회차 까닭을 그대로
    앞까닭 = {}
    if 읽기만 and os.path.exists(OUT):
        앞까닭 = {x['자리']: x for x in json.load(open(OUT, encoding='utf-8'))['파일']}
    일들, 본 = [], set()
    for r in dom['곳']:
        cd = r['laf_cd']
        if 고른곳 and cd not in 고른곳:
            continue
        바탕 = r.get('들어간주소') or r.get('끝주소') or ''
        for f in r.get('파일', []):
            일 = {'곳': cd, '이름': f.get('이름', ''), '주소': f.get('주소', ''), '바탕': 바탕}
            if not B.요즘것(일['이름'], 기준해):
                continue   # 옛 해 — 항목 판정에 안 쓰므로 안 받는다(build_transparency 와 같은 잣대)
            k = 열쇠(cd, 바탕, 일)
            if k in 본:
                continue
            본.add(k)
            일['자리'] = os.path.join(캐시, k + '.bin')
            일들.append(일)
    print(f'받을 파일 {len(일들)}개', flush=True)

    # ① 바로 받기 — 이미 받은 것은 다시 안 받는다
    def 하나(일):
        if os.path.exists(일['자리']):
            읽어두기(일, open(일['자리'], 'rb').read())
            return
        if 읽기만:
            앞 = 앞까닭.get(os.path.basename(일['자리']), {})
            일['까닭'] = 앞.get('까닭') or '앞 회차에 없음(받기 안 함)'
            if 앞.get('누름'):
                일['누름'] = True
            return
        if 누를것(일['주소']):
            일['까닭'] = '누르기 필요'
            return
        try:
            읽어두기(일, 바로받기(일))
        except R.못읽음 as e:
            일['까닭'] = str(e)
        except Exception as e:
            일['까닭'] = '못 받음 ' + str(e)[:60]
    with cf.ThreadPoolExecutor(8) as ex:
        for i, _ in enumerate(ex.map(하나, 일들), 1):
            if i % 200 == 0:
                print(f'   {i}/{len(일들)}', flush=True)

    # ② 누르기 — 자바스크립트 단추이거나, 바로 받기가 웹 화면·오류를 준 것
    누름 = [일 for 일 in 일들 if 일['까닭'] == '누르기 필요' or 일['까닭'].startswith('못 받음') or 일['까닭'] == '파일이 아니라 웹 화면이 받아짐']
    if 누름 and not 읽기만:
        for 일 in 누름:
            if os.path.exists(일['자리']):
                os.remove(일['자리'])   # 웹 화면을 받은 자리 — 누른 것으로 갈아 쓴다
        # 크롬 넷을 따로 띄워 나눠 누른다(포트 CDP_PORT … +3) — 한 곳의 파일은 한 크롬에(같은 누리집을 동시에 두드리지 않게)
        묶 = [[] for _ in range(4)]
        for 일 in sorted(누름, key=lambda x: x['곳']):
            min(묶, key=lambda b: len(b) if not b or b[-1]['곳'] != 일['곳'] else -1).append(일)
        print(f'누르기 {len(누름)}개 — 크롬 넷으로', flush=True)
        바탕포트 = int(os.environ.get('CDP_PORT') or 9444)
        일꾼 = []
        for i, b in enumerate(x for x in 묶 if x):
            일감 = os.path.join(캐시, f'일감{i}.json')
            json.dump([{'바탕': 일['바탕'], '이름': 일['이름'], '주소': 일['주소'], '자리': 일['자리']} for 일 in b],
                      open(일감, 'w', encoding='utf-8'), ensure_ascii=False)
            일꾼.append(subprocess.Popen(['node', os.path.join(ROOT, 'scripts', 'click_budget_books.js'), 일감],
                                       env={**os.environ, 'CDP_PORT': str(바탕포트 + i)}))
        for p in 일꾼:
            p.wait()
        for 일 in 누름:
            if os.path.exists(일['자리']):
                앞 = 일['까닭']
                읽어두기(일, open(일['자리'], 'rb').read())
                일['누름'] = True
                if 일['까닭']:
                    일['까닭'] += f' (누름, 앞서 {앞})'
            else:
                일['까닭'] = '누르기도 안 됨 (' + 일['까닭'] + ')'

    for 일 in 일들:
        일['자리'] = os.path.basename(일['자리'])
        if 일['까닭'].startswith(('누르기도 안 됨', '누르기 필요')) and 뷰어.search(일['주소'] + ' ' + 일['이름']):
            일['까닭'] = '문서 뷰어·바로듣기 링크(원본 파일 아님) — ' + 일['까닭']
        elif 일['까닭'].startswith(('누르기도 안 됨', '누르기 필요')) and not 일['주소']:
            일['까닭'] = '화면 글자에만 있는 파일 이름(누를 링크 없음) — ' + 일['까닭']
    if 고른곳 and os.path.exists(OUT):   # 시험은 그 곳만 갈아 끼운다
        옛 = [x for x in json.load(open(OUT, encoding='utf-8'))['파일'] if x['곳'] not in 고른곳]
        일들 = 옛 + 일들
    json.dump({'만든날': __import__('datetime').date.today().isoformat(), '기준해': 기준해, '파일': 일들},
              open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    import collections
    print(collections.Counter(일.get('꼴') or (일['까닭'].split(' (')[0][:20]) for 일 in 일들).most_common())
    print('적음:', OUT)


if __name__ == '__main__':
    main()
