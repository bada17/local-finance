"""계약 다시 받기 시험 — python scripts/test_refresh_contracts.py (인터넷 안 씀)."""
import datetime
import gzip
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backfill_contracts
import build_contracts_summary
import refresh_contracts as rc

날A = '20260910'
날B = '20260911'


def 줄(번호, 금액=100, 이름='회수기 구입', 날=날A, 등록='20260911'):
    return {'laf_cd': '4143000', 'laf_hg_nm': '경기도 의왕시', 'wa_laf_hg_nm': '경기', 'ctrt_ldgr_mng_no': 번호,
            'ctrt_trgt_nm': 이름, 'clt_nm': '수퍼빈', 'ctrt_tot_tott_amt': 금액, 'ctrt_mth_nm': '수의1인견적',
            'ctrt_knd_nm': '물품', 'sbc_yn': 'N', 'smz_ctrt_ymd': 날, 'rgstr_dt': 등록, 'data_crt_ymd': 등록}


class 판(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        os.makedirs(os.path.join(self.root, 'data', 'contracts'))

    def tearDown(self):
        self._tmp.cleanup()

    def 하루저장(self, 날, 줄들):
        with gzip.open(os.path.join(self.root, 'data', 'contracts', f'{날}.json.gz'), 'wt', encoding='utf-8') as f:
            json.dump(줄들, f, ensure_ascii=False)

    def 쌓인파일(self):
        폴더 = os.path.join(self.root, 'data', 'contracts_late')
        return sorted(os.listdir(폴더)) if os.path.isdir(폴더) else []

    def 돌리기(self, 답, 날들=(날A,), 오늘='20261104', **더):
        """답 = {날: (줄들, 전체) 또는 일으킬 예외}"""
        불린날 = []

        def 불러오기(날):
            불린날.append(날)
            값 = 답[날]
            if isinstance(값, BaseException):
                raise 값
            return 값
        셈 = rc.다시받기(list(날들), 오늘, 불러오기, root=self.root, 쉬기=0, **더)
        셈['불린날'] = 불린날
        return 셈


class 날고르기(unittest.TestCase):
    def test_최근은_빠짐없이_어제부터_새_날_먼저(self):
        날들 = rc.고를날(datetime.date(2026, 11, 4), 최근=120, 바퀴=30)
        self.assertEqual(날들[0], '20261103')
        self.assertEqual(날들[119], (datetime.date(2026, 11, 3) - datetime.timedelta(days=119)).strftime('%Y%m%d'))
        self.assertNotIn('20261104', 날들)
        self.assertEqual(날들, sorted(날들, reverse=True))

    def test_옛날은_한_바퀴에_모두_한_번씩(self):
        첫날 = datetime.date(2026, 11, 4)
        옛 = (첫날 - datetime.timedelta(days=121)).strftime('%Y%m%d')     # 오늘 기준 최근 밖
        본횟수 = {}
        for i in range(30):
            for 날 in rc.고를날(첫날 + datetime.timedelta(days=i), 최근=0, 바퀴=30):
                if 날 <= 옛:
                    본횟수[날] = 본횟수.get(날, 0) + 1
        전체 = (datetime.date.fromisoformat(f'{옛[:4]}-{옛[4:6]}-{옛[6:]}') - rc.시작).days + 1
        self.assertEqual(len(본횟수), 전체)
        self.assertEqual(set(본횟수.values()), {1})

    def test_시작일_앞은_안_부른다(self):
        날들 = rc.고를날(datetime.date(2026, 11, 4))
        self.assertGreaterEqual(min(날들), rc.시작.strftime('%Y%m%d'))


class 변경분(판):
    def test_새_줄과_고쳐진_줄만_쌓는다(self):
        self.하루저장(날A, [줄('1', 100), 줄('2', 200)])
        새것 = [줄('1', 100), 줄('2', 999), 줄('3', 300)]
        셈 = self.돌리기({날A: (새것, 3)})
        self.assertEqual((셈['새 줄'], 셈['고쳐진 줄'], 셈['금액 바뀐 줄']), (1, 1, 1))
        쌓인 = rc.읽기(os.path.join(self.root, 'data', 'contracts_late', '20261104.json.gz'))
        self.assertEqual(sorted(r['ctrt_ldgr_mng_no'] for r in 쌓인), ['2', '3'])

    def test_등록일_칸만_바뀐_줄은_안_쌓는다(self):
        self.하루저장(날A, [줄('1', 등록='20260911')])
        셈 = self.돌리기({날A: ([줄('1', 등록='20261103')], 1)})
        self.assertEqual((셈['새 줄'], 셈['고쳐진 줄']), (0, 0))
        self.assertEqual(self.쌓인파일(), [])

    def test_합쳐_읽으면_지금_자료와_같다(self):
        self.하루저장(날A, [줄('1', 100), 줄('2', 200)])
        새것 = [줄('1', 100), 줄('2', 999), 줄('3', 300)]
        self.돌리기({날A: (새것, 3)})
        합 = rc.합친하루(날A, rc.늦은줄읽기(self.root), self.root)
        self.assertEqual({r['ctrt_ldgr_mng_no']: r['ctrt_tot_tott_amt'] for r in 합}, {'1': 100, '2': 999, '3': 300})

    def test_늦게_받은_파일이_앞_파일을_이긴다(self):
        self.하루저장(날A, [줄('1', 100)])
        self.돌리기({날A: ([줄('1', 200)], 1)}, 오늘='20261103')
        self.돌리기({날A: ([줄('1', 300)], 1)}, 오늘='20261104')
        self.assertEqual(self.쌓인파일(), ['20261103.json.gz', '20261104.json.gz'])
        합 = rc.합친하루(날A, rc.늦은줄읽기(self.root), self.root)
        self.assertEqual([r['ctrt_tot_tott_amt'] for r in 합], [300])

    def test_같은_날_또_돌려도_그대로다(self):
        self.하루저장(날A, [줄('1', 100)])
        답 = {날A: ([줄('1', 100), 줄('2', 200)], 2)}
        self.돌리기(답)
        길 = os.path.join(self.root, 'data', 'contracts_late', '20261104.json.gz')
        처음 = open(길, 'rb').read()
        셈 = self.돌리기(답)
        self.assertEqual(셈['새 줄'], 0)
        self.assertEqual(open(길, 'rb').read(), 처음)

    def test_같은_날_둘째_돌림은_첫째_것에_더한다(self):
        self.하루저장(날A, [줄('1', 100)])
        self.돌리기({날A: ([줄('1', 100), 줄('2', 200)], 2)})
        self.돌리기({날A: ([줄('1', 100), 줄('2', 200), 줄('3', 300)], 3)})
        쌓인 = rc.읽기(os.path.join(self.root, 'data', 'contracts_late', '20261104.json.gz'))
        self.assertEqual(sorted(r['ctrt_ldgr_mng_no'] for r in 쌓인), ['2', '3'])

    def test_0줄_파일인_날도_채워진다(self):
        self.하루저장(날A, [])
        self.돌리기({날A: ([줄('1'), 줄('2')], 2)})
        self.assertEqual(len(rc.합친하루(날A, rc.늦은줄읽기(self.root), self.root)), 2)

    def test_저쪽에서_사라진_줄은_세기만_하고_지우지_않는다(self):
        self.하루저장(날A, [줄('1'), 줄('2')])
        셈 = self.돌리기({날A: ([줄('1')], 1)})
        self.assertEqual(셈['사라진 줄'], 1)
        self.assertEqual(len(rc.합친하루(날A, rc.늦은줄읽기(self.root), self.root)), 2)

    def test_파일_없는_날은_건너뛴다_채우기_몫(self):
        셈 = self.돌리기({날A: ([줄('1')], 1)})
        self.assertEqual(셈['불린날'], [])
        self.assertEqual(셈['파일 없는 날'], 1)


class 실패(판):
    def test_덜_받은_날은_안_쌓고_실패로_센다(self):
        self.하루저장(날A, [줄('1')])
        셈 = self.돌리기({날A: ([줄('1'), 줄('2')], 3)})
        self.assertEqual(셈['실패'], 1)
        self.assertEqual(self.쌓인파일(), [])

    def test_자료_없다는_답은_실패가_아니다(self):
        self.하루저장(날A, [])
        셈 = self.돌리기({날A: SystemExit('오류 {"RESULT": [{"CODE": "INFO-200"}]}')})
        self.assertEqual(셈['실패'], 0)

    def test_시간초과가_나도_앞서_받은_것은_남는다(self):
        self.하루저장(날A, [줄('1')])
        self.하루저장(날B, [줄('9', 날=날B)])
        셈 = self.돌리기({날B: ([줄('9', 날=날B), 줄('8', 날=날B)], 2), 날A: SystemExit('세 번 다 실패: timed out')}, 날들=(날B, 날A))
        self.assertEqual(셈['실패'], 1)
        self.assertEqual(len(rc.합친하루(날B, rc.늦은줄읽기(self.root), self.root)), 2)

    def test_세_번_내리_실패하면_멈춘다(self):
        날들 = [f'202609{d:02d}' for d in range(1, 8)]
        for 날 in 날들:
            self.하루저장(날, [줄('1', 날=날)])
        셈 = self.돌리기({날: SystemExit('세 번 다 실패') for 날 in 날들}, 날들=날들)
        self.assertEqual(len(셈['불린날']), 3)
        self.assertEqual(셈['못 본 날'], 4)

    def test_시간이_다_되면_멈추고_받은_것은_남긴다(self):
        self.하루저장(날A, [줄('1')])
        self.하루저장(날B, [줄('9', 날=날B)])
        셈 = self.돌리기({날B: ([줄('9', 날=날B), 줄('8', 날=날B)], 2), 날A: ([줄('1')], 1)}, 날들=(날B, 날A), 초=-1)
        self.assertEqual(셈['불린날'], [])
        self.assertEqual(셈['못 본 날'], 2)


class 채우기빈파일(unittest.TestCase):
    """2026-10-21: 시간 초과를 「자료 없는 날」로 읽어 평일 파일이 0줄로 굳었다."""

    def 하루(self, 답):
        with tempfile.TemporaryDirectory() as 폴더, mock.patch.object(backfill_contracts, 'OUT', 폴더), \
                mock.patch.object(backfill_contracts, 'fetch', side_effect=답):
            n, 불렀나 = backfill_contracts.하루('20261020', 'key')
            return n, 불렀나, os.listdir(폴더)

    def test_시간초과면_파일을_안_만든다(self):
        n, 불렀나, 파일 = self.하루(SystemExit("세 번 다 실패: URLError(TimeoutError('timed out'))"))
        self.assertEqual((n, 불렀나, 파일), (None, True, []))

    def test_자료_없는_날만_빈_파일을_남긴다(self):
        n, 불렀나, 파일 = self.하루(SystemExit('오류 {"RESULT": [{"CODE": "INFO-200"}]}'))
        self.assertEqual((n, 불렀나, 파일), (0, True, ['20261020.json.gz']))


class 요약에서도_합쳐_센다(판):
    def test_고쳐진_금액과_새_줄이_요약에_든다(self):
        self.하루저장(날A, [줄('1', 100)])
        self.돌리기({날A: ([줄('1', 150), 줄('2', 200)], 2)})
        b = build_contracts_summary
        with mock.patch.object(b, 'ROOT', self.root), \
                mock.patch.object(b, 'IN', os.path.join(self.root, 'data', 'contracts')), \
                mock.patch.object(b, 'OUT', os.path.join(self.root, 'data', 'contracts_summary.json')), \
                mock.patch.object(b, '곳별', os.path.join(self.root, 'site_contracts')), \
                mock.patch.object(sys, 'argv', ['build_contracts_summary.py']):
            b.main()
        with open(os.path.join(self.root, 'data', 'contracts_summary.json'), encoding='utf-8') as f:
            요약 = json.load(f)
        칸 = 요약['곳']['4143000']['2026']
        self.assertEqual((칸['건수'], 칸['금액']), (2, 350))


if __name__ == '__main__':
    unittest.main()
