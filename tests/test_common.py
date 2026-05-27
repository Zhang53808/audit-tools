"""公共模块单元测试。

覆盖 common/address.py, common/amount.py, common/text.py
"""

import unittest
from datetime import datetime
from pathlib import Path

from audit_tools.common.address import clean_address, multi_strategy_similarity
from audit_tools.common.amount import clean_amount, to_number, parse_date
from audit_tools.common.text import sanitize_filename, unique_path


class TestCleanAddress(unittest.TestCase):

    def test_remove_province(self):
        self.assertEqual(clean_address("山东省济南市工业南路89号"), "工业南路89号")

    def test_remove_autonomous_region(self):
        self.assertEqual(
            clean_address("广西壮族自治区南宁市青秀区民族大道100号"),
            "民族大道100号"
        )

    def test_remove_municipality(self):
        self.assertEqual(clean_address("上海市浦东新区陆家嘴环路1000号"), "陆家嘴环路1000号")

    def test_multi_level_prefix(self):
        self.assertEqual(
            clean_address("新疆维吾尔自治区乌鲁木齐市天山区解放北路100号"),
            "解放北路100号"
        )

    def test_prefecture_city(self):
        self.assertEqual(clean_address("湖北省武汉市洪山区珞喻路200号"), "珞喻路200号")

    def test_abbreviation_gaoxin(self):
        self.assertEqual(
            clean_address("成都市高新技术产业开发区天府大道999号"),
            "天府大道999号"
        )

    def test_fullwidth_punctuation(self):
        result = clean_address("北京市朝阳区（CBD）建国路88号")
        self.assertIn("(CBD)", result)
        self.assertIn("建国路88号", result)

    def test_fullwidth_comma(self):
        result = clean_address("深圳市，南山区，科技园路1号")
        self.assertIn("科技园路1号", result)

    def test_extra_spaces(self):
        self.assertEqual(clean_address("  济南市  工业南路  89号  "), "工业南路89号")

    def test_empty_string(self):
        self.assertEqual(clean_address(""), "")

    def test_none_value(self):
        self.assertEqual(clean_address(None), "")

    def test_non_string(self):
        self.assertEqual(clean_address(123), "")

    def test_already_clean(self):
        self.assertEqual(clean_address("工业南路89号"), "工业南路89号")

    def test_street_level_preserved(self):
        result = clean_address("江苏省南京市鼓楼区汉口路22号")
        self.assertIn("汉口路22号", result)


class TestMultiStrategySimilarity(unittest.TestCase):

    def test_identical(self):
        score, strategy = multi_strategy_similarity("济南市工业南路89号", "济南市工业南路89号")
        self.assertGreaterEqual(score, 85)

    def test_province_prefix_diff(self):
        score, _ = multi_strategy_similarity("山东省济南市工业南路89号", "济南市工业南路89号")
        self.assertGreaterEqual(score, 85)

    def test_district_prefix_diff(self):
        score, _ = multi_strategy_similarity("上海市浦东新区陆家嘴环路1000号", "陆家嘴环路1000号")
        self.assertGreaterEqual(score, 85)

    def test_abbreviation_diff(self):
        score, _ = multi_strategy_similarity(
            "成都市高新技术产业开发区天府大道999号", "成都市高新区天府大道999号"
        )
        self.assertGreaterEqual(score, 85)

    def test_different_door_number(self):
        score, _ = multi_strategy_similarity("福建省厦门市思明区中山路100号", "福建省厦门市思明区中山路120号")
        self.assertGreaterEqual(score, 70)

    def test_completely_different(self):
        score, _ = multi_strategy_similarity("北京市朝阳区建国路88号", "广州市天河区体育西路100号")
        self.assertLess(score, 70)

    def test_both_empty(self):
        score, _ = multi_strategy_similarity("", "")
        self.assertEqual(score, 0.0)

    def test_one_empty(self):
        score, _ = multi_strategy_similarity("济南市工业南路89号", "")
        self.assertEqual(score, 0.0)


class TestCleanAmount(unittest.TestCase):

    def test_clean_number(self):
        self.assertEqual(clean_amount("1,234.56"), 1234.56)

    def test_rmb_symbol(self):
        self.assertAlmostEqual(clean_amount("\uffe51,234.56"), 1234.56)

    def test_parentheses_negative(self):
        self.assertAlmostEqual(clean_amount("(1,234.56)"), -1234.56)

    def test_none_value(self):
        self.assertEqual(clean_amount(None), 0.0)

    def test_empty_string(self):
        self.assertEqual(clean_amount(""), 0.0)

    def test_float_value(self):
        self.assertEqual(clean_amount(100.5), 100.5)

    def test_int_value(self):
        self.assertEqual(clean_amount(500), 500.0)


class TestToNumber(unittest.TestCase):

    def test_normal_number(self):
        self.assertEqual(to_number("1234.56"), 1234.56)

    def test_percent_sign(self):
        self.assertEqual(to_number("5%"), 5.0)

    def test_parentheses_negative(self):
        self.assertEqual(to_number("(1,234.56)"), -1234.56)

    def test_none_default(self):
        self.assertEqual(to_number(None), 0.0)

    def test_custom_default(self):
        self.assertEqual(to_number(None, -999), -999.0)


class TestParseDate(unittest.TestCase):

    def test_full_date(self):
        result = parse_date("2025-03-15")
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.month, 3)
        self.assertEqual(result.day, 15)

    def test_chinese_date(self):
        result = parse_date("2025年03月15日")
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.year, 2025)

    def test_year_month_only(self):
        result = parse_date("2025-03")
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.day, 1)

    def test_datetime_object(self):
        dt = datetime(2025, 6, 1)
        self.assertEqual(parse_date(dt), dt)

    def test_none_value(self):
        self.assertIsNone(parse_date(None))


class TestSanitizeFilename(unittest.TestCase):

    def test_remove_illegal_chars(self):
        result = sanitize_filename('test:file<name>.pdf')
        self.assertNotIn(":", result)
        self.assertNotIn("<", result)

    def test_compress_spaces(self):
        result = sanitize_filename("a   b")
        self.assertEqual(result, "a b")


class TestUniquePath(unittest.TestCase):
    def test_no_collision(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "test.pdf"
            result = unique_path(p)
            self.assertEqual(result, p)

    def test_with_collision(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "test.pdf"
            base.write_text("a")
            result = unique_path(base)
            self.assertEqual(result.stem, "test_2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
