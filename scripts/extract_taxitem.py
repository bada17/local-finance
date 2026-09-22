# 지방세통계연감(hwpx)에서 **자치단체별 세목** 표를 뽑는다.
#
#   python scripts/extract_taxitem.py "<연감 hwpx 경로>"
#   python scripts/extract_taxitem.py              바탕 화면에 있는 것을 쓴다
#
# 왜 — 지방재정365 API 는 세목을 **시·도 17곳까지만** 준다(146종 전수 확인).
#      기초 243곳의 세목(취득세·재산세·주민세…)은 **이 연감에만** 있다.
#
# ⚠️ **hwpx 는 zip + XML(OWPML)** 이다. 옛 `.hwp` 와 달리 표를 읽을 수 있다.
# ⚠️ 연감은 이름을 **「종 로 구」처럼 띄어 쓴다.** 빈칸을 지워야 맞는다.
# ⚠️ 시도 한 곳의 표가 **넷으로 쪼개져** 있다 —
#    [이름+시세 앞칸][시세 뒷칸][이름+구세][군세]. 이름 칸이 없는 표는 **옆으로 이어지는 조각**이다.
# ⚠️ 머리칸이 **세로로 병합**돼 있다(`합 계` 가 두 줄을 먹는다). 그래서 칸을 세지 말고
#    `cellAddr`(칸 좌표)·`cellSpan`(병합)을 읽어 자리를 잡는다.
# ⚠️ 단위는 **천원**이다.
#
# 결과 : data/taxitem/<시도>.json  ·  site/data/taxitem/<자치단체코드>.json 은 build 쪽에서 낸다.

import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
기본파일 = 'C:/Users/dbqke/OneDrive/바탕 화면/행정안전부_지방세통계연감_20241231.hwpx'

꼬리 = lambda e, t: e.tag.endswith('}' + t) or e.tag.endswith(t)
민 = lambda s: re.sub(r'\s+', '', s or '')
글 = lambda e: ' '.join(''.join(e.itertext()).split())


def 깔끔(s):
    """영문 병기를 떼고 빈칸을 지운다 — 「종 로 구 Jongno-gu」 → 「종로구」.
    ⚠️ 연감은 칸마다 한글 옆에 영문을 붙여 둔다. 머리칸에도 붙으므로 **머리칸에도 써야 한다.**"""
    s = re.sub(r'[A-Za-z][A-Za-z0-9\s\-,.()/&]*', '', s or '')
    return 민(s)


def 수(s):
    s = 민(s).replace(',', '')
    if s in ('', '-', '−'):
        return None
    try:
        return int(s)
    except ValueError:
        return None


def 격자(표):
    """표를 (줄, 칸) 격자로 편다. 병합된 칸은 좌표 그대로 놓는다."""
    줄들 = [e for e in 표.iter() if 꼬리(e, 'tr')]
    칸수 = int(표.attrib.get('colCnt') or 0)
    줄수 = int(표.attrib.get('rowCnt') or len(줄들))
    판 = [[None] * 칸수 for _ in range(줄수)]
    for r in 줄들:
        for c in [e for e in r.iter() if 꼬리(e, 'tc')]:
            주소 = next((e for e in c if 꼬리(e, 'cellAddr')), None)
            if 주소 is None:
                continue
            ci, ri = int(주소.attrib['colAddr']), int(주소.attrib['rowAddr'])
            if 0 <= ri < 줄수 and 0 <= ci < 칸수:
                판[ri][ci] = 글(c)
    return 판


def 자치단체표인가(판):
    """첫 칸에 「…구/시/군」이 두 줄 이상이면 자치단체 표로 본다.
    ⚠️ 두 줄로 잡는다 — **제주는 제주시·서귀포시 둘뿐**이다. 셋으로 잡으면 제주가 통째로 빠진다."""
    n = 0
    for 줄 in 판:
        v = 깔끔(줄[0] if 줄 else '')
        if 2 <= len(v) <= 7 and re.search(r'(구|시|군)$', v):
            n += 1
    return n >= 2


시도짧은 = {'서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종', '경기',
          '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주'}

# 남의 표에 딸려 온 줄을 가려낸다.
# ⚠️ **세종만 넣는다.** 「광주시」를 광주광역시로 보면 **경기도 광주시**가 걷힌다(실제로 -2.25% 났다).
#    같은 이름의 기초가 있는 한 이름만으로 시도를 단정할 수 없다.
남의본청 = {'세종시': '세종특별자치시'}


def 전국총괄표인가(판):
    """⚠️ 「1. 시·도, 시·군·구별」 총괄표는 **줄이 시도 이름**(서울·부산·대구…)이다.
    「대구」·「광주」가 「…구」로 끝나서 자치단체 표로 잘못 읽히고, 그 값이 엉뚱한 시도에 섞인다
    (대구 합계가 4.4조 대신 6,928억으로 들어갔다). 시도 이름 줄이 셋 넘으면 총괄표로 본다."""
    n = sum(1 for 줄 in 판 if 줄 and 깔끔(줄[0] or '') in 시도짧은)
    return n >= 3


def 옆으로잇기(왼, 오른):
    """이름 칸이 없는 **옆으로 이어지는 조각**을 붙인다. 줄 차례가 같다."""
    붙 = []
    for i in range(max(len(왼), len(오른))):
        a = 왼[i] if i < len(왼) else [None] * (len(왼[0]) if 왼 else 0)
        b = 오른[i] if i < len(오른) else [None] * (len(오른[0]) if 오른 else 0)
        붙.append(list(a) + list(b))
    return 붙


def 곳이름인가(v):
    """「합 계」·「서울시」·「종로구」처럼 줄의 이름 칸으로 보이나."""
    v = 깔끔(v)
    return bool(v) and (v in ('합계', '총계') or
                        (2 <= len(v) <= 8 and re.search(r'(시|군|구|도)$', v)))


def 머리읽기(판):
    """머리 두 줄(그룹·세목)을 합쳐 칸마다 이름을 짓는다.

    ⚠️ 머리를 낱말로 찾으면 안 된다 — 연감은 칸마다 영문을 붙여 둬서
       「소 계Sub-total」처럼 되고 어떤 낱말 규칙도 어긋난다(실제로 구세가 통째로 빠졌다).
       ⭐ **첫 데이터 줄(이름 칸이 자치단체인 줄) 바로 앞을 머리로 본다.**"""
    첫데이터 = None
    for i, 줄 in enumerate(판):
        if 줄 and 곳이름인가(줄[0] or ''):
            첫데이터 = i
            break
    세목줄 = (첫데이터 - 1) if 첫데이터 else 1
    세목줄 = max(0, min(세목줄, len(판) - 1))
    그룹줄 = max(0, 세목줄 - 1)

    이름 = []
    앞그룹 = ''
    for ci in range(len(판[0])):
        g = 깔끔(판[그룹줄][ci] if ci < len(판[그룹줄]) else '')
        s = 깔끔(판[세목줄][ci] if ci < len(판[세목줄]) else '')
        if g and g not in ('세목별', '단위：천원', '단위:천원'):
            앞그룹 = g
        이름.append((앞그룹, s or g))
    return 이름, 세목줄


def 블록나누기(판):
    """⚠️ 한 표 안에 **시세 블록과 구세 블록이 위아래로 쌓여** 있는 시도가 있다
    (광주·대구·대전·울산·인천). 그러면 「중구」가 두 번 나와 **뒤엣것이 앞엣것을 덮어쓴다**
    — 대구 중구가 3,039억 대신 667억(구세만)이 됐다.
    ⭐ 「합계」 줄이 다시 나오면 새 블록이 시작된 것으로 보고 잘라 낸다."""
    시작 = []
    for i, 줄 in enumerate(판):
        if 줄 and 깔끔(줄[0] or '') == '합계':
            시작.append(i)
    if len(시작) <= 1:
        return [판]
    토막 = []
    for n, s in enumerate(시작):
        머리 = 시작[n - 1] if n else 0          # 앞 블록 끝 ~ 이 블록 합계 줄 앞까지가 머리
        처음 = 머리 if n == 0 else 시작[n - 1] + 1
        끝 = 시작[n + 1] if n + 1 < len(시작) else len(판)
        # 머리 두 줄을 이 블록 앞에 붙여 준다
        앞 = max(0, s - 2)
        토막.append(판[앞:끝])
    return 토막


def 표뽑기(판):
    if len(블록나누기(판)) > 1:
        나온 = []
        for 조각 in 블록나누기(판):
            나온 += 한블록뽑기(조각)
        return 나온
    return 한블록뽑기(판)


def 한블록뽑기(판):
    이름칸, 머리끝 = 머리읽기(판)
    나온 = []
    for 줄 in 판[머리끝 + 1:]:
        곳 = 깔끔(줄[0] if 줄 else '')
        if not 곳:
            continue
        값 = {}
        for ci in range(1, len(줄)):
            그룹, 세목 = 이름칸[ci] if ci < len(이름칸) else ('', '')
            v = 수(줄[ci])
            if not 세목 or v is None:
                continue
            키 = f'{그룹}·{세목}' if 그룹 and 그룹 != 세목 else 세목
            # ⚠️ 같은 이름의 칸이 두 번 나오는 표가 있다(광주·대구·대전·울산·인천).
            #    덮어쓰면 합계가 조용히 작아진다 — 겹치면 번호를 붙여 둘 다 남긴다.
            if 키 in 값:
                n = 2
                while f'{키}({n})' in 값:
                    n += 1
                키 = f'{키}({n})'
            값[키] = v
        if 값:
            # ⚠️ 낱 세목만 골라 더하는 셈은 쓰지 않는다 — 「구세」·「군세」처럼 **묶음인데
            #    소계라고 이름 붙지 않은 칸**이 섞여 이중계산이 난다(실제로 +1만%가 났다).
            #    합계는 표가 준 「합계」 칸을 그대로 쓴다. 겹친 칸은 위에서 번호를 붙여 살려 뒀다.
            나온.append({'곳': 곳, '값': 값})
    return 나온


def main():
    경로 = sys.argv[1] if len(sys.argv) > 1 else 기본파일
    if not os.path.exists(경로):
        raise SystemExit(f'파일이 없다: {경로}')
    z = zipfile.ZipFile(경로)
    본문들 = sorted((n for n in z.namelist() if re.search(r'Contents/section\d+\.xml$', n)),
                 key=lambda s: int(re.search(r'section(\d+)', s).group(1)))

    시도별 = {}
    지금시도 = None
    본표 = 0
    이은조각 = 0
    for n in 본문들:
        뿌리 = ET.fromstring(z.read(n))
        표들 = [e for e in 뿌리.iter() if 꼬리(e, 'tbl')]
        판들 = [격자(t) for t in 표들]
        # ⚠️ 조각이 바뀌면 블록을 닫는다. 안 닫으면 **뒤쪽 조각의 표가 앞 시도에 섞여**
        #    합계를 덮어쓴다(대구가 4.4조 대신 6,928억이 됐다).
        지금시도 = None
        i = 0
        while i < len(판들):
            판 = 판들[i]
            if not 판 or not 판[0]:
                i += 1
                continue
            # 「1-2. 서울특별시」 꼴의 제목이 표 첫 줄에 붙어 있다
            첫줄 = ' '.join(민(x) for x in 판[0] if x)
            # ⚠️ 그 앞에 **전국 총괄표**(「1. 시·도, 시·군·구별」)가 있다. 줄이 서울·부산·대구 같은
            #    **시도 이름**이라 자치단체 표로 잘못 읽히고, 그 값이 앞 시도에 섞여 들어간다
            #    (실제로 대구 합계가 4.4조 대신 6,928억으로 들어갔다). 만나면 블록을 닫는다.
            if re.search(r'^\d+\.\s*시·?도', 첫줄) or re.match(r'^\d+\.시도', 첫줄):
                지금시도 = None
            # ⚠️ 연감에는 **다른 편에도 시도별 시군구 표**가 있다(재산세 과세현황 `9-1-1.`,
            #    자동차세 `10-1-1.`, 비과세감면 `15-2-1.` …). 그것까지 주워 담으면 한 시도 안에서
            #    총괄과 상세가 섞여 합계가 어긋난다(대구가 4.4조 대신 6,928억이 됐다).
            #    ⭐ 우리가 쓸 것은 **제2편 「1-x. <시도>」 부과징수실적**뿐이다.
            m = re.search(r'(?:^|\s)1-\d+\.\s*([가-힣]+(?:특별시|광역시|특별자치시|특별자치도|도))', 첫줄)
            if m:
                지금시도 = m.group(1)
            elif re.search(r'\d+-\d+\.\s*[가-힣]+(?:특별시|광역시|특별자치시|특별자치도|도)', 첫줄):
                지금시도 = None          # 다른 편의 시도 표 — 블록을 닫는다
            if 전국총괄표인가(판):          # 전국 총괄표는 블록을 닫는다
                지금시도 = None
                i += 1
                continue
            if not 자치단체표인가(판) or not 지금시도:
                i += 1
                continue

            # ⭐ 이름 칸이 없는 뒤 조각들을 **옆으로 붙인다.** 줄 수가 같은 동안 이어 붙인다.
            합판 = 판
            j = i + 1
            while j < len(판들) and 판들[j] and len(판들[j]) == len(판) \
                    and not 자치단체표인가(판들[j]):
                합판 = 옆으로잇기(합판, 판들[j])
                이은조각 += 1
                j += 1

            줄들 = 표뽑기(합판)
            if 줄들:
                본표 += 1
                묶 = 시도별.setdefault(지금시도, {})
                for r in 줄들:
                    # ⚠️ 다른 시도의 본청 줄이 같은 쪽에 붙어 오는 일이 있다
                    #    (세종은 기초가 없어 울산 표 끝에 「세종시」 한 줄로 딸려 왔다).
                    if r['곳'] in 남의본청 and 남의본청[r['곳']] != 지금시도:
                        continue
                    칸 = 묶.setdefault(r['곳'], {})
                    for k, v in r['값'].items():
                        # ⚠️ **덮어쓰지 않는다.** 블록이 쌓인 표에서 같은 이름이 다시 오면
                        #    뒤엣것이 앞엣것을 지워 합계가 조용히 작아진다. 겹치면 번호를 붙인다.
                        키 = k
                        n = 2
                        while 키 in 칸 and 칸[키] != v:
                            키 = f'{k}({n})'
                            n += 1
                        칸[키] = v
            i = j

    낼곳 = os.path.join(ROOT, 'data', 'taxitem')
    os.makedirs(낼곳, exist_ok=True)
    총곳 = 0
    for 시도, 묶 in 시도별.items():
        with open(os.path.join(낼곳, f'{시도}.json'), 'w', encoding='utf-8') as f:
            json.dump({'시도': 시도, '단위': '천원', '기준': '2024 결산',
                       '곳': [{'이름': k, '값': v} for k, v in 묶.items()]},
                      f, ensure_ascii=False, separators=(',', ':'))
        총곳 += len(묶)
    세목수 = {s for 묶 in 시도별.values() for v in 묶.values() for s in v}
    print(f'표 {본표}개(옆으로 이은 조각 {이은조각}개)에서 뽑았다 — 시·도 {len(시도별)}곳 · 줄 {총곳}개 · 세목 이름 {len(세목수)}가지')
    print(f'  저장 data/taxitem/ ({len(시도별)}개 파일)')
    for 시도, 묶 in list(시도별.items())[:6]:
        print(f'   {시도:<10} {len(묶)}곳')


if __name__ == '__main__':
    main()
