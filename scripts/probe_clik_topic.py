"""내부용 CLIK 전문 분석 시험. 전문/결과는 --out(저장소 밖)에만 쓴다.

python scripts/probe_clik_topic.py --out ../clik-private --limit 40 --sample 24
실행 직전 git pull. 같은 키를 쓰는 봇/다른 클론과 동시 실행하지 않는다.
검색의 '정밀도'는 사람이 문맥을 검토해야 한다. 자동 검출률을 정밀도라고 부르지 않는다.
"""
import argparse
import collections
from datetime import datetime, timedelta, timezone
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request
import keys

ROOT=Path(__file__).resolve().parents[1]


class BudgetClient:
    def __init__(self,key,state,limit=40,reserve=20):
        self.key,self.state,self.limit,self.reserve=key,Path(state),limit,reserve
        self.used=0

    @staticmethod
    def today():
        return datetime.now(timezone(timedelta(hours=9))).date().isoformat()

    def call(self,params):
        if self.used>=self.limit:
            raise RuntimeError('이번 실행의 호출 상한에 도달했습니다.')
        # 같은 클론 안 중복 실행은 잠근다. 다른 클론/봇은 pull과 실행 시간 분리가 필요하다.
        lock=self.state.with_suffix('.json.lock')
        self.state.parent.mkdir(parents=True,exist_ok=True)
        try:
            fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError:
            raise RuntimeError('호출 장부가 사용 중입니다. 동시 실행 여부를 확인하세요.') from None
        os.close(fd)
        try:
            state=json.loads(self.state.read_text(encoding='utf-8')) if self.state.exists() else {}
            ledger=state.setdefault('날짜별호출',{})
            today=self.today()
            if ledger.get(today,0)>=1000-self.reserve:
                raise RuntimeError('일일 한도의 예비 몫을 남기고 멈췄습니다.')
            ledger[today]=ledger.get(today,0)+1
            tmp=self.state.with_suffix('.json.tmp')
            tmp.write_text(json.dumps(state,ensure_ascii=False,indent=1),encoding='utf-8')
            os.replace(tmp,self.state)
            self.used+=1
        finally:
            lock.unlink()
        # 보내기 전에 장부에 센다. 타임아웃/빈 응답도 한 번이며 숨은 재시도는 없다.
        url='https://clik.nanet.go.kr/openapi/minutes.do?'+urllib.parse.urlencode({'key':self.key,'type':'json',**params})
        request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(request,timeout=45) as response:
                raw=response.read()
            value=json.loads(raw.decode('utf-8'))
            value=value[0] if isinstance(value,list) and value else value
            if not isinstance(value,dict) or value.get('RESULT_CODE')!='SUCCESS':
                code=value.get('RESULT_CODE','EMPTY') if isinstance(value,dict) else 'EMPTY'
                raise RuntimeError('CLIK 응답: '+str(code))
            return value
        except Exception as exc:
            # urllib 예외 문자열에는 키가 든 URL이 포함될 수 있어 그대로 출력하지 않는다.
            if isinstance(exc,RuntimeError):
                raise
            raise RuntimeError('요청/해석 실패: '+type(exc).__name__) from None


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[];self.skip=0

    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip+=1
        if not self.skip and tag in ('p','div','br','tr','li','h1','h2','h3'):self.parts.append('\n')

    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
        if not self.skip and tag in ('p','div','tr','li'):self.parts.append('\n')

    def handle_data(self,data):
        if not self.skip:self.parts.append(data)


def extract_mentions(markup,query):
    parser=PlainText();parser.feed(markup or '')
    lines=[re.sub(r'\s+',' ',line).strip() for line in ''.join(parser.parts).splitlines()]
    lines=[line for line in lines if line]
    needle=re.sub(r'\s+','',query)
    speaker='미확인';mentions=[]
    for i,line in enumerate(lines):
        # ○역할 이름 형식만 발언자로 인정한다. 본문에 등장한 이름을 추정하지 않는다.
        match=re.match(r'^[○◯●◎]\s*([^\s]+(?:\s+[^\s]+)?)',line)
        if match:
            candidate=match.group(1)
            if re.search(r'(의원|위원장|시장|군수|구청장|과장|국장|실장|부장|팀장|본부장|이사장|위원|의장|단장)',candidate):
                speaker=candidate
            else:
                speaker='미확인'
        if needle and needle in re.sub(r'\s+','',line):
            pos=re.search(r'\s*'.join(map(re.escape,needle)),line)
            start=max(0,(pos.start() if pos else 0)-260)
            excerpt=line[start:start+950]
            mentions.append({'줄':i+1,'발언자표기':speaker,'발췌':excerpt,
                             '문맥':'\n'.join(lines[max(0,i-1):i]+[excerpt]+lines[i+1:i+2])[:1800],
                             '검토':'미검토'})
    return mentions


def check_output(out,root=ROOT):
    out=Path(out).resolve();root=Path(root).resolve()
    if out==root or root in out.parents:
        raise ValueError('전문과 내부 결과는 저장소 밖에 두어야 합니다.')
    return out


def sample_rows(rows,count):
    # 편의 표본 안에서 의회×연도를 돌아가며 고른다. 모집단의 무작위 표본은 아니다.
    strata=collections.defaultdict(list)
    for row in sorted(rows,key=lambda r:hashlib.sha256(r['DOCID'].encode()).hexdigest()):
        strata[(row.get('RASMBLY_ID'),str(row.get('MTG_DE',''))[:4])].append(row)
    chosen=[]
    while len(chosen)<count and any(strata.values()):
        for group in sorted(strata):
            if strata[group]:chosen.append(strata[group].pop())
            if len(chosen)>=count:break
    return chosen


def find_html(value):
    if isinstance(value,dict):
        if isinstance(value.get('MINTS_HTML'),str):return value['MINTS_HTML']
        for v in value.values():
            result=find_html(v)
            if result:return result
    if isinstance(value,list):
        for v in value:
            result=find_html(v)
            if result:return result
    return ''


def write_report(out,report):
    (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    esc=html.escape
    cards=[]
    for doc in report['표본']:
        r=doc['목록'];url='https://clik.nanet.go.kr/potal/search/searchView.do?'+urllib.parse.urlencode({'DOCID':r['DOCID'],'collection':'minutes'})
        mentions=''.join(f'<article><b>{esc(m["발언자표기"])} · 본문 {m["줄"]}줄</b><pre>{esc(m["문맥"])}</pre><small>문맥 검토 전 자동 발췌</small></article>' for m in doc['발췌'])
        cards.append(f'<section><h2>{esc(str(r.get("MTG_DE","")))} · {esc(r.get("RASMBLY_NM",""))}</h2><p>{esc(r.get("MTGNM",""))} · 제{esc(str(r.get("RASMBLY_SESN","")))}회 / {esc(str(r.get("MINTS_ODR","")))}차 · <a href="{esc(url)}">CLIK 원문</a></p><p>{esc(doc["상태"])}</p>{mentions}</section>')
    content='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>섬박람회 의회 기록 · 내부 검토</title><style>body{font:16px/1.8 system-ui,sans-serif;max-width:980px;margin:40px auto;padding:0 24px;background:#f6f5ef;color:#203329}h1{font-size:34px}h2{font-size:21px}section{margin:32px 0;padding-top:20px;border-top:2px solid #203329}article{padding:18px;background:#fffef9;margin:14px 0}pre{font:inherit;white-space:pre-wrap;overflow-wrap:anywhere}small{color:#596a5e}a{color:#226447}.note{padding:18px;background:#e9eee4}</style>'''
    content+=f'<p>함께하는 시민행동 · 내부 검토용 / 공개 화면 아님</p><h1>{esc(report["검색어"])}<br>의회에서 어떻게 논의됐나</h1><div class="note">검색 결과 전체가 관련 회의라는 뜻은 아닙니다. 아래는 의회·연도를 나눈 편의 표본이며, 발언자는 원문의 발언 표지를 읽은 값입니다. 정확한 발언자와 의미는 원문 대조가 필요합니다.</div><pre>{esc(json.dumps(report["측정"],ensure_ascii=False,indent=2))}</pre>'+''.join(cards)
    (out/'review.html').write_text(content,encoding='utf-8')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',required=True);ap.add_argument('--query',default='여수세계섬박람회')
    ap.add_argument('--limit',type=int,default=40);ap.add_argument('--reserve',type=int,default=20)
    ap.add_argument('--sample',type=int,default=24);ap.add_argument('--pages',type=int,default=6)
    ap.add_argument('--env-dir',help='CLIK_KEY가 든 .env의 디렉터리. 값은 출력하지 않음')
    args=ap.parse_args()
    if not (1<=args.limit<=1000 and 0<=args.reserve<1000 and args.sample>0 and 1<=args.pages<=10):ap.error('호출/표본/쪽 수 범위를 확인하세요.')
    out=check_output(args.out)
    if args.env_dir:keys.ROOT=args.env_dir
    key=keys.키읽기('CLIK_KEY')
    out.mkdir(parents=True,exist_ok=True)
    cache=out/'details';cache.mkdir(exist_ok=True)
    client=BudgetClient(key,ROOT/'data/clik/상태.json',args.limit,args.reserve)
    begin=time.monotonic();errors=[]
    params={'displayType':'list','searchType':'ALL','searchKeyword':args.query,'listCount':100,'sort':'MTG_DE/DESC'}
    first=client.call({**params,'startCount':0})
    total=int(first.get('TOTAL_COUNT') or 0)
    pages=max(1,(total+99)//100)
    offsets=sorted({round(i*(pages-1)/max(1,args.pages-1))*100 for i in range(args.pages)})
    rows={}
    for offset in offsets:
        try:
            response=first if offset==0 else client.call({**params,'startCount':offset})
            for item in response.get('LIST') or []:
                row=item.get('ROW',item)
                if re.fullmatch(r'CLIKC\d+',str(row.get('DOCID',''))):rows[row['DOCID']]=row
        except RuntimeError as exc:
            errors.append(str(exc));break
    (out/'search-sample.json').write_text(json.dumps({'검색어':args.query,'전체':total,'쪽시작':offsets,'목록':list(rows.values())},ensure_ascii=False),encoding='utf-8')
    report={'검색어':args.query,'날짜':client.today(),'표본':[],'측정':{}}
    for row in sample_rows(list(rows.values()),args.sample):
        target=cache/(row['DOCID']+'.json')
        try:
            if target.exists():detail=json.loads(target.read_text(encoding='utf-8'))
            else:
                detail=client.call({'displayType':'detail','docid':row['DOCID']})
                target.write_text(json.dumps(detail,ensure_ascii=False),encoding='utf-8')
            markup=find_html(detail)
            mentions=extract_mentions(markup,args.query)
            status='정확한 구절 검출 · 문맥 검토 필요' if mentions else ('본문에서 정확한 구절 미검출' if markup else '전문 빈 응답')
        except RuntimeError as exc:
            status=str(exc);mentions=[];markup='';errors.append(status)
        report['표본'].append({'목록':row,'상태':status,'전문문자수':len(markup),'발췌':mentions})
        print(f'{len(report["표본"])}/{args.sample} · {row["DOCID"]} · {status}',flush=True)
        if client.used>=args.limit or '한도' in status or 'ERROR09' in status:break
    docs=report['표본'];readable=sum(bool(d['전문문자수']) for d in docs);hits=sum(bool(d['발췌']) for d in docs)
    report['측정']={'API검색전체':total,'검색목록표본':len(rows),'전문시도':len(docs),'전문확보':readable,
                    '정확한구절검출문서':hits,'전문확보중구절검출률':round(hits/readable,3) if readable else None,
                    '추가호출':client.used,'소요초':round(time.monotonic()-begin,1),'오류':errors,
                    '범위':'API 전 기간 검색. 양 끝과 중간 쪽에서 의회×연도 편의 표본.',
                    '정밀도':'미산정 — 자동 구절 검출과 실제 관련성은 다름. 사람이 문맥을 분류해야 함.',
                    '재현율':'미산정 — 검색 결과 밖 누락, 표기 변형, 미수집 회의록의 모집단을 알 수 없음.'}
    write_report(out,report)
    print(json.dumps(report['측정'],ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except (RuntimeError,ValueError) as exc:raise SystemExit(str(exc)) from None
