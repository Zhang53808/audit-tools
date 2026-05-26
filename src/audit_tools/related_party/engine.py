"""关联方识别 - 12维度交叉比对主引擎。

从 related_party_check.py 提取，使用 common 模块消除重复。
"""

import sys
from typing import Dict, List, Optional, Tuple

import pandas as pd

from audit_tools.common.logging import get_logger
from audit_tools.common.excel_output import write_dataframe_to_excel
from audit_tools.related_party.dimensions import (
    check_D01_equity,
    check_D02_common_shareholders,
    check_D03_actual_controller,
    check_D04_executive_overlap,
    check_D05_legal_rep_cross,
    check_D06_legal_rep_trajectory,
    check_D07_same_address,
    check_D08_shared_contact,
    check_D09_change_window,
    check_D10_name_similarity,
    check_D11_insured_anomaly,
    check_D12_supplement_personnel,
)

logger = get_logger(__name__)

DIM_LABELS = [
    "股权穿透", "共同股东", "实际控制人", "高管重叠",
    "法人交叉", "法人变更", "同址经营", "联系方式共用",
    "变更时间窗口", "名称相似", "参保异常", "人员关联",
]

DIM_KEYS = {
    "股权穿透": "D01", "共同股东": "D02", "实际控制人": "D03",
    "高管重叠": "D04", "法人交叉": "D05", "法人变更": "D06",
    "同址经营": "D07", "联系方式共用": "D08", "变更时间窗口": "D09",
    "名称相似": "D10", "参保异常": "D11", "人员关联": "D12",
}

HIGH_WEIGHT_DIMS = {"股权穿透", "实际控制人", "法人变更"}


def calculate_risk(flag_count: int, has_high_weight: bool) -> Tuple[str, str]:
    """映射到风险等级。

    基础规则:
      0     → 低风险
      1-2   → 中风险
      ≥3    → 高风险

    权重升级: D01/D03/D06 任一触发 → 升一档
    """
    if flag_count == 0:
        level = "低风险"
    elif flag_count <= 2:
        level = "中风险"
    else:
        level = "高风险"

    if has_high_weight and level == "低风险":
        level = "中风险"
    elif has_high_weight and level == "中风险":
        level = "高风险"

    icon = {"低风险": "🟢", "中风险": "🟡", "高风险": "🔴"}
    return level, f"{icon.get(level, '')} {level}"


def run_check(
    audit: dict,
    targets: List[dict],
    personnel_list: Optional[List[str]] = None,
    output_file: Optional[str] = None,
) -> pd.DataFrame:
    """跑 12 维度全量比对。

    Args:
        audit: 审计方数据
        targets: 客户/供应商列表
        personnel_list: 补充人员名单（用于 D12）
        output_file: 输出 Excel 路径

    Returns:
        结果 DataFrame
    """
    logger.info("被审计单位: %s", audit['name'])
    logger.info("待核查企业: %d 家", len(targets))

    # 逐条跑独立维度
    rows = []
    for t in targets:
        name = t["name"]
        flags = {}

        flags["股权穿透"] = check_D01_equity(audit, t)
        flags["实际控制人"] = check_D03_actual_controller(audit, t)
        flags["高管重叠"] = check_D04_executive_overlap(audit, t)
        flags["法人变更"] = check_D06_legal_rep_trajectory(audit, t)
        flags["同址经营"] = check_D07_same_address(audit, t)
        flags["变更时间窗口"] = check_D09_change_window(audit, t)
        flags["名称相似"] = check_D10_name_similarity(audit, t)
        flags["参保异常"] = check_D11_insured_anomaly(t)
        flags["人员关联"] = check_D12_supplement_personnel(t, personnel_list)

        rows.append({"name": name, "_target": t, "_flags": flags})

    # 跨企业维度
    d02_results = check_D02_common_shareholders(targets)
    d05_results = check_D05_legal_rep_cross(targets)
    d08_results = check_D08_shared_contact(targets)

    for row in rows:
        name = row["name"]
        row["_flags"]["共同股东"] = d02_results.get(name, (False, ""))
        row["_flags"]["法人交叉"] = d05_results.get(name, (False, ""))
        row["_flags"]["联系方式共用"] = d08_results.get(name, (False, ""))

    # 汇总 + 风险评分
    data = []
    for row in rows:
        name = row["name"]
        t = row["_target"]
        flags = row["_flags"]

        # 数据可用性
        data_available = {}
        data_available["股权穿透"] = bool(t.get("shareholders")) and bool(audit.get("shareholders"))
        data_available["共同股东"] = bool(t.get("shareholders"))
        data_available["实际控制人"] = bool(t.get("actual_controller")) and bool(audit.get("actual_controller"))
        data_available["高管重叠"] = bool(t.get("executives")) and bool(audit.get("executives"))
        data_available["法人交叉"] = bool(t.get("legal_rep"))
        data_available["法人变更"] = bool(t.get("historical_legal_reps")) and bool(audit.get("executives"))
        data_available["同址经营"] = bool(t.get("address")) and bool(audit.get("address"))
        data_available["联系方式共用"] = bool(t.get("phone")) or bool(t.get("email"))
        data_available["变更时间窗口"] = bool(t.get("change_dates"))
        data_available["名称相似"] = True
        data_available["参保异常"] = "insured_employees" in t and "transaction_amount" in t
        data_available["人员关联"] = bool(personnel_list)

        flag_count = 0
        for dim_cn in DIM_LABELS:
            triggered = flags.get(dim_cn, (False,))[0]
            if triggered and data_available.get(dim_cn, False):
                flag_count += 1

        has_high = any(
            flags.get(d, (False,))[0] and data_available.get(d, False)
            for d in HIGH_WEIGHT_DIMS
        )
        risk_level, risk_label = calculate_risk(flag_count, has_high)

        record = {"企业名称": name}
        for dim_cn in DIM_LABELS:
            triggered, evidence = flags.get(dim_cn, (False, ""))
            if not data_available.get(dim_cn, False):
                record[dim_cn] = "—"
            elif triggered:
                record[dim_cn] = evidence
            else:
                record[dim_cn] = "✗"
        record["异常维度数"] = flag_count
        record["风险等级"] = risk_label
        data.append(record)

        icon = "🔴" if risk_level == "高风险" else ("🟡" if risk_level == "中风险" else "🟢")
        triggered_dims = [
            dim_cn for dim_cn in DIM_LABELS
            if flags.get(dim_cn, (False,))[0] and data_available.get(dim_cn, False)
        ]
        dims_str = ", ".join(triggered_dims) if triggered_dims else "无"
        logger.info("  %s %s: %s", icon, name, dims_str)

    df = pd.DataFrame(data)

    # 统计
    stats = df["风险等级"].apply(lambda x: x.split()[-1]).value_counts()
    logger.info("=" * 50)
    logger.info("核查完成")
    logger.info("  总数: %d", len(targets))
    logger.info("  🟢 低风险: %d", stats.get("低风险", 0))
    logger.info("  🟡 中风险: %d", stats.get("中风险", 0))
    logger.info("  🔴 高风险: %d", stats.get("高风险", 0))

    partial_dims = [
        dim_cn for dim_cn in DIM_LABELS
        if any(row[dim_cn] == "—" for row in data)
    ]
    if partial_dims:
        logger.info("以下维度数据不全，标注为「—」：")
        for d in partial_dims:
            missing = sum(1 for row in data if row[d] == "—")
            logger.info("   %s: %d/%d 家企业缺数据", d, missing, len(targets))

    # 输出 Excel
    if output_file is None:
        output_file = "关联方核查结果.xlsx"

    col_widths = {"企业名称": 28}
    for d in DIM_LABELS:
        col_widths[d] = 32
    col_widths["异常维度数"] = 10
    col_widths["风险等级"] = 14

    write_dataframe_to_excel(
        df,
        output_file,
        sheet_name="关联方核查",
        col_widths=col_widths,
        risk_col="风险等级",
        triggered_cols=DIM_LABELS,
    )

    logger.info("  报告已保存: %s", output_file)
    return df
