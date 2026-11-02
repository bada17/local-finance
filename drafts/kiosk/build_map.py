"""Read repository boundaries and write only this draft's map.json.

Requires pyarrow for this optional rebuild. The browser has no dependencies.
Boundary source: vuski/admdongkor, CC BY 4.0, as recorded in scripts/build_shapes.py.
"""
import json
import struct
from pathlib import Path

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
BOUNDARY = HERE.parents[1] / 'data' / 'boundary'


def rings(wkb):
    output = []

    def read(pos):
        order = '<' if wkb[pos] == 1 else '>'
        kind = struct.unpack_from(order + 'I', wkb, pos + 1)[0] % 1000
        pos += 5
        count = struct.unpack_from(order + 'I', wkb, pos)[0]
        pos += 4
        if kind == 3:
            for _ in range(count):
                size = struct.unpack_from(order + 'I', wkb, pos)[0]
                pos += 4
                output.append(list(struct.iter_unpack(order + 'dd', wkb[pos:pos + size * 16])))
                pos += size * 16
        elif kind == 6:
            for _ in range(count):
                pos = read(pos)
        else:
            raise ValueError(f'Unsupported WKB: {kind}')
        return pos

    read(0)
    return output


provinces = pq.read_table(BOUNDARY / 'sido_20260701_light.parquet').to_pylist()
districts = pq.read_table(BOUNDARY / 'sgg_20260701_light.parquet').to_pylist()
old = pq.read_table(BOUNDARY / 'sgg_20260401_light.parquet').to_pylist()
present = {row['sggcd'] for row in districts}
districts += [row for row in old if row['sggcd'] not in present]
for row in provinces + districts:
    row['rings'] = rings(row['geometry'])

points = [p for row in provinces for ring in row['rings'] for p in ring]
x0, y0 = min(p[0] for p in points), min(p[1] for p in points)
x1, y1 = max(p[0] for p in points), max(p[1] for p in points)
scale = 720 / (y1 - y0)


def shape(parts):
    paths, all_points = [], []
    for ring in parts:
        pts = []
        for x, y in ring:
            p = (round((x - x0) * scale, 1), round((y1 - y) * scale, 1))
            if not pts or p != pts[-1]:
                pts.append(p)
        if len(set(pts)) >= 3:
            paths.append('M' + 'L'.join(f'{x},{y}' for x, y in pts) + 'Z')
            all_points += pts
    if not all_points:
        return None
    lo_x, lo_y = min(p[0] for p in all_points), min(p[1] for p in all_points)
    hi_x, hi_y = max(p[0] for p in all_points), max(p[1] for p in all_points)
    main_ring = max(parts, key=area)
    main = [((x - x0) * scale, (y1 - y) * scale) for x, y in main_ring]
    label = [round((min(p[0] for p in main) + max(p[0] for p in main)) / 2, 1),
             round((min(p[1] for p in main) + max(p[1] for p in main)) / 2, 1)]
    return {'d': ''.join(paths), 'box': [lo_x, lo_y, hi_x - lo_x, hi_y - lo_y], 'label': label}


def area(ring):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1])))


codes = {'서울': '11', '부산': '26', '대구': '27', '인천': '28', '대전': '30',
         '울산': '31', '세종': '36', '경기': '41', '강원': '51', '충북': '43',
         '충남': '44', '전북': '52', '경북': '47', '경남': '48', '제주': '50'}
regions = {}
for name, code in codes.items():
    regions[name] = shape([ring for row in provinces if row['sidocd'] == code for ring in row['rings']])
gwangju = {'동구', '서구', '남구', '북구', '광산구'}
for name in ['광주', '전남']:
    regions[name] = shape([ring for row in districts
                          if row['sidocd'] == '12' and ((row['sggnm'] in gwangju) == (name == '광주'))
                          for ring in row['rings']])

source = json.loads((HERE / 'data.json').read_text(encoding='utf-8'))
municipalities, unmatched, attempted = {}, [], set()
for contract in source['rows']:
    key = contract['코드']
    if key in attempted:
        continue
    attempted.add(key)
    region = contract['시도']
    if region == '전남광주':
        region = '광주' if key.startswith('29') else '전남'
    name = contract['지자체'].split(' ', 1)[-1]
    candidates = [row for row in districts if row['sidocd'] == codes.get(region, '12')]
    if region in ['광주', '전남']:
        candidates = [row for row in candidates if (row['sggnm'] in gwangju) == (region == '광주')]
    matches = [row for row in candidates if row['sggnm'] == name]
    if not matches and name.endswith('시'):
        matches = [row for row in candidates if row['sggnm'].startswith(name)]
    if not matches and (name == region or name in ['서울특별시', '세종특별자치시', '제주특별자치도', '도청']):
        municipalities[key] = regions[region]
        continue
    geom = shape([ring for row in matches for ring in row['rings']])
    if geom:
        municipalities[key] = geom
    else:
        unmatched.append({'code': key, 'name': contract['지자체']})

overview_parts = [max(row['rings'], key=area) for row in provinces]
overview_box = shape(overview_parts)['box']
result = {'source': 'vuski/admdongkor · 시도·시군구 경계 2026-07-01, 인천 구경계 2026-04-01 · CC BY 4.0',
          'width': round((x1 - x0) * scale, 1), 'height': 720,
          'overviewBox': overview_box,
          'regions': regions, 'municipalities': municipalities, 'unmatched': unmatched}
(HERE / 'map.json').write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print(json.dumps({'regions': len(regions), 'municipalities': len(municipalities), 'unmatched': unmatched}, ensure_ascii=True))
