# 보탬e 지방보조금을 자치단체별로 묶는다 — data/grants/<해>.json.gz → site/data/grants/<코드>.json
#
#   python scripts/build_grants.py
#
# ⑥ 「누가 받아 갔나」 판의 **보조금 칸**이 이걸 읽는다. 계약 칸(build_contracts_summary.py)과 짝이다.
# ⚠️ 보탬e 곳코드(6110000 등 행정표준코드)와 화면의 곳코드(1100000 등 지방재정365)가 **다르다.**
#    이름으로 잇는다 — 「중구」가 6곳이라 **시도를 붙여서** 맞춘다(시도 없이 세면 243곳이 222곳이 된다).
# 받는 쪽은 보탬e 기관 ID(pfmInstId)로 묶는다. 같은 ID의 공개 이름이 여럿이면 금액이 큰 이름을 쓴다.
# 원자료에서 받은 곳을 가린 건은 전체와 비공개 합계에만 넣고, 개인으로 보이는 이름은 공개 파일에서 가린다.
# ⭐ 해를 박지 않는다. data/grants/ 에 있는 해를 전부 굽는다.

import collections
import glob
import gzip
import json
import os
import re
import sys
import unicodedata

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'site', 'data', 'grants')
상위 = 30

시도줄임 = {'서울특별시': '서울', '부산광역시': '부산', '대구광역시': '대구', '인천광역시': '인천',
         '광주광역시': '광주', '대전광역시': '대전', '울산광역시': '울산', '세종특별자치시': '세종',
         '경기도': '경기', '강원특별자치도': '강원', '강원도': '강원', '충청북도': '충북', '충청남도': '충남',
         '전북특별자치도': '전북', '전라북도': '전북', '전라남도': '전남', '경상북도': '경북',
         '경상남도': '경남', '제주특별자치도': '제주'}
# 보탬e 이름이 화면 목록과 다른 곳 — 인천 서구는 2026년 서해구로 이름이 바뀌었다
딴이름 = {'인천서해구': '인천서구'}

# 원자료에는 개인·단체 구분이 없다 — 이름 꼴(성+한두 글자)로 가른다.
# 다만 사업명이 시설 운영·종사자 인건비면 받은 곳은 시설로 보고 이름을 둔다(2026-10-26 옛 화면 규칙, 11-09 사용자 「일단 해」).
#   ponytail: 낱말 어림 — 개인이 운영하는 시설 이름이 운영자 이름과 같으면 드러난다. 이름 앞에 「개인」이 붙으면 늘 가린다
시설사업 = re.compile(r'(복지|거주|요양|재활|양육|양로|보호)시설|운영|종사자|인건비|임금|병동|위탁|보호')
성씨 = '김이박최정강조윤장임한오서신권황안송류전홍고문양손배백허유남심노하곽성차주우구민나진지엄채원천방공현함변염여추도소석선설마길연위표명기반왕금옥육인맹제모탁국어은편용예경봉사부가복태목형피두감음빈동온호범좌팽승간상갈견당화창'
사람이름꼴 = re.compile(rf'(남궁|황보|제갈|선우|독고|사공|서문|[{성씨}])[가-힣]{{1,2}}')
이름구분 = re.compile(r'[()[\],./:·–—-]+')
확인한기관 = {'백양사', '동산원'}
숨김표시 = '이름을 가린 곳'


def 붙인글(문구):
    return ''.join(unicodedata.normalize('NFKC', 문구).split())


def 이름에서개인찾기(이름, 사업=''):
    이름 = 붙인글(이름)
    if 이름 in 확인한기관:
        return None
    개인 = 이름.startswith('개인')
    if 개인:
        이름 = 이름.removeprefix('개인').lstrip('()[:·-')
    elif 시설사업.search(붙인글(사업)):
        return None
    앞말 = 이름구분.split(이름, maxsplit=1)[0]
    if not 개인 and 이름[len(앞말):len(앞말) + 1] == ')':   # 「사복)」「재)」 — 법인 줄임말
        return None
    return 사람이름꼴.fullmatch(앞말) if 앞말 not in 확인한기관 else None


def 별칭식(별칭들):
    # 앞뒤가 한글이 아닐 때만 — 「노인회」를 가렸다고 「대한노인회 ○○지회」까지 가리지 않게(2026-11-09, 낱말 중간을 뒤지면 1,197억이 가려졌다)
    if not 별칭들:
        return None
    return re.compile(r'(?<![가-힣])(?:' + '|'.join(map(re.escape, sorted(별칭들, key=len, reverse=True))) + r')(?![가-힣])')


def 화면이름(광역, 곳):
    시도 = 시도줄임[광역]
    n = 시도 + ('본청' if 곳 == 광역 else 곳)
    return 딴이름.get(n, n)


def main():
    with open(os.path.join(ROOT, 'site', 'data', 'loc', 'index.json'), encoding='utf-8') as f:
        idx = json.load(f)
    코드찾기 = {x['이름']: x['cd'] for x in idx['곳']}

    곳별 = collections.defaultdict(dict)       # 코드 → 해 → 묶음
    가릴곳 = {}                               # 받은 곳의 식별자 → 공개용 이름
    가릴낱말 = set()
    못맞춤 = set()
    for 파일 in sorted(glob.glob(os.path.join(ROOT, 'data', 'grants', '*.json.gz'))):
        해 = os.path.basename(파일)[:4]
        with gzip.open(파일, 'rt', encoding='utf-8') as f:
            자료 = json.load(f)
        for r in 자료:
            n = 화면이름(r['_광역'], r['_곳'])
            cd = 코드찾기.get(n)
            if not cd:
                못맞춤.add(n)
                continue
            y = 곳별[cd].setdefault(해, {'금액': 0, '건수': 0, '비공개금액': 0, '비공개건수': 0,
                                      '공시끝날': '', '받은곳': {}})
            금액 = int(r.get('bizctSbatAmt') or 0)
            y['금액'] += 금액
            y['건수'] += 1
            y['공시끝날'] = max(y['공시끝날'], r.get('pbaYmd') or '')
            이름 = (r.get('pfmInstNm') or '').strip()
            if not 이름 or 이름 == '비공개기관':
                y['비공개금액'] += 금액
                y['비공개건수'] += 1
                continue
            기관ID = r.get('pfmInstId')
            열쇠 = ('ID', 기관ID) if 기관ID else ('이름', 이름)
            if 찾음 := 이름에서개인찾기(이름, r.get('pfmBizNm') or ''):
                가릴낱말.add(찾음[0])
                가린이름 = 찾음[1] + '**'
                전에 = 가릴곳.setdefault(열쇠, 가린이름)
                if 전에 != 가린이름:
                    가릴곳[열쇠] = 숨김표시
            b = y['받은곳'].setdefault(열쇠, {'이름꼴': collections.Counter(), '금액': 0, '건수': 0,
                                           '사업': collections.Counter()})
            b['이름꼴'][이름] += 금액
            b['금액'] += 금액
            b['건수'] += 1
            b['사업'][(r.get('pfmBizNm') or '').strip()] += 금액

    if 못맞춤:
        raise SystemExit(f'화면 목록과 못 맞춘 곳 {len(못맞춤)} — {sorted(못맞춤)}')

    # 개인으로 보이는 곳의 모든 별칭을 모아 다른 곳의 이름·사업명에 반복되어도 가린다.
    가릴별칭 = 가릴낱말 | {붙인글(이름) for 해들 in 곳별.values() for y in 해들.values()
                        for 열쇠, b in y['받은곳'].items() if 열쇠 in 가릴곳 for 이름 in b['이름꼴']}
    문구 = 별칭식(가릴별칭)

    def 별칭있음(글):
        return 문구 and 문구.search(unicodedata.normalize('NFKC', 글))

    os.makedirs(OUT, exist_ok=True)
    for cd, 해들 in 곳별.items():
        낼 = {'laf_cd': cd, '가림완료': True, '칸': ['받은 곳', '금액', '건수', '가장 큰 사업'], '해': {}}
        for 해, y in 해들.items():
            줄 = sorted(y['받은곳'].items(), key=lambda item: -item[1]['금액'])
            y['받은곳수'] = len(줄)
            y['받은곳'] = []
            for 열쇠, b in 줄[:상위]:
                이름 = b['이름꼴'].most_common(1)[0][0]
                사업 = b['사업'].most_common(1)[0][0]
                if 열쇠 in 가릴곳:
                    이름, 사업 = 가릴곳[열쇠], ''
                elif 별칭있음(이름):
                    이름, 사업 = 숨김표시, ''
                elif 별칭있음(사업):
                    사업 = ''
                y['받은곳'].append([이름, b['금액'], b['건수'], 사업])
            y['상위몫'] = sum(b['금액'] for _, b in 줄[:5])
            낼['해'][해] = y
        with open(os.path.join(OUT, f'{cd}.json'), 'w', encoding='utf-8') as f:
            json.dump(낼, f, ensure_ascii=False, separators=(',', ':'))
    print(f'적음: site/data/grants/ {len(곳별)}곳')


def 스스로검사():   # python scripts/build_grants.py --selftest (지어낸 이름)
    assert 이름에서개인찾기('홍길동', '마을 축제')
    assert 이름에서개인찾기('홍길동(홍길동농장)', '친환경 농자재')
    assert not 이름에서개인찾기('홍길원', '아동복지시설 종사자 인건비')
    assert 이름에서개인찾기('개인(홍길동)', '시설 운영')
    assert not 이름에서개인찾기('사복)행복재활원', '프로그램 지원')
    assert not 이름에서개인찾기('한국문화예술교육진흥원', '')
    식 = 별칭식({'노인회', '홍길동'})
    assert not 식.search('대한노인회 마포구지회')
    assert 식.search('농장(홍길동)') and 식.search('홍길동 가옥 보수')
    print('가림 규칙 검사 통과')


if __name__ == '__main__':
    스스로검사() if '--selftest' in sys.argv else main()
