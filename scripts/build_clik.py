"""CLIK 목록을 곳별로 굽는다. 원본/전문/API를 수정하거나 호출하지 않는다."""
import collections
from datetime import date
import gzip
import json
from pathlib import Path
import re
from build_grants import 시도줄임

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {
    '회의록': ('DOCID','RASMBLY_ID','RASMBLY_NM','RASMBLY_NUMPR','RASMBLY_SESN','MINTS_ODR','MTG_DE','MTGNM'),
    '의안': ('DOCID','RASMBLY_ID','RASMBLY_NUMPR','ITNC_DE','BI_SJ','BI_NO','BI_KND_NM','CL_STD_NM','PROPSR'),
}


def valid_date(value):
    s = str(value or '')
    if not re.fullmatch(r'\d{8}', s) or s in ('18000101','19000101','19700101'):
        return ''
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:])).isoformat()
    except ValueError:
        return ''


def council_location(name, places):
    name = re.sub(r'\s+', '', name).removesuffix('의회')
    integrated = '전남광주통합특별시'
    if name.startswith(integrated):
        district = name[len(integrated):]
        candidates = [places[k] for k in ('전남'+district, '광주'+district) if k in places] if district else [places.get('전남광주본청')]
        return candidates[0] if len(candidates) == 1 else None
    for long, short in sorted(시도줄임.items(), key=lambda x:-len(x[0])):
        if name.startswith(long):
            district = name[len(long):] or '본청'
            key = short + district
            if key == '인천서해구':
                key = '인천서구'  # 같은 의회 코드 032008. 다른 새 구역은 합치지 않는다.
            if key == '경북군위군':
                key = '대구군위군'  # 목록에 남은 옛 소속명. 의회 이름은 원표기 보존.
            return places.get(key)
    return None


def result_group(value):
    s = re.sub(r'\s+', '', str(value or ''))
    if s in ('','-','분류불가'):
        return '확인 필요'
    if s in ('원안가결','처리-가결(원안)','원안','원안의결','원안가결(원안채택)'):
        return '원안가결'
    if s in ('수정가결','수정의결','처리-가결(수정)','가결(수정)','수정가결(수정채택)'):
        return '수정가결'
    if s in ('가결','가결의결'):
        return '가결(구분 없음)'
    if s in ('부결','폐기','철회','보류','계류','접수','미처리','채택'):
        return s
    return '기타'


def compile_rows(places, councils, source):
    mapping = {r['rasmblyId']:council_location(r['의회명'], places) for r in councils}
    councils = list(councils)
    for row in source.get('회의록', []):
        rid, name = row.get('RASMBLY_ID'), row.get('RASMBLY_NM')
        if rid and rid not in mapping and name:
            mapping[rid] = council_location(name, places)
            councils.append({'rasmblyId':rid,'의회명':name,'지금있나':None,'까닭':'코드표에 없어 회의록의 의회명으로 연결'})
    data = {cd:{'laf_cd':cd,'의회':[],'회의록':[],'의안':[]} for cd in places.values()}
    report = {'입력건수':{},'게시건수':{},'날짜미확인':{},'미연결건수':{},'미연결의회':[], '미연결목록':{}}
    for council in councils:
        cd = mapping[council['rasmblyId']]
        (data[cd]['의회'] if cd else report['미연결의회']).append(council)
    for kind, rows in source.items():
        report['입력건수'][kind] = len(rows)
        bad_dates = 0
        unmatched = []
        for row in rows:
            record = {f:row.get(f, '') for f in FIELDS[kind]}
            record['날짜'] = valid_date(row.get('MTG_DE' if kind == '회의록' else 'ITNC_DE'))
            bad_dates += not bool(record['날짜'])
            if kind == '의안':
                record['처리묶음'] = result_group(row.get('CL_STD_NM'))
            cd = mapping.get(row.get('RASMBLY_ID'))
            (data[cd][kind] if cd else unmatched).append(record)
        for value in data.values():
            value[kind].sort(key=lambda r:(r['날짜'],r['DOCID']), reverse=True)
        report['날짜미확인'][kind] = bad_dates
        report['미연결목록'][kind] = unmatched
        report['미연결건수'][kind] = len(unmatched)
        report['게시건수'][kind] = sum(len(d[kind]) for d in data.values())
    return data, report


def main():
    def read(path):
        return json.loads(path.read_text(encoding='utf-8'))
    idx = read(ROOT/'site/data/loc/index.json')
    places = {r['이름']:r['cd'] for r in idx['곳']}
    for path in sorted((ROOT/'site/data/ongoing').glob('*.json.gz')):
        cd = path.name.split('.')[0]
        if cd not in places.values():
            with gzip.open(path,'rt',encoding='utf-8') as f:
                r = json.load(f)
            places[r['자치단체']] = cd
    source = {}
    for kind in FIELDS:
        rows = []
        for path in sorted((ROOT/'data/clik').glob(kind+'_*.json.gz')):
            with gzip.open(path,'rt',encoding='utf-8') as f:
                rows.extend(json.load(f))
        source[kind] = rows
    state = read(ROOT/'data/clik/상태.json')
    data, report = compile_rows(places, read(ROOT/'data/clik/의회목록.json'), source)
    report['수집'] = {k:state['갈래'][k] for k in FIELDS}
    out = ROOT/'site/data/clik'
    out.mkdir(exist_ok=True)
    for cd, payload in data.items():
        payload['수집'] = report['수집']
        # 열 이름을 한 번만 쓴다. 원자료 필드는 보존하고 반복 키만 줄인다.
        payload['칸'] = {}
        for kind in FIELDS:
            fields = list(FIELDS[kind]) + ['날짜'] + (['처리묶음'] if kind == '의안' else [])
            payload['칸'][kind] = fields
            payload[kind] = [[r[f] for f in fields] for r in payload[kind]]
        (out/f'{cd}.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (ROOT/'site/data/clik.json').write_text(json.dumps(report,ensure_ascii=False,indent=1),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('미연결목록','수집')},ensure_ascii=False))
    print(f'구움: {len(data)}곳 / {sum(p.stat().st_size for p in out.glob("*.json"))/1024/1024:.1f}MB')


if __name__ == '__main__':
    main()
