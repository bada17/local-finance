# 데이터 지도를 굽는다 — site/datamap.html
#
#   python scripts/build_datamap.py
#
# **질문을 뼈대로 삼는다.** 우리가 답하려는 질문을 늘어놓고, 지금 답할 수 있나를 매긴다.
#   ● 된다 · ◐ 반쪽 · ○ 못 한다.  빈칸마다 **어떤 자료가 있어야 풀리는지**를 적는다.
#
# ⭐ **상태를 손으로 적지 않는다.** 자료가 실제로 저장소에 있는지 훑어서 판정한다.
#    보탬e 를 받아 오면 다시 굽는 것만으로 ○ 가 ● 로 바뀐다.
# ⚠️ 사람이 적는 것은 셋뿐이다 — 질문 목록 · 자료가 어디 있나 · 반쪽인 까닭.
#
# 이 화면은 **우리 작업 관리용**이다(2026-09-21 사용자 결정). 파일 이름과 명령을 그대로 적는다.
#
# `catalog.html` 과 다르다 — 그쪽은 지방재정365가 **주는** 146종 목록이고,
# 여기는 **우리가 무엇을 말할 수 있나**의 지도다.

import glob
import gzip
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, 'site')


def 있나(*길들):
    for g in 길들:
        if glob.glob(os.path.join(ROOT, g)):
            return True
    return False


def 크기(*길들):
    총, 수 = 0, 0
    for g in 길들:
        for p in glob.glob(os.path.join(ROOT, g)):
            if os.path.isfile(p):
                총 += os.path.getsize(p)
                수 += 1
    return 총, 수


def 보기좋게(b):
    for 단위, 몫 in (('MB', 1 << 20), ('KB', 1 << 10)):
        if b >= 몫:
            return f'{b / 몫:,.0f}{단위}'
    return f'{b}B'


def js(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────
# 1. 가진 자료 — 저장소를 훑어서 채운다
# ─────────────────────────────────────────────────────────────────
def 자료훑기():
    표 = {}

    p = os.path.join(ROOT, 'data', 'indicators')
    이름들 = sorted(f for f in os.listdir(p) if f.endswith('.json') and '-' in f) if os.path.isdir(p) else []
    if 이름들:
        d = js(f'data/indicators/{이름들[-1]}')
        표['지표'] = {'이름': '재정지표 28종', '있다': True,
                    '출처': '지방재정365 OpenAPI (HCDIB 등)',
                    '언제': f"결산 {d['결산연도']} · 예산 {d['예산연도']}",
                    '얼마나': f"{len(d['지표목록'])}종 × {len(d['자치단체'])}곳",
                    '어디': [f'data/indicators/{이름들[-1]}', 'site/data/loc/*.json'],
                    '다시': 'python scripts/fetch_indicators.py && python scripts/build_model_data.py --all'}

    if 있나('data/series.json'):
        표['시계열'] = {'이름': '16년 시계열', '있다': True, '출처': '지방재정365',
                     '언제': '2009~2024', '얼마나': 보기좋게(크기('data/series.json')[0]),
                     '어디': ['data/series.json'],
                     '다시': 'python scripts/fetch_series.py'}

    길 = sorted(glob.glob(os.path.join(SITE, 'data', 'ongoing', '*.json.gz')))
    if 길:
        o = json.load(gzip.open(길[0], 'rt', encoding='utf-8'))
        기준 = str(o.get('기준') or '')
        총, 수 = 크기('site/data/ongoing/*.json.gz')
        표['진행'] = {'이름': '진행 중인 사업', '있다': True, '출처': '지방재정365 QWGJK',
                    '언제': f'{기준[:4]}년 {int(기준[4:6])}월 누계' if len(기준) >= 6 else 기준,
                    '얼마나': f'{수}곳 · {보기좋게(총)}',
                    '어디': ['site/data/ongoing/<코드>.json.gz'],
                    '다시': 'python scripts/build_ongoing.py --all'}

    if 있나('data/contracts_summary.json'):
        cs = js('data/contracts_summary.json')
        건 = sum(v['건수'] for c in cs['곳'].values() for v in c.values())
        총, 수 = 크기('data/contracts/*.json.gz')
        표['계약'] = {'이름': '계약 원본', '있다': True, '출처': '지방재정365 WCEGCF',
                    '언제': f"{cs['범위']['첫날']}~{cs['범위']['끝날']}",
                    '얼마나': f'{건:,}건 · {보기좋게(총)}({수}일)',
                    '어디': ['data/contracts/<날짜>.json.gz', 'data/contracts_summary.json',
                           'site/data/contracts/<코드>.json'],
                    '다시': 'python scripts/build_contracts_summary.py --해 <연도>'}

    if 있나('data/disclosure.json'):
        dis = js('data/disclosure.json')
        회차 = len(js('data/disclosure_history.json')['회차']) if 있나('data/disclosure_history.json') else 0
        크롬 = js('data/disclosure_dom.json').get('만든날', '') if 있나('data/disclosure_dom.json') else ''
        표['공시'] = {'이름': '재정공시 점검', '있다': True,
                    '출처': '지방재정365 FINLK + 243곳 홈페이지 실측',
                    '언제': f"{dis.get('만든날','')}" + (f' · 크롬 {크롬}' if 크롬 else ''),
                    '얼마나': f"{len(dis['곳'])}곳 · 점검 {회차}회차",
                    '어디': ['data/disclosure.json', 'data/disclosure_dom.json',
                           'data/disclosure_history.json'],
                    '다시': 'python scripts/check_disclosure.py && node scripts/recheck_disclosure.js'}

    if 있나('data/lofin365_146.json'):
        cat = js('data/lofin365_146.json')
        cov = js('data/coverage.json') if 있나('data/coverage.json') else {'서비스': {}, '만든날': ''}
        표['자료지도'] = {'이름': '지방재정365 자료 지도', '있다': True, '출처': '지방재정365 목록·명세',
                      '언제': cov.get('만든날', ''),
                      '얼마나': f"{len(cat)}종 · 눌러 본 것 {len(cov['서비스'])}종",
                      '어디': ['data/lofin365_146.json', 'data/coverage.json'],
                      '다시': 'python scripts/build_coverage.py'}

    if 있나('data/openfiscal_198.json'):
        표['열린재정'] = {'이름': '열린재정 198종(코드만)', '있다': True, '출처': '열린재정 OpenAPI',
                      '언제': '2026-09-18', '얼마나': '198종 · 호출 확인 87종',
                      '어디': ['data/openfiscal_198.json'], '다시': ''}

    # ── 아직 없는 자료 — 있으면 무엇이 풀리는지가 아래 질문 표에 붙는다
    없는것 = {
        '보탬e': {'이름': '보탬e 지방보조금', '있다': False,
                '어디있나': '보탬e 포털(lofin 보조금). 지방재정365에는 편성현황만 있다',
                '막힘': '아직 안 받았다 — 받는 길부터 확인해야 한다'},
        '나라장터': {'이름': '나라장터 계약정보', '있다': False,
                  '어디있나': 'data.go.kr 조달청 계약정보 API (사업자등록번호가 여기 있다)',
                  '막힘': f"⚠️ `.env` 의 `DATA_GO_KR_KEY` 가 비어 있다"
                          f"{' (키가 들어오면 바로 된다)' if 있나('scripts/probe_g2b.py') else ''}"},
        '클린아이': {'이름': '클린아이 지방공기업 경영정보', '있다': False,
                  '어디있나': '클린아이(cleaneye.go.kr). 기관별 알맹이가 여기 있다',
                  '막힘': '아직 안 봤다'},
        'CLIK': {'이름': '지방의정포털 회의록', '있다': False,
                 '어디있나': '지방의정포털 CLIK',
                 '막힘': '⛔ 사용자가 GPT 와 정하기로 했다 — 건드리지 않는다'},
        '투자심사': {'이름': '투자심사 결과', '있다': False,
                  '어디있나': '지방재정365에 없다. 자치단체 공시·행안부 쪽을 봐야 한다',
                  '막힘': '법 제37조의4 가 공개하라는 것인데 API 로는 안 나온다'},
        '주민참여예산': {'이름': '주민참여예산 운영현황', '있다': False,
                    '어디있나': '주민e참여에 전국 통합본이 없다. 자치단체마다 따로',
                    '막힘': '모으는 길이 없다 — 손으로 훑어야 한다'},
    }
    return 표, 없는것


# ─────────────────────────────────────────────────────────────────
# 2. 질문 — 사람이 적는다. 상태는 아래에서 자동으로 매긴다.
#    필요 : 이 질문에 답하려면 있어야 하는 자료 열쇠
#    흠   : 자료가 다 있어도 남는 구멍 (있으면 ◐ 반쪽)
# ─────────────────────────────────────────────────────────────────
질문들 = [
    ('살림의 크기', [
        ('얼마나 큰 살림인가 — 세출·세입 총액, 1인당', ['지표'], []),
        ('10년 동안 어떻게 변했나', ['시계열'],
         ['자료는 받아 뒀는데 **화면에 아직 안 올렸다**(5년치만 올리기로 했다).']),
        ('중앙정부·다른 나라와 견주면', ['열린재정'],
         ['열린재정은 **중앙정부 총량**이라 자치단체로 안 쪼개진다. 107종은 `ERROR-310`.']),
    ]),
    ('돈의 출처와 쓰임', [
        ('제 돈인가 받은 돈인가 — 자립도·자주도', ['지표'], []),
        ('무엇에 쓰나 — 분야별 비중과 금액', ['지표'], []),
        ('올해 무슨 사업이 돌아가고 있나', ['진행'],
         ['지출은 **그날까지 누계**이고 출납폐쇄 전이라 나중에 달라진다.',
          '2026년 구역 개편으로 **네 곳은 아예 없다**(빈칸이지 0이 아니다).']),
    ]),
    ('제대로 쓰나', [
        ('수의계약이 얼마나 되나', ['지표', '계약'],
         ['계약 자료의 **4.6%가 상대방이 조달청**이다 — 진짜 업체가 아니다.',
          '다년계약이 **총액 줄과 연차 줄로 두 번** 들어온다(2.4%).',
          '같은 계약원부번호가 여러 줄로 오는 것 1.1% — 변경계약인지 모른다.']),
        ('업무추진비·행사축제비를 얼마나 쓰나', ['지표'], []),
        ('끝난 행사의 실제 원가는', ['지표'],
         ['행사축제원가회계(`EVFTCT`)가 **2024년까지**다 — 올해 행사는 2028년쯤에야 잡힌다.']),
    ]),
    ('누가 받아 갔나', [
        ('어느 업체가 얼마를 받아 갔나', ['계약'],
         ['⚠️ **사업자등록번호가 없다.** 「(주)○○」와 「주식회사 ○○」를 완전히는 못 묶는다(12,096쌍이 갈린 채).',
          '조달청을 거친 4.6%는 **진짜 업체가 이 자료에 없다**.']),
        ('그 업체가 어떤 회사인가 — 대표·주소·다른 계약', ['나라장터'], []),
        ('어느 단체가 보조금을 받아 갔나', ['보탬e'], []),
        ('이 사업을 누가 받아 갔나 — 사업과 계약을 잇기', ['계약', '진행'],
         ['⛔ **잇는 열쇠가 없다.** 계약명 글자 맞추기는 여수시 109건 중 2%만 걸려 접었다.']),
    ]),
    ('공개를 제대로 하나', [
        ('법이 시킨 재정공시를 올렸나', ['공시'],
         ['**파일 이름으로** 센다 — 이름을 읽을 수 있는 곳이 151곳뿐이다.',
          '2026년에 생긴 **새 구역 넷은 아예 목록에 없다**(FINLK 가 안 준다).']),
        ('시민이 그 공시를 쓸 수 있나 — 엑셀인가 그림인가', ['공시'], []),
        ('지난번보다 나아졌나', ['공시'],
         ['회차가 **아직 한 번**이다. 다음 점검 때부터 견줄 수 있다.']),
        ('자치단체 홈페이지에서 몇 번 눌러야 닿나', ['공시'],
         ['⛔ **아직 안 쟀다.** 지금은 지방재정365가 준 **직통 주소**로만 재고 있어 실제보다 후하다.']),
        ('언제 올렸나 — 법정 기한(2개월)을 지켰나', ['공시'],
         ['페이지에 날짜가 적힌 곳이 **82곳**뿐이다. 나머지는 올린 날을 모른다.']),
        ('공기업·출자출연기관은 어떻게 운영되나', ['클린아이'], []),
        ('투자심사를 어떻게 했나', ['투자심사'], []),
        ('주민참여예산이 실제로 어떻게 돌아갔나', ['주민참여예산'], []),
    ]),
    ('감시의 뒷받침', [
        ('의회가 무엇을 지적했나', ['CLIK'], []),
        ('그 자료가 지방재정365에 있기는 한가', ['자료지도'], []),
    ]),
]


def 매기기(자료, 없는것):
    묶음 = []
    셈 = {'됨': 0, '반쪽': 0, '못함': 0}
    for 축, 목록 in 질문들:
        줄 = []
        for 물음, 필요, 흠 in 목록:
            빠진 = [k for k in 필요 if k not in 자료]
            상태 = '못함' if 빠진 else ('반쪽' if 흠 else '됨')
            셈[상태] += 1
            줄.append({
                '물음': 물음, '상태': 상태,
                '쓰는자료': [{'열쇠': k, '이름': 자료[k]['이름'], '언제': 자료[k]['언제']}
                         for k in 필요 if k in 자료],
                '빠진자료': [{'열쇠': k,
                          '이름': 없는것.get(k, {}).get('이름', k),
                          '어디있나': 없는것.get(k, {}).get('어디있나', ''),
                          '막힘': 없는것.get(k, {}).get('막힘', '')} for k in 빠진],
                '흠': 흠,
            })
        묶음.append({'축': 축, '질문': 줄})
    return 묶음, 셈


def main():
    자료, 없는것 = 자료훑기()
    묶음, 셈 = 매기기(자료, 없는것)

    # 없는 자료마다 — 그것이 있으면 풀리는 질문
    풀리는 = {k: [] for k in 없는것}
    for g in 묶음:
        for q in g['질문']:
            for m in q['빠진자료']:
                풀리는.setdefault(m['열쇠'], []).append(q['물음'])
    빈자료 = [{**v, '열쇠': k, '풀리는질문': 풀리는.get(k, [])} for k, v in 없는것.items()]

    tpl = open(os.path.join(SITE, 'datamap.template.html'), encoding='utf-8').read()
    out = (tpl
           .replace('__GROUPS__', json.dumps(묶음, ensure_ascii=False, separators=(',', ':')))
           .replace('__HAVE__', json.dumps(list(자료.values()), ensure_ascii=False, separators=(',', ':')))
           .replace('__MISSING__', json.dumps(빈자료, ensure_ascii=False, separators=(',', ':')))
           .replace('__TALLY__', json.dumps(셈, ensure_ascii=False))
           .replace('__ASOF__', __import__('datetime').date.today().isoformat()))
    p = os.path.join(SITE, 'datamap.html')
    with open(p, 'w', encoding='utf-8') as f:
        f.write(out)
    print(f'구움: site/datamap.html ({os.path.getsize(p)/1024:,.0f} KB)')
    print(f'   질문 {sum(셈.values())}개 — 된다 {셈["됨"]} · 반쪽 {셈["반쪽"]} · 못 한다 {셈["못함"]}')
    print(f'   가진 자료 {len(자료)}덩이 · 없는 자료 {len(빈자료)}가지')
    for x in 빈자료:
        if x['풀리는질문']:
            print(f'   ○ {x["이름"]:<22} → 질문 {len(x["풀리는질문"])}개가 풀린다')


if __name__ == '__main__':
    main()
