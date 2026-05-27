"""折旧测算辅助函数。

从 depreciation_check.py 提取。
"""

from datetime import datetime


def normalize_life(value: float) -> float:
    """客户表可能填年限，也可能填月数。≤50 的值按年换算成月。"""
    if value <= 0:
        return 0
    return value * 12 if value <= 50 else value


def expected_months(acq_date, audit_year, life, used_life_min, disposed, disposal_month, has_disposal):
    """计算审计年度内应计提折旧的月数。

    Returns:
        (months, tag)
        tag: "" | "已提足" | "未来年度入账" | "有处置"
    """
    remaining_at_start = life - (used_life_min - 1) if used_life_min and used_life_min > 0 else life
    if remaining_at_start <= 0:
        return 0, "已提足"

    if acq_date.year < audit_year:
        months = 12
    elif acq_date.year == audit_year:
        months = max(0, 12 - acq_date.month)
    else:
        return 0, "未来年度入账"

    months = min(months, int(remaining_at_start))
    tag = ""
    if has_disposal and disposed:
        if disposal_month and disposal_month < months:
            months = disposal_month
        else:
            tag = "有处置"
    return months, tag
