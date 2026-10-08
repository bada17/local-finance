# 「우리 동네 페이지」(drafts/town.html)에 그릴 지자체 모양을 굽는다 — drafts/shapes.json
#
#   pip install pyarrow pandas      (이 스크립트만 쓴다 — 경계가 바뀔 때 한 번)
#   python scripts/build_shapes.py
#
# 경계: vuski/admdongkor 의 시군구·시도 경계(단순화본, 2026-07-01) — CC BY 4.0, 화면에 출처를 적을 것.
#   data/boundary/sgg_20260701_light.parquet · sido_20260701_light.parquet (+ 인천 옛 구는 sgg_20260401_light.parquet)
#   좌표는 미터 단위 평면 좌표(EPSG:5179 계열)라 투영 없이 그대로 쓴다. y 만 뒤집는다.
# ⚠️ 코드로 잇지 않는다 — 경계 자료는 강원 51·전북 52 새 코드이고 광주+전남이 「전남광주통합특별시(12)」로 묶여 있는데,
#    우리 243곳(laf_cd)은 옛 코드다. 그래서 시도 + 이름으로 잇는다. 일반구가 있는 시(수원 등)는 구들을 모아 그린다.

import json
import os
import struct
import sys

import pandas as pd

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, 'data', 'boundary')
시도코드 = {'서울': ['11'], '부산': ['26'], '대구': ['27'], '인천': ['28'], '광주': ['12'], '대전': ['30'], '울산': ['31'],
         '세종': ['36'], '경기': ['41'], '강원': ['51'], '충북': ['43'], '충남': ['44'], '전북': ['52'], '전남': ['12'],
         '경북': ['47'], '경남': ['48'], '제주': ['50']}
광주구 = {'동구', '서구', '남구', '북구', '광산구'}   # 통합특별시(12) 안에서 광주 몫


def 고리들(wkb):
    """WKB Polygon/MultiPolygon → [[(x, y), ...], ...] (바깥·구멍 가리지 않고 고리만)."""
    out, p = [], 0

    def 하나(p):
        bo = '<' if wkb[p] == 1 else '>'
        t = struct.unpack_from(bo + 'I', wkb, p + 1)[0] % 1000
        p += 5
        if t == 3:
            n = struct.unpack_from(bo + 'I', wkb, p)[0]; p += 4
            for _ in range(n):
                m = struct.unpack_from(bo + 'I', wkb, p)[0]; p += 4
                out.append(list(struct.iter_unpack(bo + 'dd', wkb[p:p + 16 * m]))); p += 16 * m
        elif t == 6:
            n = struct.unpack_from(bo + 'I', wkb, p)[0]; p += 4
            for _ in range(n):
                p = 하나(p)
        else:
            raise ValueError(f'모르는 도형 {t}')
        return p
    하나(0)
    return out


def 경로(고리, 크기=600, 틀=None):
    """고리들을 틀(bbox) 안에서 긴 변이 크기가 되게 줄여 SVG path 로. 정수로 반올림해 점이 겹치면 버린다."""
    xs = [x for g in 고리 for x, _ in g]; ys = [y for g in 고리 for _, y in g]
    x0, y0, x1, y1 = 틀 or (min(xs), min(ys), max(xs), max(ys))
    k = 크기 / max(x1 - x0, y1 - y0)
    d = []
    for g in 고리:
        pts = []
        for x, y in g:
            q = (round((x - x0) * k), round((y1 - y) * k))
            if not pts or q != pts[-1]:
                pts.append(q)
        if len(set(pts)) < 3:
            continue
        d.append('M' + 'L'.join(f'{a} {b}' for a, b in pts) + 'Z')
    return ''.join(d), round((x1 - x0) * k), round((y1 - y0) * k)


def main():
    sgg = pd.read_parquet(os.path.join(B, 'sgg_20260701_light.parquet'))
    sido = pd.read_parquet(os.path.join(B, 'sido_20260701_light.parquet'))
    # 인천은 2026-07 구가 바뀌었다(제물포·영종·검단). 우리 자료는 옛 중구·동구·서구라 그 앞 경계(2026-04)를 덧붙여 찾는다
    옛 = pd.read_parquet(os.path.join(B, 'sgg_20260401_light.parquet'))
    sgg = pd.concat([sgg, 옛[~옛['sggcd'].isin(sgg['sggcd'])]], ignore_index=True)
    sgg['고리'] = sgg['geometry'].map(lambda g: 고리들(bytes(g)))
    sido['고리'] = sido['geometry'].map(lambda g: 고리들(bytes(g)))

    # 전국 — 작은 지도(어디쯤인지)용. 긴 변 300 이면 충분하다
    전국고리 = [g for r in sido['고리'] for g in r]
    xs = [x for g in 전국고리 for x, _ in g]; ys = [y for g in 전국고리 for _, y in g]
    전국틀 = (min(xs), min(ys), max(xs), max(ys))
    전국d, 전국w, 전국h = 경로(전국고리, 300, 전국틀)
    전국k = 300 / max(전국틀[2] - 전국틀[0], 전국틀[3] - 전국틀[1])

    곳 = json.load(open(os.path.join(ROOT, 'site', 'data', 'dash.json'), encoding='utf-8'))['곳']
    out, 못 = {}, []
    for cd, 이름, 시도, 갈래, _ in 곳:
        코드 = 시도코드[시도]
        후보 = sgg[sgg['sidocd'].isin(코드)]
        if 갈래 == '광역':
            if 시도 == '광주':
                고리 = [g for r in 후보[후보['sggnm'].isin(광주구)]['고리'] for g in r]
            elif 시도 == '전남':
                고리 = [g for r in 후보[~후보['sggnm'].isin(광주구)]['고리'] for g in r]
            else:
                고리 = [g for r in sido[sido['sidocd'].isin(코드)]['고리'] for g in r]
        else:
            nm = 이름[len(시도):]
            줄 = 후보[후보['sggnm'] == nm]
            if 줄.empty and nm.endswith('시'):
                줄 = 후보[후보['sggnm'].str.startswith(nm)]
            if 시도 == '전남':
                줄 = 줄[~줄['sggnm'].isin(광주구)]
            고리 = [g for r in 줄['고리'] for g in r]
        if not 고리:
            못.append(이름)
            continue
        d, w, h = 경로(고리)
        gx = [x for g in 고리 for x, _ in g]; gy = [y for g in 고리 for _, y in g]
        out[cd] = {'d': d, 'w': w, 'h': h,
                   '점': [round(((min(gx) + max(gx)) / 2 - 전국틀[0]) * 전국k), round((전국틀[3] - (min(gy) + max(gy)) / 2) * 전국k)]}

    path = os.path.join(ROOT, 'drafts', 'shapes.json')
    json.dump({'출처': 'vuski/admdongkor 시군구·시도 경계 2026-07-01 (CC BY 4.0)', '전국': {'d': 전국d, 'w': 전국w, 'h': 전국h}, '곳': out},
              open(path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f'적음: drafts/shapes.json ({os.path.getsize(path) // 1024}KB) · {len(out)}곳 · 못 이은 곳 {len(못)} {못}')
    assert not 못, '못 이은 곳이 있다 — 이름이 바뀌었는지 볼 것'


if __name__ == '__main__':
    main()
