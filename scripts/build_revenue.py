# 세입 판을 굽는다 — **돈이 어디서 오나.**
#
#   python scripts/build_revenue.py
#
# 지금까지 화면은 **쓰는 쪽**(세출·계약·보조금)에 쏠려 있었다. 들어오는 쪽은 재정자립도
# 두 줄뿐이었다. `data/revenue/` 43종을 자치단체별로 갈라 `site/data/revenue/<코드>.json` 을 낸다.
#
# 다섯 칸으로 짠다 —
#   ① 얼마가 들어오나   세입결산·세입예산 총계와 회계별 쪼개짐 (IIBBH·ARBGT)
#   ② 어디서 오나       재원별 구성 — **예산(FIRVBG)과 결산(FIACRV)을 나란히 본다**
#   ③ 무슨 세금인가     세목별 — 취득세·재산세·주민세… (KAAAE)
#   ④ 걷힌 것과 밀린 것  지방세 징수실적과 체납 누계 (DFGDGG·ABDBC)
#   ⑤ 깎아 준 돈        비과세·감면 (CHABG)
#   ⑥ 상과 벌          교부세 감액·인센티브 (LLBSR·LLBSI)
#
# ⚠️ **예산과 결산은 다른 자료다.** 예산은 들어올 것으로 **잡은 것**(추정),
#    결산은 실제로 **들어온 것**이다. 둘을 섞지 말고 나란히 둔다 —
#    잡은 것과 들어온 것의 차이 자체가 볼 거리다.
# ⚠️ **세목별(주민세·재산세 같은 것)은 시·도 17곳까지만 있다.**
#    기초 243곳 자료에서는 「지방세」가 **한 덩어리**다(FIACRV 레벨3까지 봐도 그렇다).
#    그래서 기초를 고르면 **그 시·도의 세목 구성**을 보여 주고 그렇다고 적는다.
#
# ⭐ **⑤가 이 판의 머리기사다.** `LLBSR` 에는 **감액사유**와 **위반지출내역**이 글로 들어 있다.
#    「법령위반과다지출」·「수입징수태만」·「재정투융자미심사」 같은 말이 그대로 나온다.
#    2012~2026 년 15년치 전국 합계가 **3,374억 원**이다.
#
# ⚠️ 자료마다 **있는 해가 다르다.** 없는 해를 0 으로 채우지 않는다 — 빈칸은 빈칸으로 둔다.
# ⚠️ 원자료를 그대로 싣지 않는다. 화면이 쓰는 것만 추려 담는다(한 곳에 20KB 안쪽).

import collections
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
RAW = os.path.join(ROOT, 'data', 'revenue')
OUT = os.path.join(ROOT, 'site', 'data', 'revenue')


def 읽기(코드):
    p = os.path.join(RAW, f'{코드}.json.gz')
    if not os.path.exists(p):
        return []
    with gzip.open(p, 'rt', encoding='utf-8') as f:
        return json.load(f)


def 수(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def 비(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def 곳별(줄들):
    """자치단체코드별로 묶는다."""
    d = collections.defaultdict(list)
    for r in 줄들:
        cd = str(r.get('laf_cd') or '').strip()
        if cd:
            d[cd].append(r)
    return d


def main():
    os.makedirs(OUT, exist_ok=True)

    세입결산 = 곳별(읽기('IIBBH'))
    세입예산 = 곳별(읽기('ARBGT'))
    재원 = 곳별([r for r in 읽기('FIACRV') if str(r.get('lvl_no')) == '2'])
    재원예산 = 곳별(읽기('FIRVBG'))          # 잡은 것 — 결산과 나란히 둔다

    # 세목별(취득세·재산세·주민세…) — 시·도 17곳까지만 있다. 시도 이름으로 묶는다.
    # ⚠️ 이름 꼴이 다르다 — 우리 자료는 「충북」인데 세목 자료는 「충청북도」다. 손으로 맞춘다.
    시도맞춤 = {
        '서울특별시': '서울', '부산광역시': '부산', '대구광역시': '대구', '인천광역시': '인천',
        '광주광역시': '광주', '대전광역시': '대전', '울산광역시': '울산', '세종특별자치시': '세종',
        '경기도': '경기', '강원도': '강원', '충청북도': '충북', '충청남도': '충남',
        '전라북도': '전북', '전라남도': '전남', '경상북도': '경북', '경상남도': '경남',
        '제주특별자치도': '제주',
    }
    세목줄 = collections.defaultdict(lambda: collections.defaultdict(dict))
    못맞춘 = set()
    for r in 읽기('KAAAE'):
        if str(r.get('cap_dv_nm')) != '시도':
            continue
        긴이름 = str(r.get('wa_laf_hg_nm') or '')
        짧은 = 시도맞춤.get(긴이름)
        if not 짧은:
            못맞춘.add(긴이름)
            continue
        금액 = 수(r.get('rcvmt_aggr_amt'))
        이름칸 = str(r.get('dtmk_nm') or '')
        if 이름칸 and 금액:
            세목줄[짧은][r['_해']][이름칸] = 금액
    if 못맞춘:
        print(f'  ⚠ 시도 이름을 못 맞춘 것 — {", ".join(sorted(못맞춘))}')
    징수 = 곳별(읽기('DFGDGG'))
    체납 = 곳별(읽기('ABDBC'))
    감면 = 곳별(읽기('CHABG'))
    감액 = 곳별(읽기('LLBSR'))
    인센 = 곳별(읽기('LLBSI'))
    개요 = 곳별(읽기('MLNXOJ'))

    이름 = {}
    시도 = {}
    for 묶 in (세입결산, 세입예산, 재원, 체납, 감액):
        for cd, 줄 in 묶.items():
            이름.setdefault(cd, str(줄[0].get('laf_hg_nm') or ''))
            시도.setdefault(cd, str(줄[0].get('wa_laf_hg_nm') or ''))

    곳들 = sorted(이름)
    낸것 = 0
    감액합 = 0
    감액곳 = 0
    바구니 = collections.defaultdict(list)     # 전국 견줄 값

    for cd in 곳들:
        d = {'laf_cd': cd, '이름': 이름.get(cd, ''), '시도': 시도.get(cd, '')}

        # ① 얼마가 들어오나
        d['세입결산'] = sorted(
            [{'해': r['_해'], '총계': 수(r.get('total')), '일반회계': 수(r.get('pfa_amt1')),
              '공기업특별': 수(r.get('pfa_amt2')), '기타특별': 수(r.get('pfa_amt3')),
              '기금': 수(r.get('pfa_amt4'))}
             for r in 세입결산.get(cd, [])], key=lambda x: x['해'])
        d['세입예산'] = sorted(
            [{'해': r['_해'], '총계': 수(r.get('pfa_amt1')), '일반회계': 수(r.get('pfa_amt2')),
              '공기업특별': 수(r.get('pfa_amt3')), '기타특별': 수(r.get('pfa_amt4')),
              '기금': 수(r.get('pfa_amt5'))}
             for r in 세입예산.get(cd, [])], key=lambda x: x['해'])

        # ② 어디서 오나 — 예산(잡은 것)과 결산(들어온 것)을 나란히
        def 구성(줄들, 금액칸):
            해별 = collections.defaultdict(dict)
            for r in 줄들:
                이름칸 = str(r.get('armk_nm') or '')
                if 이름칸:
                    해별[r['_해']][이름칸] = 수(r.get(금액칸))
            if not 해별:
                return None, []
            최신 = max(해별)
            칸 = {k: v for k, v in 해별[최신].items() if v}
            총 = sum(칸.values())
            if not 총:
                return None, []
            제돈 = sum(v for k, v in 칸.items() if k in ('지방세수입', '세외수입'))
            묶 = {'해': 최신, '제돈몫': round(제돈 / 총 * 100, 1), '합계': 총,
                 '칸': sorted(({'이름': k, '금액': v, '몫': round(v / 총 * 100, 1)}
                              for k, v in 칸.items()), key=lambda x: -x['금액'])}
            흐름 = []
            for 해 in sorted(해별):
                칸2 = {k: v for k, v in 해별[해].items() if v}
                총2 = sum(칸2.values())
                if 총2:
                    몫 = sum(v for k, v in 칸2.items() if k in ('지방세수입', '세외수입'))
                    흐름.append({'해': 해, '몫': round(몫 / 총2 * 100, 1)})
            return 묶, 흐름

        d['재원'], d['제돈흐름'] = 구성(재원.get(cd, []), 'tott_sum_amt')
        d['재원예산'], d['제돈흐름예산'] = 구성(재원예산.get(cd, []), 'last_bdg_tott_amt')
        if d['재원']:
            바구니['제돈몫'].append(d['재원']['제돈몫'])

        # ③ 무슨 세금인가 — 세목별. ⚠️ 시·도 17곳까지만 있다
        시도키 = 시도.get(cd) or ''
        해묶 = 세목줄.get(시도키)
        if 해묶:
            최신해 = max(해묶)
            칸 = {k: v for k, v in 해묶[최신해].items() if v}
            총 = sum(칸.values()) or 1
            d['세목'] = {'해': 최신해, '단위': f'{시도키} 전체(시·도)',
                       '이곳것아님': not cd.endswith('00000'),
                       '칸': sorted(({'이름': k, '금액': v, '몫': round(v / 총 * 100, 1)}
                                    for k, v in 칸.items()), key=lambda x: -x['금액'])[:12]}

        # ③ 걷힌 것과 밀린 것
        d['징수'] = sorted(
            [{'해': r['_해'], '올해': 수(r.get('pfin_stl_amt5')), '작년': 수(r.get('pfin_stl_amt4')),
              '증가율': 비(r.get('rate'))} for r in 징수.get(cd, [])], key=lambda x: x['해'])
        d['체납'] = sorted(
            [{'해': r['_해'], '누계': 수(r.get('pfa_amt1')), '지방세': 수(r.get('pfa_amt2')),
              '세외수입': 수(r.get('pfa_amt3'))} for r in 체납.get(cd, [])], key=lambda x: x['해'])
        # 체납이 그 해 지방세 징수액의 몇 %인가 — 밀린 정도를 한 수로
        징수해 = {x['해']: x['올해'] for x in d['징수'] if x['올해']}
        for x in d['체납']:
            걷 = 징수해.get(x['해'])
            x['징수대비'] = round(x['지방세'] / 걷 * 100, 1) if (걷 and x['지방세']) else None
        최신체납 = d['체납'][-1] if d['체납'] else None
        if 최신체납 and 최신체납.get('징수대비') is not None:
            바구니['체납대비'].append(최신체납['징수대비'])

        # ④ 깎아 준 돈
        d['감면'] = sorted(
            [{'해': r['_해'], '비과세': 수(r.get('pfa_amt1')), '감면': 수(r.get('pfa_amt2')),
              '징수': 수(r.get('pfa_amt3')), '감면율': 비(r.get('rate'))}
             for r in 감면.get(cd, [])], key=lambda x: x['해'])
        if d['감면'] and d['감면'][-1]['감면율'] is not None:
            바구니['감면율'].append(d['감면'][-1]['감면율'])

        # ⑤ 상과 벌 — 이 판의 머리기사
        벌 = []
        for r in 감액.get(cd, []):
            돈 = 수(r.get('mamt_amt2')) or 수(r.get('mamt_amt1'))
            사유 = str(r.get('mamt_rson_cn') or '').strip()
            내역 = str(r.get('viol_ep_cn') or '').strip()
            if 사유 in ('N/A', 'NA'):
                사유 = ''
            if not (돈 or 사유 or 내역):
                continue
            벌.append({'해': r['_해'], '금액': 돈, '사유': 사유, '내역': 내역[:200]})
        벌.sort(key=lambda x: (-x['해'], -(x['금액'] or 0)))
        d['감액'] = 벌
        d['감액합계'] = sum(x['금액'] or 0 for x in 벌)
        if 벌:
            감액곳 += 1
            감액합 += d['감액합계']
            바구니['감액합계'].append(d['감액합계'])

        상 = []
        for r in 인센.get(cd, []):
            돈 = 수(r.get('pfa_amt1'))
            if 돈:
                상.append({'해': r['_해'], '금액': 돈,
                          '체납축소': 수(r.get('pfa_amt5')), '재정공시': 수(r.get('pfa_amt7'))})
        상.sort(key=lambda x: -x['해'])
        d['인센티브'] = 상
        d['인센티브합계'] = sum(x['금액'] or 0 for x in 상)

        # 곁들임 — 재정자립도·자주도 흐름 (개요에서)
        d['자립'] = sorted(
            [{'해': r['_해'], '자립도': 비(r.get('smy_cntt_amt_rt')),
              '자주도': 비(r.get('smy_cntt_amt_rt2'))} for r in 개요.get(cd, [])],
            key=lambda x: x['해'])

        with open(os.path.join(OUT, f'{cd}.json'), 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, separators=(',', ':'))
        낸것 += 1

    def 가운데(xs):
        xs = sorted(v for v in xs if v is not None)
        return xs[len(xs) // 2] if xs else None

    색인 = {
        '곳': [{'cd': cd, '이름': 이름[cd], '시도': 시도.get(cd, '')} for cd in 곳들],
        '가운데': {k: 가운데(v) for k, v in 바구니.items()},
        '전국': {'감액합계': 감액합, '감액곳': 감액곳},
    }
    with open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump(색인, f, ensure_ascii=False, separators=(',', ':'))

    크기 = sum(os.path.getsize(p) for p in glob.glob(os.path.join(OUT, '*.json')))
    print(f'구움: site/data/revenue/ — {낸것}곳 · {크기 / 1024:,.0f} KB')
    print(f'  교부세를 깎인 곳 {감액곳}곳 · 합계 {감액합:,}원 (2012~2026)')
    print(f'  전국 가운데값 — 제 돈 몫 {색인["가운데"].get("제돈몫")}% · '
          f'체납/징수 {색인["가운데"].get("체납대비")}% · 감면율 {색인["가운데"].get("감면율")}%')


if __name__ == '__main__':
    main()
