# 투명성 지표 「의회에 낸 예산안」 — CLIK 의안 목록의 본예산안(2026·2027년도)만 상세를 불러
#   붙은 파일 이름(BI_FILE_NM)·제출일·처리일을 data/score_clik.json 에 둔다(2026-11-13).
#
#   CLIK_KEY=… python scripts/fetch_score_clik.py      이어받는다(받은 DOCID 는 건너뜀)
#
# 왜 — 의회 누리집을 봇으로 8곳 시험해 보니 예산안 글은 1곳뿐이었다(의안 목록을 JS 로 그리는 곳이 많다).
#      CLIK 의안 상세는 의회마다 같은 꼴로 파일 이름을 준다. 건당 1회, 약 240회.
# ⚠️ 호출 장부(data/clik/상태.json 날짜별호출)에는 안 적는다 — 그 파일은 main 봇이 커밋한다.
#    오늘 봇이 한도를 넘으면 ERROR09 로 멈출 뿐이다.
import gzip, json, glob, os, re, sys, datetime
sys.path.insert(0, os.path.dirname(__file__))
import fetch_clik_detail as F
import build_clik as B

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'score_clik.json')

def 본예산(sj):
    return re.search(r'202[67]년도', sj) and '예산안' in sj and not re.search(r'추가경정|추경|교육비|수정예산', sj)

def main():
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'clik', '의안_*.json.gz'))):
        rows += json.load(gzip.open(f, 'rt', encoding='utf-8'))
    places = B.load_places()
    councils = json.load(open(os.path.join(ROOT, 'data', 'clik', '의회목록.json'), encoding='utf-8'))
    곳 = {r['rasmblyId']: B.council_location(r['의회명'], places) for r in councils}
    나온 = json.load(open(OUT, encoding='utf-8'))['의안'] if os.path.exists(OUT) else {}
    할 = [r for r in rows if 본예산(r['BI_SJ']) and r['DOCID'] not in 나온]
    print('본예산안', len(할), '건 부를 차례')
    키 = F.키읽기()
    for i, r in enumerate(할):
        d, 오류 = F.부르기('bill.do', {'key': 키, 'type': 'json', 'docid': r['DOCID'], 'displayType': 'detail'})
        if 오류 in ('ERROR09', '무응답'):
            print('멈춤', 오류); break
        d = d or {}
        나온[r['DOCID']] = {'cd': 곳.get(r['RASMBLY_ID']), '의안': r['BI_SJ'], '제출': r['ITNC_DE'],
                          '본회의처리': d.get('PLNMT_PROCESS_DE', ''), '파일': [x for x in (d.get('BI_FILE_NM') or '').split('\n') if x.strip()],
                          '받음': bool(d)}
        if i % 40 == 39:
            print(f'  {i + 1}/{len(할)}')
    json.dump({'만든날': datetime.date.today().isoformat(), '의안': 나온}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('끝', len(나온), '건 ·', sum(1 for v in 나온.values() if v['파일']), '건에 파일')

if __name__ == '__main__':
    main()
