# 보탬e 지방보조금 공시 수집기 — **누가 받아 갔나**가 여기 있다.
#
#   python scripts/fetch_grants.py 2025              그 해 전국(243곳)
#   python scripts/fetch_grants.py 2025 6110000      그 광역과 그 밑 기초만 (시험용)
#   python scripts/fetch_grants.py 2025 --다시       이미 받아 둔 것을 지우고 새로
#
# 왜 — 지방재정365에는 지방보조금 **편성현황**(UCMZQA 등)만 있다. 얼마를 잡았나까지다.
#      **누구에게 얼마가 갔나**는 보탬e 공시에만 있다.
#
# ⚠️ 인증키가 없다. 화면이 쓰는 창구를 그대로 부른다 —
#    `POST /sp/aidBizInfoPbaInq` (JSON 본문). 지역 코드는 `POST /sp/aidBizInfoPbaPry`.
# ⚠️ **`lafWa`(광역)를 비우면 화면이 막는다.** 곳마다 따로 불러야 한다.
# ⚠️ **보조사업자가 「비공개기관」으로 오는 줄이 있다.** 지우지 말고 그대로 담는다 —
#    「얼마나 가렸나」도 세어야 할 숫자다.
# ⚠️ 원자료가 크다. **gz 로 담고, 화면에는 센 것만 찍는다.**

import gzip
import json
import os
import ssl
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 'https://www.losims.go.kr'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')
머리 = {'Content-Type': 'application/json', 'User-Agent': UA,
       'Referer': BASE + '/sp/aidBizInfoPba'}

# ⚠️ 파이썬 기본값으로는 **TLS 악수에서 거절당한다**(SSLV3_ALERT_HANDSHAKE_FAILURE).
#    curl 은 되는데 파이썬만 안 되는 자리라 키·주소를 의심하기 쉽다. 암호모음 탓이다.
얼개 = ssl.create_default_context()
얼개.set_ciphers('DEFAULT@SECLEVEL=1')


def 부르기(길, 몸, 되풀이=3):
    자료 = json.dumps(몸).encode('utf-8')
    끝 = None
    for n in range(되풀이):
        try:
            req = urllib.request.Request(BASE + 길, data=자료, headers=머리)
            with urllib.request.urlopen(req, timeout=120, context=얼개) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            끝 = e
            time.sleep(2 * (n + 1))
    raise SystemExit(f'세 번 다 실패({길}): {끝!r}')


def 곳목록(해, 광역만=''):
    """[(코드, 이름, 광역이름)] — 광역 본청과 그 밑 기초를 모두 편다."""
    광역 = 부르기('/sp/aidBizInfoPbaPry', {'sLafCd': 'WA', 'fyr': 해})
    if 광역만:
        광역 = [w for w in 광역 if w['lafCd'] == 광역만]
        if not 광역:
            raise SystemExit(f'그런 광역이 없다: {광역만}')
    나온 = []
    for w in 광역:
        밑 = 부르기('/sp/aidBizInfoPbaPry', {'sLafCd': w['lafCd'], 'fyr': 해})
        for p in 밑:
            나온.append((w['lafCd'], p['lafCd'], p['lafNm'], w['lafNm']))
        time.sleep(0.1)
    return 나온


def 한곳(해, 광역코드, 곳코드):
    """그 곳의 공시를 다 받아 목록으로 돌려준다."""
    담 = []
    쪽 = 1
    전체 = None
    while True:
        d = 부르기('/sp/aidBizInfoPbaInq', {
            'curPage': 쪽, 'pageSize': '1000', 'bizYr': 해,
            'lafWa': 광역코드, 'lafPry': 곳코드,
            'pfmBizNm': '', 'pfmInstNm': '', 'pbaYmdSt': '', 'pbaYmdEn': ''})
        줄 = d.get('prtlAidBizInfoPbaIx') or []
        전체 = (d.get('input') or {}).get('totCnt', 전체)
        담.extend(줄)
        if not 줄 or 전체 is None or len(담) >= 전체:
            break
        쪽 += 1
        time.sleep(0.15)
    return 담, (전체 or 0)


def main():
    if len(sys.argv) < 2:
        raise SystemExit('쓰는 법: fetch_grants.py <연도> [광역코드] [--다시]')
    해 = sys.argv[1]
    다시 = '--다시' in sys.argv
    광역만 = next((a for a in sys.argv[2:] if a.isdigit()), '')

    낼곳 = os.path.join(ROOT, 'data', 'grants')
    os.makedirs(낼곳, exist_ok=True)
    이름 = f'{해}{"_" + 광역만 if 광역만 else ""}.json.gz'
    길 = os.path.join(낼곳, 이름)
    if os.path.exists(길) and not 다시:
        raise SystemExit(f'이미 있다: data/grants/{이름} (다시 받으려면 --다시)')

    곳들 = 곳목록(해, 광역만)
    print(f'■ {해}년 · 부를 곳 {len(곳들)}곳')

    담 = []
    빈곳 = []
    안맞 = []
    시작 = time.time()
    for i, (광역코드, 곳코드, 곳이름, 광역이름) in enumerate(곳들, 1):
        줄, 전체 = 한곳(해, 광역코드, 곳코드)
        for r in 줄:                       # 어느 곳에서 받은 것인지 박아 둔다
            r['_광역'] = 광역이름
            r['_곳'] = 곳이름
            r['_곳코드'] = 곳코드
        담.extend(줄)
        if 전체 == 0:
            빈곳.append(f'{광역이름} {곳이름}')
        elif len(줄) != 전체:
            안맞.append(f'{광역이름} {곳이름} {len(줄)}/{전체}')
        if i % 25 == 0 or i == len(곳들):
            print(f'  … {i}/{len(곳들)}곳 · {len(담):,}건 · {time.time() - 시작:.0f}초')
        time.sleep(0.1)

    with gzip.open(길, 'wt', encoding='utf-8') as f:
        json.dump(담, f, ensure_ascii=False)

    가린것 = sum(1 for r in 담 if (r.get('pfmInstNm') or '').strip() == '비공개기관')
    액 = sum(r.get('bizctSbatAmt') or 0 for r in 담)
    크기 = os.path.getsize(길) / 1024 / 1024
    print(f'\n  받음 {len(담):,}건 · {time.time() - 시작:.0f}초')
    print(f'  저장 data/grants/{이름} ({크기:,.1f} MB)')
    print(f'  교부액 합계 {액:,}원')
    print(f'  ⚠ 받는 쪽이 「비공개기관」인 줄 {가린것:,}건 '
          f'({가린것 / len(담) * 100:.1f}%)' if 담 else '')
    if 빈곳:
        print(f'  공시가 0건인 곳 {len(빈곳)}곳 — {", ".join(빈곳[:8])}'
              f'{" …" if len(빈곳) > 8 else ""}')
    if 안맞:
        print(f'  ⚠ 건수가 안 맞는 곳 {len(안맞)}곳 — {", ".join(안맞[:5])}')


if __name__ == '__main__':
    main()
