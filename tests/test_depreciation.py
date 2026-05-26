"""折旧测算核心计算逻辑测试。"""

import unittest
from datetime import datetime

from audit_tools.common.amount import to_number, parse_date
from audit_tools.depreciation.helpers import normalize_life, expected_months


class TestNormalizeLife(unittest.TestCase):

    def test_years_to_months(self):
        self.assertEqual(normalize_life(10), 120)

    def test_already_months(self):
        self.assertEqual(normalize_life(60), 60)

    def test_zero(self):
        self.assertEqual(normalize_life(0), 0)

    def test_boundary_50(self):
        self.assertEqual(normalize_life(50), 600)

    def test_boundary_51(self):
        self.assertEqual(normalize_life(51), 51)


class TestExpectedMonths(unittest.TestCase):

    def setUp(self):
        self.audit_year = 2025
        self.life = 120  # 10年

    def test_acquired_before_audit_year(self):
        months, tag = expected_months(
            datetime(2020, 6, 1), self.audit_year, self.life, None, False, 0, False
        )
        self.assertEqual(months, 12)
        self.assertEqual(tag, "")

    def test_acquired_in_audit_year_march(self):
        months, tag = expected_months(
            datetime(2025, 3, 1), self.audit_year, self.life, None, False, 0, False
        )
        self.assertEqual(months, 9)

    def test_acquired_in_audit_year_december(self):
        months, tag = expected_months(
            datetime(2025, 12, 1), self.audit_year, self.life, None, False, 0, False
        )
        self.assertEqual(months, 0)

    def test_acquired_after_audit_year(self):
        months, tag = expected_months(
            datetime(2026, 3, 1), self.audit_year, self.life, None, False, 0, False
        )
        self.assertEqual(months, 0)
        self.assertEqual(tag, "未来年度入账")

    def test_already_fully_depreciated(self):
        months, tag = expected_months(
            datetime(2015, 6, 1), self.audit_year, self.life, 121, False, 0, False
        )
        self.assertEqual(months, 0)
        self.assertEqual(tag, "已提足")

    def test_almost_fully_depreciated(self):
        # 已提119个月，life=120，remaining_at_start = 120 - (119-1) = 2
        months, tag = expected_months(
            datetime(2015, 6, 1), self.audit_year, self.life, 119, False, 0, False
        )
        self.assertEqual(months, 2)

    def test_disposed_mid_year(self):
        months, tag = expected_months(
            datetime(2020, 6, 1), self.audit_year, self.life, None, True, 5, True
        )
        self.assertEqual(months, 5)
        self.assertEqual(tag, "")

    def test_disposed_late(self):
        # disposal_month > 12 so months stays at 12
        months, tag = expected_months(
            datetime(2020, 6, 1), self.audit_year, self.life, None, True, 13, True
        )
        self.assertEqual(months, 12)
        self.assertEqual(tag, "有处置")


class TestToNumber(unittest.TestCase):

    def test_basic(self):
        self.assertEqual(to_number("1000"), 1000.0)

    def test_negative_in_parens(self):
        self.assertEqual(to_number("(500)"), -500.0)

    def test_rmb_yuan(self):
        self.assertEqual(to_number("\uffe51234"), 1234.0)


class TestParseDate(unittest.TestCase):

    def test_dash_format(self):
        dt = parse_date("2025-06-15")
        self.assertEqual(dt.year, 2025)
        self.assertEqual(dt.month, 6)

    def test_cn_format(self):
        dt = parse_date("2025年06月15日")
        self.assertEqual(dt.day, 15)

    def test_year_month(self):
        dt = parse_date("2025/06")
        self.assertEqual(dt.day, 1)

    def test_invalid(self):
        self.assertIsNone(parse_date("not a date"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
