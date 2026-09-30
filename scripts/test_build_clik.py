"""의회가 잘못 연결되거나 자료가 조용히 사라지는 것을 막는다."""
import unittest
from build_clik import valid_date, council_location, result_group, compile_rows


class ClikTest(unittest.TestCase):
    def test_invalid_dates_are_not_real_dates(self):
        for value in ('', '0', '18000101', '19000101', '19700101', '19700101000000', '202211119', '20260230'):
            self.assertEqual(valid_date(value), '')
        self.assertEqual(valid_date('20240229'), '2024-02-29')

    def test_district_names_need_province(self):
        places = {'서울중구': 'A', '부산중구': 'B', '전남여수시': 'C', '광주북구': 'D', '전남광주본청': 'E', '인천서구': 'F'}
        for name, expected in [('서울특별시 중구의회', 'A'), ('부산광역시 중구의회', 'B'),
                               ('전남광주통합특별시 여수시의회', 'C'), ('전남광주통합특별시 북구의회', 'D'),
                               ('전남광주통합특별시의회', 'E'), ('인천광역시 서해구의회', 'F')]:
            self.assertEqual(council_location(name, places), expected)
        self.assertIsNone(council_location('중구의회', places))
        self.assertIsNone(council_location('충청남도 서산군의회', places))

    def test_ambiguous_integrated_name_is_not_guessed(self):
        self.assertIsNone(council_location('전남광주통합특별시 북구의회', {'전남북구':'A','광주북구':'B'}))

    def test_missing_old_gunwi_code_uses_full_source_name(self):
        rows = [{'DOCID':'CLIKC9','RASMBLY_ID':'054006','RASMBLY_NM':'경상북도 군위군의회','MTG_DE':'20260312'}]
        data, report = compile_rows({'대구군위군':'G'}, [], {'회의록':rows,'의안':[]})
        self.assertEqual(len(data['G']['회의록']), 1)
        self.assertEqual(report['미연결건수']['회의록'], 0)

    def test_status_keeps_uncertain_separate(self):
        self.assertEqual(result_group('처리-가결(원안)'), '원안가결')
        self.assertEqual(result_group('수정의결'), '수정가결')
        self.assertEqual(result_group('분류불가'), '확인 필요')
        self.assertEqual(result_group('생소한 표기'), '기타')

    def test_counts_conserve_rows_and_keep_historical_council(self):
        councils = [{'rasmblyId':'old','의회명':'인천광역시 동구의회','지금있나':False},
                    {'rasmblyId':'new','의회명':'인천광역시 제물포구의회','지금있나':True}]
        rows = [{'DOCID':'CLIKC1','RASMBLY_ID':'old','MTG_DE':'20230101'},
                {'DOCID':'CLIKC2','RASMBLY_ID':'new','MTG_DE':'20260702'},
                {'DOCID':'CLIKC3','RASMBLY_ID':'old','MTG_DE':'0'},
                {'DOCID':'CLIKC4','RASMBLY_ID':'unknown','MTG_DE':'20250101'}]
        data, report = compile_rows({'인천동구':'A','인천제물포구':'B'}, councils, {'회의록':rows,'의안':[]})
        self.assertEqual([r['DOCID'] for r in data['A']['회의록']], ['CLIKC1','CLIKC3'])
        self.assertEqual([r['DOCID'] for r in data['B']['회의록']], ['CLIKC2'])
        self.assertEqual(report['미연결건수']['회의록'], 1)
        self.assertEqual(report['날짜미확인']['회의록'], 1)
        self.assertEqual(report['입력건수']['회의록'], sum(len(d['회의록']) for d in data.values())+1)


if __name__ == '__main__':
    unittest.main()
