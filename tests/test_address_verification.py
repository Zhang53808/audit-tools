"""函证地址核查 - 单元测试（移植版）。

从根目录测试文件移植，更新为 package import。
"""

import unittest
from audit_tools.common.address import clean_address, multi_strategy_similarity


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
        self.assertNotIn("，", result)

    def test_extra_spaces(self):
        self.assertEqual(clean_address("  济南市  工业南路  89号  "), "工业南路89号")

    def test_empty_string(self):
        self.assertEqual(clean_address(""), "")

    def test_none_value(self):
        self.assertEqual(clean_address(None), "")

    def test_non_string(self):
        self.assertEqual(clean_address(123), "")

    def test_nan_string(self):
        self.assertEqual(clean_address("nan"), "nan")

    def test_already_clean(self):
        self.assertEqual(clean_address("工业南路89号"), "工业南路89号")

    def test_street_level_preserved(self):
        result = clean_address("江苏省南京市鼓楼区汉口路22号")
        self.assertIn("汉口路22号", result)


class TestMultiStrategySimilarity(unittest.TestCase):

    def test_identical(self):
        score, strategy = multi_strategy_similarity("济南市工业南路89号", "济南市工业南路89号")
        self.assertGreaterEqual(score, 85)
        self.assertEqual(strategy, "ratio")

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

    def test_same_area_different_writing(self):
        score, _ = multi_strategy_similarity("深圳市南山区科技园R2-B栋", "深圳南山科技园R2B栋402")
        self.assertGreaterEqual(score, 70)

    def test_completely_different(self):
        score, _ = multi_strategy_similarity("北京市朝阳区建国路88号", "广州市天河区体育西路100号")
        self.assertLess(score, 70)

    def test_different_city_same_district_name(self):
        score, _ = multi_strategy_similarity("武汉市洪山区珞喻路200号", "武汉市洪山区光谷大道100号")
        self.assertLess(score, 85)

    def test_both_empty(self):
        score, _ = multi_strategy_similarity("", "")
        self.assertEqual(score, 0.0)

    def test_one_empty(self):
        score, _ = multi_strategy_similarity("济南市工业南路89号", "")
        self.assertEqual(score, 0.0)

    def test_partial_strategy_activated(self):
        _, strategy = multi_strategy_similarity(
            "陆家嘴环路1000号", "上海市浦东新区陆家嘴环路1000号恒生银行大厦18楼"
        )
        self.assertIn(strategy, ["partial", "token_sort", "ratio"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
