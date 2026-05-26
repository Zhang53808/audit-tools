"""地址清洗与相似度计算。

从 address_verification.py 提取，消除与 related_party_check.py 的代码重复。
"""

import re
from typing import Tuple

from thefuzz import fuzz


def clean_address(addr: str) -> str:
    """清洗地址：去行政前缀、统一标点、去空白、统一常见缩写。

    目标：让"山东省济南市工业南路89号"和"济南市工业南路89号"
          在清洗后都变成"济南工业南路89号"，提升文本匹配准确率。
    """
    if not isinstance(addr, str) or not addr.strip():
        return ""

    result = addr.strip()

    # 1. 统一全角标点为半角
    result = result.replace("（", "(").replace("）", ")")
    result = result.replace("，", ",").replace("。", ".")
    result = result.replace("；", ";").replace("：", ":")
    result = result.replace("－", "-").replace("—", "-")
    result = result.replace("'", "'").replace("'", "'")
    result = result.replace("\u201c", '"').replace("\u201d", '"')

    # 2. 去除多余空白
    result = re.sub(r'\s+', '', result)

    # 3. 去除省/自治区前缀
    result = re.sub(
        r'^(北京市|天津市|上海市|重庆市|'
        r'河北省|山西省|辽宁省|吉林省|黑龙江省|'
        r'江苏省|浙江省|安徽省|福建省|江西省|山东省|'
        r'河南省|湖北省|湖南省|广东省|海南省|'
        r'四川省|贵州省|云南省|陕西省|甘肃省|青海省|'
        r'台湾省|'
        r'内蒙古自治区|广西壮族自治区|西藏自治区|宁夏回族自治区|新疆维吾尔自治区|'
        r'香港特别行政区|澳门特别行政区)',
        '', result
    )

    # 4. 统一常见缩写
    abbreviations = {
        "高新技术产业开发区": "高新区",
        "经济技术开发区": "开发区",
        "化学工业区": "化工区",
        "保税港区": "保税区",
        "出口加工区": "出口加工区",
    }
    for full, abbr in abbreviations.items():
        result = result.replace(full, abbr)

    # 5. 去除连续的"市/区/县/州/盟/旗"层级前缀
    prev = None
    while prev != result:
        prev = result
        result = re.sub(
            r'^([\u4e00-\u9fff]{2,6}(?:市|区|县|州|盟|旗|自治州|自治县|自治旗))',
            '', result
        )

    return result


def multi_strategy_similarity(addr1: str, addr2: str) -> Tuple[float, str]:
    """用三种策略计算地址相似度，取最高分。

    策略:
      - ratio:           全字符串编辑距离（精确但敏感）
      - token_sort_ratio: 分词后排序再比较（容忍词序差异）
      - partial_ratio:    子串匹配（容忍地址冗余前缀）

    返回: (最高分数, 策略名称)
    """
    s1 = clean_address(addr1)
    s2 = clean_address(addr2)

    if not s1 or not s2:
        return 0.0, "ratio"

    strategies = [
        ("ratio", fuzz.ratio(s1, s2)),
        ("token_sort", fuzz.token_sort_ratio(s1, s2)),
        ("partial", fuzz.partial_ratio(s1, s2)),
    ]

    best_name, best_score = max(strategies, key=lambda x: x[1])
    return float(best_score), best_name
