import copy
import unittest
from clik_action import reserve, settle


class ReservationTest(unittest.TestCase):
    def setUp(self):
        self.day = '2026-09-29'
        self.state = {'갈래': {'보존': 1}, '날짜별호출': {self.day: 900}}

    def test_reserve_then_refund_only_unused_calls(self):
        before = copy.deepcopy(self.state)
        reserved = reserve(self.state, self.day, 'run1')
        self.assertEqual(self.state, before)
        self.assertEqual(reserved['날짜별호출'][self.day], 940)
        reserved['날짜별호출'][self.day] += 3  # another recorded caller
        final = settle(reserved, 'run1', 30)
        self.assertEqual(final['날짜별호출'][self.day], 933)
        self.assertEqual(final['갈래'], {'보존': 1})
        self.assertEqual(final['내부표본호출']['run1']['실호출'], 30)

    def test_quota_and_repeated_run_fail_closed(self):
        self.state['날짜별호출'][self.day] = 950
        with self.assertRaises(ValueError): reserve(self.state, self.day, 'r')
        self.state['날짜별호출'][self.day] = 900
        reserved = reserve(self.state, self.day, 'r')
        with self.assertRaises(ValueError): reserve(reserved, self.day, 'r')

    def test_refund_cannot_repeat_or_exceed_reservation(self):
        reserved = reserve(self.state, self.day, 'r')
        for used in (-1, 41):
            with self.assertRaises(ValueError): settle(reserved, 'r', used)
        final = settle(reserved, 'r', 30)
        with self.assertRaises(ValueError): settle(final, 'r', 30)

    def test_lost_reservation_or_rewound_ledger_never_refunds(self):
        with self.assertRaises(ValueError): settle(self.state, 'missing', 0)
        reserved = reserve(self.state, self.day, 'r')
        reserved['날짜별호출'][self.day] = 900
        with self.assertRaises(ValueError): settle(reserved, 'r', 0)


if __name__ == '__main__': unittest.main()
