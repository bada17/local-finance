# 국고보조사업 수의계약 — data.go.kr 파일 15163532 「기획예산처_보조사업별_수의계약현황」을 받는다.
#
#   python scripts/fetch_subsidy_contracts.py
#
# 보조사업자가 국고보조금으로 맺은 수의계약 전부(2017~, 7만여 줄). 한 해에 한 번 새 파일이 올라온다(다음 2027-09).
# ⭐ 「수행기관경로」(부처 > 광역 > 기초 > 보조사업자)에 **어느 자치단체를 거쳐 간 돈인지 정식 이름이 들어 있다** —
#    build_side.py 가 그걸로 243곳에 붙인다. 보조사업 → 계약 → 계약상대방이 한 줄이라 건 하나하나가 이어진다.
# ⚠️ README 에 「보탬e 와 바로 붙는다」고 적혀 있었는데 **틀렸다**(2026-10-14) — 이건 국고(e나라도움) 번호이고,
#    보탬e 는 지방보조금이다. 두 자료의 번호는 하나도 안 겹친다.
#
# 받는 길 — 화면의 내려받기 단추가 하는 그대로: selectFileDataDownload.do(POST)로 첨부 번호를 받고 fileDownload.do 로 받는다.
# 원본 CSV(120MB)는 저장소에 안 넣는다. 긴 글 칸(사업목적·주요사업내용·수혜대상조건·홈페이지)을 빼고 묶어 둔다.
#
# 결과: data/subsidy_contracts.json.gz — {받은날, 파일, 칸:[…], 줄:[[…], …]}

import csv
import gzip
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'subsidy_contracts.json.gz')
PK, DETAIL = '15163532', 'uddi:2aef8d52-41db-4d4a-99fc-97445a721f01'
칸 = ['계약연도', '보조사업명', '보조사업자', '계약건명', '계약유형', '계약금액(백만원)', '계약상대방', '중앙관서',
     '사업시작일', '사업종료일', '당해연도사업비(원)', '보조형태', '수행기관경로', '수행기관', '내역사업아이디', '보조사업아이디']


def 부르기(url, data=None):
    for n in range(3):
        try:
            req = urllib.request.Request(url, data=data, headers={'User-Agent': 'Mozilla/5.0'})
            return urllib.request.urlopen(req, timeout=300).read()
        except Exception:
            if n == 2:
                raise
            time.sleep(20 * (n + 1))


def main():
    정보 = json.loads(부르기('https://www.data.go.kr/tcs/dss/selectFileDataDownload.do', urllib.parse.urlencode({
        'publicDataDetailPk': DETAIL, 'publicDataPk': PK, 'atchFileId': '', 'fileDetailSn': '1', 'publicDataTyCode': 'PR0051'}).encode()))
    if not 정보.get('status'):
        raise SystemExit(f'첨부 번호를 못 받았다: {정보.get("error")}')
    파일 = 정보['dataSetFileDetailInfo'].get('dataNm')
    if os.path.exists(OUT) and json.load(gzip.open(OUT, 'rt', encoding='utf-8')).get('파일') == 파일:
        print(f'그대로 — {파일}')
        return
    몸 = 부르기('https://www.data.go.kr/cmm/cmm/fileDownload.do?' + urllib.parse.urlencode(
        {'atchFileId': 정보['atchFileId'], 'fileDetailSn': 정보['fileDetailSn'], 'dataNm': 'x'}))
    줄 = [[r[k] for k in 칸] for r in csv.DictReader(io.StringIO(몸.decode('utf-8-sig')))]
    if len(줄) < 1000:
        raise SystemExit(f'줄이 너무 적다({len(줄)}) — 받은 것이 파일이 아닐 수 있다')
    with gzip.open(OUT, 'wt', encoding='utf-8', compresslevel=9) as f:
        json.dump({'받은날': time.strftime('%Y-%m-%d'), '파일': 파일, '칸': 칸, '줄': 줄}, f, ensure_ascii=False, separators=(',', ':'))
    print(f'받음: {파일} · {len(줄):,}줄 → data/subsidy_contracts.json.gz ({os.path.getsize(OUT) / 1e6:.1f} MB)')


if __name__ == '__main__':
    main()
