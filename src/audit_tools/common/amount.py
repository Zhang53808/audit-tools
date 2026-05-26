"""金额清洗与日期解析。

合并自 clean_vouchers.py 的 clean_amount() 和 depreciation_check.py 的 to_number() + parse_date()。
"""

from datetime import datetime
from typing import Optional, Union


DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日",
    "%Y-%m", "%Y/%m", "%Y年%m月",
]


def clean_amount(value) -> float:
    """清洗金额：去掉货币符号、逗号、空格和括号负数。

    适用场景：凭证明细 Excel 清洗。
    """
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    negative = text.startswith("(") and text.endswith(")")
    text = (
        text.replace("\uffe5", "")   # ￥
        .replace("\u00a5", "")       # ¥
        .replace(",", "")
        .replace(" ", "")
        .replace("(", "")
        .replace(")", "")
    )

    try:
        amount = float(text)
    except ValueError:
        return 0.0

    return -amount if negative else amount


def to_number(value, default: float = 0.0) -> float:
    """更健壮的金额解析（折旧测算用）。

    额外处理：
      - 百分号去除（残值率字段可能含 %）
      - 括号负数: (1,234.56) -> -1234.56
      - None / 空字符串 -> default
    """
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return default
    negative = text.startswith("(") and text.endswith(")")
    text = (
        text.replace(",", "")
        .replace("\uffe5", "")
        .replace("\u00a5", "")
        .replace("%", "")
        .replace("(", "")
        .replace(")", "")
        .strip()
    )
    try:
        number = float(text)
    except ValueError:
        return default
    return -number if negative else number


def parse_date(value) -> Optional[datetime]:
    """解析多种中文日期格式。

    支持:
      - datetime 对象（直接返回）
      - Excel 日期单元格
      - str: 2025-03-15 / 2025/03/15 / 2025年03月15日
      - str: 2025-03 / 2025/03 / 2025年03月（缺省日为1号）
    """
    if isinstance(value, datetime):
        return value
    if value is None:
        return None
    if hasattr(value, "year") and hasattr(value, "month"):
        return datetime(value.year, value.month, getattr(value, "day", 1))

    text = str(value).strip()
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None
