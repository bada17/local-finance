# 검토용 엑셀 — data/disclosure_tags_곳.csv · _항목.csv 를 시트로, 꼬리표 뜻 시트를 맨 앞에.
import csv, sys, collections
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

root, out = sys.argv[1], sys.argv[2]
뜻 = [
    ('곳 꼬리표', '', ''),
    ('⓪ 점검 대상에 없음', '2026 새 구역 — 지방재정365 FINLK 가 주소를 안 줌', '그쪽 목록 상태'),
    ('① 주소가 죽음', '지방재정365 가 준 주소가 안 열림(손으로 새 주소 찾은 곳은 그렇게 적음)', '시민도 링크로 못 봄'),
    ('② 받은 주소로 직접 들어가면 막음', '「잘못된 접근」 경고 뒤 첫 화면으로', '시민도 링크로 못 봄'),
    ('③ 자동 접속을 막음(우리만 못 봄)', '「개발자도구감지」 등 — 사람 브라우저는 열림', '우리 한계'),
    ('④ 주소가 공시 화면이 아님', '첫 화면·예산서 목록·엉뚱한 게시판으로 감', '시민이 헤맴'),
    ('④′ 화면 이름은 예산서인데 공시 묶음이 붙음', '화면 이름과 내용이 다름', ''),
    ('⑤ 한 단계 더 들어가야 함', '안내 화면·목록 — 공시 글로 한 겹 더', '한 번 더 누름'),
    ('⑥ 파일 이름이 없음 / 못 옮김', '「다운받기」 단추만', ''),
    ('⑦ 파일 대신 화면에 숫자', '부천 재정 누리집', '판단 필요'),
    ('⑧ 화면은 열렸는데 파일을 못 잡음', '자동이 파일 링크를 못 찾음', '우리 한계일 수 있음'),
    ('⑨ 오늘 못 봄', '응답 없음·접속 차단(11-11)', '다시 볼 것'),
    ('', '', ''),
    ('항목 꼬리표(60조 각 호)', '', ''),
    ('A', '공시 묶음 파일 안 양식 칸에 값(숫자)이 있음 — 「어디」「쪽」「보인 글」이 근거', '있음'),
    ('B', '따로 올린 파일의 이름에 그 항목 말이 있음', '있음(이름 근거)'),
    ('H', '공시 파일이 그 칸에 「해당 없음」이라 적음', '해당 없음'),
    ('R', '공시 칸이 「항목별 참조·별도·수시 공시」로 넘기는데 이 파일엔 값 쪽이 없음', '다른 데 있을 수 있음'),
    ('D', '공시 목록 밖 누리집(메뉴 경로·2024년 뒤 날짜 붙은 글)에 그 말이 나옴 — 공시 항목인지는 사람이 확인', '목록 밖'),
    ('N', '공시 묶음에 칸 이름만 있고 숫자 없음', ''),
    ('T', '공시 묶음 목차에만 칸 이름이 있음', ''),
    ('K', '공시 묶음 칸에 있으나 문서의 해를 못 읽음', '해 확인 필요'),
    ('O', '옛 해(기준해 앞) 공시·파일에만 있음', '옛 것만'),
    ('Z', '그 항목이 들어가는 기준(예산/결산) 공시 묶음을 못 받음', '못 봄'),
    ('X', '받은 같은 기준 공시 묶음 안에 그 칸이 없음', '없음(받은 것 안에서)'),
    ('Y', '받은 파일에 공시 묶음이 없고 이름에도 없음', '못 찾음'),
    ('U', '파일을 못 받거나 못 읽음(까닭 적음)', '못 봄'),
    ('P', '공시 화면에서 파일을 못 잡음(곳 꼬리표 볼 것)', '못 봄'),
    ('?', '10호 — 양식에 이 이름의 칸이 없어 짝을 못 지음', '짝 미정'),
    ('', '', ''),
    ('근거 원문', '지방재정법 제60조(시행 2026-10-20, 국가법령정보센터 lsiSeq 291245), 공시 양식 칸 이름은 받은 공시 파일에서', ''),
    ('기준해', '2024 — 이 해 앞의 공시는 옛 것(결산공시는 한 해 늦게 나옴)', ''),
]
wb = openpyxl.Workbook()
ws = wb.active
ws.title = '꼬리표 뜻'
ws.append(['꼬리표', '뜻', '한마디'])
for r in 뜻:
    ws.append(list(r))
for c in ws[1]:
    c.font = Font(bold=True)
ws.column_dimensions['A'].width = 34
ws.column_dimensions['B'].width = 90
ws.column_dimensions['C'].width = 20
머리 = PatternFill('solid', fgColor='DDDDDD')
for 이름, 파일, 너비 in (('곳', 'disclosure_tags_곳.csv', {}), ('곳×항목', 'disclosure_tags_항목.csv', {})):
    s = wb.create_sheet(이름)
    줄들 = list(csv.reader(open(f'{root}/data/{파일}', encoding='utf-8-sig')))
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    for r in 줄들:
        s.append([ILLEGAL_CHARACTERS_RE.sub(' ', v) for v in r])   # 누리집 글에 섞인 제어 문자는 엑셀이 못 받는다
    for c in s[1]:
        c.font = Font(bold=True)
        c.fill = 머리
        c.alignment = Alignment(wrap_text=True)
    s.freeze_panes = 'C2'
    s.auto_filter.ref = s.dimensions
    for i, h in enumerate(줄들[0], 1):
        w = max(len(h) * 2, min(60, max((len(r[i - 1]) for r in 줄들[1:] if len(r) >= i), default=8)))
        s.column_dimensions[openpyxl.utils.get_column_letter(i)].width = max(8, min(60, w))
# 요약 시트 — 항목별 꼬리표 수
s = wb.create_sheet('항목별 셈', 1)
줄들 = list(csv.DictReader(open(f'{root}/data/disclosure_tags_항목.csv', encoding='utf-8-sig')))
글자 = sorted({r['꼬리표'][:1] for r in 줄들}, key='ABHRDNTKOZXYUP?'.find)
s.append(['호', '항목'] + 글자)
본 = collections.OrderedDict()
for r in 줄들:
    본.setdefault((r['호'], r['항목']), collections.Counter())[r['꼬리표'][:1]] += 1
for (호, 항목), c in 본.items():
    s.append([호, 항목] + [c.get(g, 0) for g in 글자])
for c in s[1]:
    c.font = Font(bold=True)
s.column_dimensions['B'].width = 36
wb.save(out)
print('적음', out)
