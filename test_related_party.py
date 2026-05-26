#!/usr/bin/env python3
"""
关联方识别 - 单元测试
====================
覆盖12个维度函数 + 模拟案例端到端 + 边界测试
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from related_party_check import (
    _build_fixture,
    _clean_address,
    _address_similarity,
    _name_similarity,
    _extract_names,
    check_D01_equity,
    check_D02_common_shareholders,
    check_D03_actual_controller,
    check_D04_executive_overlap,
    check_D05_legal_rep_cross,
    check_D06_legal_rep_trajectory,
    check_D07_same_address,
    check_D08_shared_contact,
    check_D10_name_similarity,
    check_D11_insured_anomaly,
    check_D12_supplement_personnel,
    calculate_risk,
)

# 加载 fixture
audit, targets = _build_fixture()
target_map = {t["name"]: t for t in targets}


class TestHelperFunctions(unittest.TestCase):
    """工具函数测试"""

    def test_clean_address_province(self):
        self.assertEqual(_clean_address("山东省济南市工业南路89号"), "工业南路89号")

    def test_clean_address_fullwidth(self):
        result = _clean_address("北京市朝阳区（CBD）建国路88号")
        self.assertIn("(CBD)", result)

    def test_address_similarity_identical(self):
        sim = _address_similarity("天津市滨海新区信环西路20号", "天津市滨海新区信环西路20号")
        self.assertGreaterEqual(sim, 90)

    def test_address_similarity_close(self):
        sim = _address_similarity("天津市滨海新区经济技术开发区信环西路20号", "天津市滨海新区经济技术开发区信环西路18号")
        self.assertGreaterEqual(sim, 70)

    def test_name_similarity_suffix_ignored(self):
        sim = _name_similarity("辰星科技股份有限公司", "通用企业股份有限公司")
        self.assertLess(sim, 50)

    def test_name_similarity_related(self):
        sim = _name_similarity("辰星科技股份有限公司", "辰研咨询有限公司")
        self.assertLess(sim, 50)  # 不靠fuzz，靠子策略

    def test_extract_names(self):
        result = _extract_names(["张某某(30%)", "李某某(25%)", "辰星控股有限公司(45%)"])
        self.assertEqual(result, {"张某某", "李某某", "辰星控股有限公司"})

    def test_extract_names_empty(self):
        self.assertEqual(_extract_names([]), set())


class TestDimensionFunctions(unittest.TestCase):
    """12维度函数测试"""

    # ---- D01 股权穿透 ----
    def test_D01_equity_triggered(self):
        t = target_map["辰研咨询有限公司"]
        triggered, reason = check_D01_equity(audit, t)
        self.assertTrue(triggered)
        self.assertIn("辰星控股有限公司", reason)

    def test_D01_equity_clean(self):
        t = target_map["通用企业股份有限公司"]
        triggered, reason = check_D01_equity(audit, t)
        self.assertFalse(triggered)

    # ---- D02 共同股东 ----
    def test_D02_common_shareholders(self):
        results = check_D02_common_shareholders(targets)
        # #2 和 #3 共享股东梁某
        self.assertTrue(results["锦程科技有限公司"][0])
        self.assertTrue(results["锦程信息咨询有限公司"][0])
        # 无关企业不应触发
        self.assertFalse(results["通用企业股份有限公司"][0])

    # ---- D03 实际控制人 ----
    def test_D03_actual_controller_triggered(self):
        t = target_map["北辰区锐达科技有限公司"]
        triggered, reason = check_D03_actual_controller(audit, t)
        self.assertTrue(triggered)
        self.assertIn("张某某", reason)

    def test_D03_actual_controller_clean(self):
        t = target_map["通用企业股份有限公司"]
        triggered, _ = check_D03_actual_controller(audit, t)
        self.assertFalse(triggered)

    # ---- D04 高管重叠 ----
    def test_D04_executive_overlap_triggered(self):
        t = target_map["锦程科技有限公司"]
        triggered, reason = check_D04_executive_overlap(audit, t)
        self.assertTrue(triggered)
        self.assertIn("王某某", reason)

    def test_D04_executive_overlap_clean(self):
        t = target_map["通用企业股份有限公司"]
        triggered, _ = check_D04_executive_overlap(audit, t)
        self.assertFalse(triggered)

    # ---- D05 法定代表人交叉 ----
    def test_D05_legal_rep_cross(self):
        results = check_D05_legal_rep_cross(targets)
        # 梁某是 #2 和 #3 的法人
        self.assertTrue(results["锦程科技有限公司"][0])
        self.assertTrue(results["锦程信息咨询有限公司"][0])
        # 无关企业不应触发
        self.assertFalse(results["通用企业股份有限公司"][0])

    # ---- D06 法人变更轨迹 ----
    def test_D06_legal_rep_trajectory_triggered(self):
        t = target_map["汇鑫信息技术有限公司"]
        triggered, reason = check_D06_legal_rep_trajectory(audit, t)
        self.assertTrue(triggered)
        self.assertIn("赵某", reason)

    def test_D06_legal_rep_trajectory_clean(self):
        t = target_map["通用企业股份有限公司"]
        triggered, _ = check_D06_legal_rep_trajectory(audit, t)
        self.assertFalse(triggered)

    # ---- D07 同址经营 ----
    def test_D07_same_address_triggered(self):
        t = target_map["辰创商贸有限公司"]
        triggered, reason = check_D07_same_address(audit, t)
        self.assertTrue(triggered)
        self.assertIn("信环西路", reason)

    def test_D07_same_address_clean(self):
        t = target_map["通用企业股份有限公司"]
        triggered, _ = check_D07_same_address(audit, t)
        self.assertFalse(triggered)

    # ---- D08 联系方式共用 ----
    def test_D08_shared_contact_triggered(self):
        results = check_D08_shared_contact(targets)
        # #1 和 #5 共用 138****5678
        self.assertTrue(results["星海贸易有限公司"][0])
        self.assertTrue(results["星辉科技有限公司"][0])

    def test_D08_shared_contact_clean(self):
        results = check_D08_shared_contact(targets)
        # 修复后 email 域名已不同，无关企业不触发
        self.assertFalse(results["通用企业股份有限公司"][0])

    # ---- D10 名称相似 ----
    def test_D10_name_similarity_triggered(self):
        t = target_map["辰研咨询有限公司"]
        triggered, reason = check_D10_name_similarity(audit, t)
        self.assertTrue(triggered)
        self.assertIn("辰", reason)

    def test_D10_name_similarity_clean(self):
        t = target_map["通用企业股份有限公司"]
        triggered, reason = check_D10_name_similarity(audit, t)
        self.assertFalse(triggered)

    # ---- D11 参保人数异常 ----
    def test_D11_insured_anomaly_triggered(self):
        t = target_map["北辰区锐达科技有限公司"]  # 0人参保 + 950万
        triggered, reason = check_D11_insured_anomaly(t)
        self.assertTrue(triggered)

    def test_D11_insured_anomaly_not_triggered(self):
        t = target_map["星海贸易有限公司"]  # 5人参保
        triggered, _ = check_D11_insured_anomaly(t)
        self.assertFalse(triggered)

    # ---- D12 补充人员 ----
    def test_D12_supplement_personnel_triggered(self):
        t = target_map["锦程科技有限公司"]
        triggered, reason = check_D12_supplement_personnel(t, ["王某某", "周某某"])
        self.assertTrue(triggered)
        self.assertIn("王某某", reason)

    def test_D12_supplement_personnel_none(self):
        t = target_map["锦程科技有限公司"]
        triggered, _ = check_D12_supplement_personnel(t, None)
        self.assertFalse(triggered)


class TestRiskScoring(unittest.TestCase):
    """风险评分测试"""

    def test_zero_flags(self):
        level, label = calculate_risk(0, False)
        self.assertIn("低风险", label)

    def test_one_flag(self):
        level, label = calculate_risk(1, False)
        self.assertIn("中风险", label)

    def test_three_flags(self):
        level, label = calculate_risk(3, False)
        self.assertIn("高风险", label)

    def test_high_weight_upgrade(self):
        # 1个高权重维度 → 从低风险升到中风险
        level, label = calculate_risk(0, True)
        self.assertIn("中风险", label)


class TestZhuolangEndToEnd(unittest.TestCase):
    """模拟案例端到端测试"""

    def test_all_8_detected(self):
        """8家隐性关联方全部触发 ≥1 维度"""
        results = {}
        for t in targets[:8]:  # 前8家
            name = t["name"]
            flags = {}
            flags["D01"] = check_D01_equity(audit, t)[0]
            flags["D03"] = check_D03_actual_controller(audit, t)[0]
            flags["D04"] = check_D04_executive_overlap(audit, t)[0]
            flags["D06"] = check_D06_legal_rep_trajectory(audit, t)[0]
            flags["D07"] = check_D07_same_address(audit, t)[0]
            flags["D10"] = check_D10_name_similarity(audit, t)[0]
            flags["D11"] = check_D11_insured_anomaly(t)[0]
            results[name] = sum(1 for v in flags.values() if v)

        # 跨企业维度
        d02 = check_D02_common_shareholders(targets)
        d05 = check_D05_legal_rep_cross(targets)
        d08 = check_D08_shared_contact(targets)
        for name in results:
            results[name] += sum([d02[name][0], d05[name][0], d08[name][0]])

        for name, count in results.items():
            self.assertGreater(count, 0, f"{name} 应至少触发1个维度，实际触发 {count}")

    def test_generic_clean(self):
        """无关企业12维度全✗"""
        t = target_map["通用企业股份有限公司"]
        flags = []
        flags.append(check_D01_equity(audit, t)[0])
        flags.append(check_D03_actual_controller(audit, t)[0])
        flags.append(check_D04_executive_overlap(audit, t)[0])
        flags.append(check_D06_legal_rep_trajectory(audit, t)[0])
        flags.append(check_D07_same_address(audit, t)[0])
        flags.append(check_D10_name_similarity(audit, t)[0])
        flags.append(check_D11_insured_anomaly(t)[0])

        d02 = check_D02_common_shareholders(targets)
        d05 = check_D05_legal_rep_cross(targets)
        d08 = check_D08_shared_contact(targets)
        flags.append(d02["通用企业股份有限公司"][0])
        flags.append(d05["通用企业股份有限公司"][0])
        flags.append(d08["通用企业股份有限公司"][0])

        total = sum(flags)
        self.assertEqual(total, 0, f"无关企业应全✗，实际触发 {total} 个维度: {flags}")

    def test_D08_shared_phone(self):
        """D08 应捕获电话共用（星海贸易 + 星辉科技共用一个号码 138****5678）"""
        d08 = check_D08_shared_contact(targets)
        self.assertTrue(d08["星海贸易有限公司"][0])
        self.assertTrue(d08["星辉科技有限公司"][0])

    def test_D06_captures_trajectory(self):
        """D06 应捕获法人变更轨迹（汇鑫信息前法人赵某=审计方监事）"""
        triggered, reason = check_D06_legal_rep_trajectory(audit, target_map["汇鑫信息技术有限公司"])
        self.assertTrue(triggered)
        self.assertIn("赵某", reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
