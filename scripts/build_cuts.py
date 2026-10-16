# 교부세 감액 화면(site/cuts.html, 작업대)이 쓰는 표를 굽는다 — site/data/cuts.json
#   python scripts/build_cuts.py
#
# 원자료: data/items/LLBSR.json.gz(지방재정365 「지방교부세 감액현황」, fetch_items.py 가 매달 다시 받는다)
# ⚠️ README 「기록」 10-13 표 — 확인한 것:
#   · mamt_amt1 = 그 해 그 곳 감액 합계(줄마다 되풀이), mamt_amt2 = 건별. 합칠 때 amt2 만 더한다.
#   · fyr = **깎인 해**다. 감사에서 걸린 해는 그 전이고, 고쳤는지는 자료에 없다.
#   · 사유는 띄어쓰기만 다른 이름이 섞여 있다(법령위반 과다지출 / 법령위반과다지출) — 빈칸을 지워 묶는다.
#     투자심사를 안 받은 것은 이름이 넷(재정투융자미심사·재정투자미심사·투융자미심사·투자미심사)이라 하나로.
#   · 사유 「N/A」 143건 — 빈 사유로 둔다(내역은 있다).
# 우리 동네(build_town.py)도 이 파일을 읽어 곳마다 한 줄을 만든다 — 이것을 먼저 굽는다.

import collections
import gzip
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
같은사유 = {'재정투융자미심사': '투자심사 안 받음', '재정투자미심사': '투자심사 안 받음', '투융자미심사': '투자심사 안 받음',
          '투자미심사': '투자심사 안 받음', '특별교부세반환': '특별교부세 반납', '특별교부세반납': '특별교부세 반납'}
# 같은 일인데 해마다 글이 다르게 적힌 것(한글만 남긴 꼴)
같은내역 = {'기초지자체학교법인설립지원예산출연부적정': '기초지방자치단체학교법인설립부적정'}   # 양구군 2013~2018
# 옛 자치단체 번호 → 지금 번호(우리 동네에서 붙일 곳). 화면에는 깎일 때 이름 그대로 낸다.
지금번호 = {'4311000': '4314000', '4371000': '4314000',   # 옛 청주시·청원군 → 청주시(2014 통합)
          '4771000': '2772000'}                         # 경북 군위군 → 대구 군위군(2023)


def 사유(s):
    s = re.sub(r'\s+', '', str(s or ''))
    if s in ('', 'N/A', 'NA'):
        return ''
    return ','.join(같은사유.get(x, x) for x in s.split(','))


def main():
    d = json.load(gzip.open(os.path.join(ROOT, 'data', 'items', 'LLBSR.json.gz'), 'rt', encoding='utf-8'))
    건, 이름 = [], {}
    for r in d['행']:
        이름[r['laf_cd']] = [r['laf_hg_nm'], r['wa_laf_hg_nm']]
        건.append([int(r['fyr']), r['laf_cd'], r.get('mamt_amt2') or 0, 사유(r.get('mamt_rson_cn')),
                  str(r.get('viol_ep_cn') or '').strip()])
    건.sort(key=lambda x: (-x[0], -x[2]))
    # 일 번호 — 같은 곳·같은 내역(한글만 견줌)은 여러 해에 나눠 깎아도 한 일이다.
    # 2019 이전엔 나눠 깎았다(인천 청사예정부지 부당매각 해마다 30억 5해 · 양구 학교법인 4해). 「몇 해」로 세면 되풀이로 부풀려진다.
    # 같은 해에 같은 내역이 여러 줄이면(특별교부세 교부조건 위반 등, 금액이 다르다) 다른 일일 수 있어 따로 둔다 —
    # 해가 다를 때만 묶고, 한 해 안에서는 금액 차례로 짝짓는다.
    일, 차례 = {}, collections.Counter()
    for x in sorted(건, key=lambda x: (x[0], -x[2])):
        글 = re.sub(r'[^가-힣]', '', x[4])
        글 = 같은내역.get(글, 글) or f'#{id(x)}'
        차례[(x[0], x[1], 글)] += 1
        x.append(일.setdefault((x[1], 글, 차례[(x[0], x[1], 글)]), len(일)))
    out = {'받은날': d['만든날'], '출처': '지방재정365 지방교부세 감액현황(LLBSR)',
           '칸': ['해', '코드', '금액', '사유', '내역', '일'], '건': 건, '이름': 이름, '지금번호': 지금번호}
    path = os.path.join(ROOT, 'site', 'data', 'cuts.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    print(f'적음: site/data/cuts.json ({os.path.getsize(path) // 1024}KB) · {len(건):,}건 · {len(이름)}곳 · '
          f'{min(x[0] for x in 건)}~{max(x[0] for x in 건)} · 합 {sum(x[2] for x in 건) / 1e8:,.0f}억 · 일 {len(일):,}가지')


if __name__ == '__main__':
    main()
