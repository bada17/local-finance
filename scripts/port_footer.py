# 홈페이지(action.or.kr) 공통 하단을 이 사이트 화면들에 옮겨 넣는다 — 2026-10-15 사용자: 「하단을 홈페이지 하단과 똑같이. 통일감이 있어야」
#
#   python scripts/port_footer.py
#
# 읽는 것 : 개편 저장소의 하단 원본 tools/parts/footer.html (공개 저장소라 깃허브에서 바로 받는다)
#           AH_FOOTER 환경변수에 파일 경로를 주면 그 파일을 읽는다(손으로 고친 것을 미리 볼 때)
# 쓰는 것 : site/*.html 의 표시 사이(AH:FOOTER START ~ END). 표시가 없으면 </main> 바로 뒤에 처음 한 번 만든다.
#           템플릿(*.template.html)과 구운 화면 둘 다 — 구운 화면은 다음 굽기에서도 템플릿 것이 그대로 나온다.
#           dashboard.html 은 넘겨주기만 하는 파일이라 뺀다. 데이터 지도도 2026-10-15 부터 붙인다(Claude 몫이 됨).
# 달마다 봇(monthly.yml)이 굽기 전에 돌린다 — 홈페이지 하단이 바뀌면 다음 달 화면에 저절로 따라온다.
#
# 손으로 베끼지 않는 까닭 — 하단은 홈페이지·상담소·밑빠진독상도 같이 쓴다(독상 tools/port-footer.py 와 같은 방식).
# 한 번 복사해 두면 주소나 대표 이름이 바뀔 때 한쪽만 고쳐져 갈라진다.
#
# 옮기면서 바꾸는 것
#   1. 캠페이너스 전용 표시와 기본 푸터 감추는 규칙을 걷어낸다
#   2. 안쪽 주소(/34 · /37 · /8)를 action.or.kr 절대 주소로
#   3. 전체 폭으로 펼치는 음수 여백을 끈다(여기는 문서 폭이 이미 전체라 가로 스크롤만 생긴다)
#   4. 이 사이트 화면의 전역 규칙(h2 밑줄·footer 여백·section 여백·.wrap 폭)이 하단에 새지 않게 막는 줄을 덧붙인다
#   5. 하단이 쓰는 글꼴(Pretendard·GmarketSans)을 불러온다 — 홈페이지는 사이트 전체가 불러 두지만 여기 초록 화면들은 기기 글꼴이라
#      안 부르면 제목 글꼴이 달라진다. 주소는 우리 동네 페이지와 같은 것. 초록 화면 본문은 이 글꼴을 안 쓰므로 바뀌지 않는다

import glob
import os
import re
import sys
import urllib.request

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = 'https://raw.githubusercontent.com/bada17/action-home-renewal/main/tools/parts/footer.html'
BEGIN = '<!-- AH:FOOTER START — 홈페이지 공통 하단. scripts/port_footer.py 가 채운다. 손으로 고치지 말 것 -->'
END = '<!-- AH:FOOTER END -->'
LINKS = {'/34': 'https://action.or.kr/34', '/37': 'https://action.or.kr/37', '/8': 'https://action.or.kr/8'}
글꼴 = """<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
<style>@font-face{font-family:'GmarketSans';src:url('https://fastly.jsdelivr.net/gh/projectnoonnu/noonfonts_2001@1.1/GmarketSansBold.woff') format('woff');font-weight:700;font-display:swap}</style>
"""
막기 = """
  /* ── 여기부터 local-finance 가 덧붙임(scripts/port_footer.py) ──
     이 사이트 화면들의 전역 규칙이 하단에 새지 않게 한다 — h2 밑줄·여백(자치단체별), footer 위 선·여백,
     section 위아래 여백(우리 동네), .wrap 의 최대 폭·안쪽 여백. 홈페이지와 한 글자도 다르지 않게 보이려는 것이다. */
  #ah-foot h2,#ah-foot h3{border:0;padding:0;text-transform:none}
  #ah-foot h3{font-family:inherit;line-height:inherit;letter-spacing:normal}
  #ah-foot footer,#ah-foot section{margin:0}
  #ah-foot section{padding:0}
  #ah-foot .wrap{max-width:none;padding:0;display:block}
</style>"""


def 원본():
    p = os.environ.get('AH_FOOTER')
    if p:
        return open(p, encoding='utf-8').read(), p
    with urllib.request.urlopen(URL, timeout=30) as r:
        return r.read().decode('utf-8'), URL


def 다듬기(src):
    body = re.sub(r'<!-- CAMPAIGNERS:COMMON-FOOTER START -->\s*', '', src, count=1)
    body = re.sub(r'<!-- 이 파일 전체를 캠페이너스 하단 반복 섹션[^>]*-->\s*', '', body, count=1)
    body = re.sub(r'\s*<!-- CAMPAIGNERS:COMMON-FOOTER END -->\s*$', '\n', body)
    body = re.sub(r'\s*/\* 캠페이너스 기본 푸터는[^*]*\*/\s*\n\s*#doz_footer_wrap[^\n]*\n', '\n', body, count=1)
    for rel, abs_ in LINKS.items():
        body = body.replace(f'href="{rel}"', f'href="{abs_}"')
    남은 = sorted(set(re.findall(r'href="(/[^"]*)"', body)))
    if 남은:
        raise SystemExit(f'안쪽 주소가 남았다 — LINKS 에 넣을 것: {", ".join(남은)}')
    body, n = re.subn(r'\s*/\* 전체 폭으로 펼치기[^*]*\*/\s*\n\s*margin-left:calc\([^\n]*\n\s*margin-right:calc\([^\n]*\n', '\n', body, count=1)
    if not n:
        print('  ! 전체 폭 음수 여백을 못 찾았다 — 원본이 바뀌었나 볼 것(가로 스크롤이 생길 수 있다)')
    if body.count('</style>') != 1:
        raise SystemExit('원본의 <style> 이 하나가 아니다 — 막는 줄을 어디에 넣을지 다시 볼 것')
    body = body.replace('</style>', 막기, 1)
    if 'id="ah-foot"' not in body:
        raise SystemExit('원본에 #ah-foot 이 없다 — 모양이 바뀌었다')
    return 글꼴 + body.strip()


def main():
    src, 어디 = 원본()
    block = f'{BEGIN}\n{다듬기(src)}\n{END}'
    바뀜 = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'site', '*.html'))):
        n = os.path.basename(p)
        if n == 'dashboard.html':
            continue
        s = open(p, encoding='utf-8').read()
        i, j = s.find(BEGIN), s.find(END)
        if i < 0:
            if s.count('</main>') != 1:
                print(f'  ! {n}: </main> 이 하나가 아니라 건너뜀')
                continue
            t = s.replace('</main>', '</main>\n' + block, 1)
        else:
            t = s[:i] + block + s[j + len(END):]
        if t != s:
            open(p, 'w', encoding='utf-8', newline='').write(t)
            바뀜.append(n)
    print(f'읽음: {어디}')
    print(f'고친 화면 {len(바뀜)}개: {" · ".join(바뀜) or "없음(이미 같음)"}')


if __name__ == '__main__':
    main()
