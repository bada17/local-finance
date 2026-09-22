# 세입 판을 굽는다 — **돈이 어디서 오나.**
#
#   python scripts/build_revenue.py
#
# 지금까지 화면은 **쓰는 쪽**(세출·계약·보조금)에 쏠려 있었다. 들어오는 쪽은 재정자립도
# 두 줄뿐이었다. `data/revenue/` 43종을 자치단체별로 갈라 `site/data/revenue/<코드>.json` 을 낸다.
#
# 다섯 칸으로 짠다 —
#   ① 얼마가 들어오나   세입결산·세입예산 총계와 회계별 쪼개짐 (IIBBH·ARBGT)
#   ② 어디서 오나       재원별 구성 — 제 돈인가 받은 돈인가 (FIACRV 레벨2)
#   ③ 걷힌 것과 밀린 것  지방세 징수실적과 체납 누계 (DFGDGG·ABDBC)
#   ④ 깎아 준 돈        비과세·감면 (CHABG)
#   ⑤ 상과 벌          교부세 감액·인센티브 (LLBSR·LLBSI)
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

        # ② 어디서 오나 — 최신 해의 재원별 구성
        해별 = collections.defaultdict(dict)
        for r in 재원.get(cd, []):
            해별[r['_해']][str(r.get('armk_nm'))] = 수(r.get('tott_sum_amt'))
        if 해별:
            최신 = max(해별)
            칸 = {k: v for k, v in 해별[최신].items() if v}
            총 = sum(칸.values()) or 1
            d['재원'] = {'해': 최신,
                       '칸': sorted(({'이름': k, '금액': v, '몫': round(v / 총 * 100, 1)}
                                    for k, v in 칸.items()),
                                   key=lambda x: -x['금액'])}
            # 제 돈(지방세+세외수입) 대 받은 돈
            제돈 = sum(v for k, v in 칸.items() if k in ('지방세수입', '세외수입'))
            d['재원']['제돈몫'] = round(제돈 / 총 * 100, 1)
            바구니['제돈몫'].append(d['재원']['제돈몫'])
            # 해마다의 제 돈 몫 — 흐름을 본다
            d['제돈흐름'] = []
            for 해 in sorted(해별):
                칸2 = {k: v for k, v in 해별[해].items() if v}
                총2 = sum(칸2.values())
                if 총2:
                    몫 = sum(v for k, v in 칸2.items() if k in ('지방세수입', '세외수입'))
                    d['제돈흐름'].append({'해': 해, '몫': round(몫 / 총2 * 100, 1)})

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
