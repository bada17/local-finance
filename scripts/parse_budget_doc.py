# ⏸ 나중에 할 일(2026-10-16 사용자 「한가해질 때」) — 예산서(사업예산서 PDF)에서 세부사업별 행사·축제경비 통계목 넷을 뽑는 시험판.
#   종로구 2026 사업예산서(864쪽)로 시험: 117개 세부사업, 합 3,078,727천원 = YCEHF 공식 3,078,127천원(0.02% 차이).
#   쓰는 법: pymupdf 로 글자를 뽑아(쪽마다 '=====쪽 N' 줄) 이 파일에 넘긴다 — python parse_budget_doc.py 글자.txt [줄 수]
#   남은 것: 광역·시·군 5~10곳 더 시험(e호조 양식이 같은지), 곳마다 사업예산서 파일 찾기(data/budget_docs.json), HWP·압축 파일.
#   ⚠️ 행사·축제경비에는 축제 아닌 것(체육대회·교육 프로그램·기념식·경로당 교실)이 섞인다 — 「축제」는 세부사업 이름으로 다시 골라야 한다.
import re, sys, collections
L = [x.strip() for x in open(sys.argv[1], encoding='utf-8')]
수 = re.compile(r'^△?[\d,]+$')
n = lambda s: (-1 if s.startswith('△') else 1) * int(s.lstrip('△').replace(',', ''))
행사 = {('201', '03'): '행사운영비', ('301', '11'): '행사실비지원금', ('307', '04'): '민간행사사업보조', ('401', '04'): '행사관련시설비'}
세부 = 편성 = None
결과 = collections.defaultdict(lambda: collections.Counter())
쪽 = 0
for i, s in enumerate(L):
    if s.startswith('=====쪽'):
        쪽 = int(s.split()[-1]); continue
    셋 = i + 3 < len(L) and all(수.match(L[i + k]) for k in (1, 2, 3))
    if not 셋:
        continue
    m = re.match(r'^(\d{3}) (\S.*)$', s)
    if m:
        편성 = m.group(1); continue
    m = re.match(r'^(\d{2}) (\S.*)$', s)
    if m:
        k = (편성, m.group(1))
        if k in 행사 and 세부:
            결과[(세부, 쪽)][행사[k]] += n(L[i + 1])
        continue
    if not s.startswith(('○', '―', '-', '=')) and not 수.match(s):
        세부 = s
합 = collections.Counter()
for (이름, 쪽), c in 결과.items():
    합.update(c)
print('세부사업', len(결과), '· 합(천원)', dict(합), '· 모두', sum(합.values()))
for (이름, 쪽), c in sorted(결과.items(), key=lambda kv: -sum(kv[1].values()))[:int(sys.argv[2]) if len(sys.argv) > 2 else 25]:
    print(f'  {쪽:4}쪽 {이름[:30]:30} {sum(c.values()):>10,} ', dict(c))
