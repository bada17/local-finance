import unittest
from read_post_files import 표풀기, 금액, 날짜, 해찾기


class 표풀기Test(unittest.TestCase):
    def test_one_row_header_skips_title_and_total(self):
        표 = [['2026년 07월 군수 업무추진비 사용내역', '', '', '', ''],
             ['□ 세부 집행내역(기관운영업무추진비)', '', '', '', ''],
             ['사용일자(일시)', '사용장소', '내 역', '금 액(원)', '사용방법'],
             ['계', '', '', '2443500', ''],
             ['2026-07-01 12:06', '본동복어', '간담회 식사', '150000', '카드']]
        줄 = 표풀기(표, 2026)
        self.assertEqual(줄, [{'날짜': '2026-07-01', '장소': '본동복어', '내용': '간담회 식사', '인원': '', '금액': 150000, '방법': '카드'}])

    def test_cash_card_split_two_row_header_and_year_from_title(self):
        표 = [['일자', '집행내용', '집행방법', '', '대상 (명)', '집행 장소'],
             ['', '', '현금', '카드', '', ''],
             ['07월01일', '화분 구입', '', '50,000', '1', '생화당'],
             ['07월06일', '경조사비', '100,000', '', '2', '']]
        줄 = 표풀기(표, 2026)
        self.assertEqual([(r['날짜'], r['금액'], r['방법']) for r in 줄],
                         [('2026-07-01', 50000, '카드'), ('2026-07-06', 100000, '현금')])

    def test_summary_rows_are_dropped(self):
        표 = [['구분', '일시', '장소', '내용', '금액'],
             ['기관', '', '', '50건', '13,154,210'],
             ['기관', '2026-09-02', '식당', '오찬', '₩ 120,000']]
        self.assertEqual([r['금액'] for r in 표풀기(표, 2026)], [120000])


class 조각Test(unittest.TestCase):
    def test_amount_and_date(self):
        self.assertEqual(금액('₩ 1,980,000'), 1980000)
        self.assertIsNone(금액('6명'))
        self.assertEqual(날짜('2025.8.4. 12:30', None), '2025-08-04')
        self.assertEqual(날짜('9/3', 2026), '2026-09-03')
        self.assertEqual(날짜('46113', 2026), '2026-04-01')        # 엑셀 날짜 번호
        self.assertEqual(날짜('20260318', 2026), '2026-03-18')
        self.assertEqual(날짜('25.03.13', 2025), '2025-03-13')     # 두 자리 해
        self.assertEqual(날짜('2028-06-26', 2025), '2025-06-26')   # 원문 오타는 글의 해로

    def test_split_month_day_and_merged_date(self):
        표 = [['연번', '사용일시', '', '사용장소', '사용목적', '사용금액'],
             ['1', '9', '1', '뉴동해컨벤션', '오찬', '275,000'],
             ['2', '', '', '해성상사', '커피', '191,400']]
        self.assertEqual([r['날짜'] for r in 표풀기(표, 2026)], ['2026-09-01', '2026-09-01'])

    def test_year_prefers_file_name(self):
        self.assertEqual(해찾기('2025년 12월 단체장.pdf', '2026년 9월 단체장', '2026-10-01'), 2025)
        self.assertEqual(해찾기("안동시장 (‘26. 9월)", None), 2026)


if __name__ == '__main__':
    unittest.main()
