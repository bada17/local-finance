import unittest

from read_budget_books import 고르기, 분할파일


class BudgetBookSelectionTest(unittest.TestCase):
    def test_earlier_year_business_book_does_not_beat_current_year_budget_book(self):
        place = {'예산': {
            '주소': 'https://example.go.kr/budget/list',
            '파일': [
                {'이름': '2024년 사업예산서.pdf', '주소': '/files/2024.pdf'},
                {'이름': '2026년 예산서 전체.pdf', '주소': '/files/2026.pdf'},
            ],
            '들어간글': [],
        }}
        self.assertEqual([f['이름'] for f, _ in 고르기(place, 2026)], ['2026년 예산서 전체.pdf'])

    def test_same_attachment_name_uses_current_year_post(self):
        place = {'예산': {
            '주소': 'https://example.go.kr/budget/list',
            '파일': [],
            '들어간글': [
                {'글': '2025년 본예산', '주소': 'https://example.go.kr/budget/2025',
                 '파일': [{'이름': '세출예산사업명세서.pdf', '주소': '/files/old.pdf'}]},
                {'글': '2026년 본예산', '주소': 'https://example.go.kr/budget/2026',
                 '파일': [{'이름': '세출예산사업명세서.pdf', '주소': '/files/new.pdf'}]},
            ],
        }}
        self.assertEqual([f['주소'] for f, _ in 고르기(place, 2026)], ['/files/new.pdf'])

    def test_combined_revenue_and_expenditure_budget_is_a_candidate(self):
        place = {'예산': {
            '주소': 'https://example.go.kr/budget/2026',
            '파일': [{'이름': '2026년 세입세출 예산서', '주소': '/files/budget.pdf'}],
            '들어간글': [],
        }}
        self.assertEqual([f['주소'] for f, _ in 고르기(place, 2026)], ['/files/budget.pdf'])

    def test_department_files_are_grouped_without_special_accounts_or_viewer_duplicates(self):
        files = [
            {'이름': f'2026/세출예산사업명세서({name}).pdf', '주소': f'/2026/{name}.pdf'}
            for name in ('기획과', '문화과', '복지과')
        ]
        files += [
            {'이름': '세출예산사업명세서(기획과).pdf', '주소': "javascript:view('/2026/기획과.pdf')"},
            {'이름': '세출예산사업명세서(주차장특별회계).pdf', '주소': '/2026/parking.pdf'},
        ]
        place = {'예산': {'주소': 'https://example.go.kr/budget', '제목': '2026년 본예산',
                          '파일': files, '들어간글': []}}
        group = 분할파일(place, 2026)
        self.assertEqual([f['주소'] for f, _ in group],
                         ['/2026/기획과.pdf', '/2026/문화과.pdf', '/2026/복지과.pdf'])

    def test_department_names_and_click_only_buttons_are_split_candidates(self):
        # 계룡: 부서 이름만 붙은 그림 단추 / 대구본청: href="#none" 단추가 fileName 으로만 갈린다
        files = [{'이름': n, '주소': f'/_prog/dn00/?file_id={i}'} for i, n in enumerate(
            ['세입예산사업명세서', '조직별 세출총괄표', '의회사무과', '본청(전략기획감사실~상하수도과)', '면동(두마면~금암동)'])]
        place = {'예산': {'주소': 'https://gyeryong.go.kr/budget?list_fyr=2026', '파일': files, '들어간글': []}}
        self.assertEqual([f['이름'] for f, _ in 분할파일(place, 2026)],
                         ['의회사무과', '본청(전략기획감사실~상하수도과)', '면동(두마면~금암동)'])
        files = [{'이름': f'2026_본예산_2_세출예산사업명세서_{i}_{n}.pdf', '주소': '#none'} for i, n in enumerate(['공보관', '행정국'])]
        place = {'예산': {'주소': 'https://jumin.daegu.go.kr/budget', '파일': files, '들어간글': []}}
        self.assertEqual(len(분할파일(place, 2026)), 2)


if __name__ == '__main__':
    unittest.main()
