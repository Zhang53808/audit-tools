"""风险评分与综合判定。

从 address_verification.py 提取，与 engine.py 解耦。
"""

from typing import Optional, Tuple


def calculate_risk_score(
    sim_score: float,
    distance: Optional[float],
    search_result: Optional[dict],
    sim_mid: float = 70,
    sim_high: float = 85,
    dist_mid: float = 5000,
) -> Tuple[int, str]:
    """综合地址相似度、距离、搜索结果打分。

    返回: (0-100分, "低风险"|"中风险"|"高风险")
    """
    score = 0

    # 地址相似度信号
    if sim_score < 60:
        score += 25
    elif sim_score < sim_mid:
        score += 15
    elif sim_score < sim_high:
        score += 5

    # 距离信号
    if distance is not None:
        if distance > 10000:
            score += 20
        elif distance > dist_mid:
            score += 10
    else:
        score += 5  # 无法获取距离，轻微惩罚

    # 搜索信号
    if search_result is not None:
        conclusion = search_result.get("conclusion", "")
        if conclusion == "no_evidence":
            score += 25
        elif conclusion == "suspicious":
            score += 15
        elif conclusion == "confirmed":
            score += 0
        else:
            score += 10
    else:
        score += 15

    score = min(score, 100)
    if score <= 25:
        level = "低风险"
    elif score <= 50:
        level = "中风险"
    else:
        level = "高风险"

    return score, level


def determine_verdict(
    sim_score: float,
    distance: Optional[float],
    dist_passed_near: bool,
    dist_passed_mid: bool,
    search_result: Optional[dict],
    risk_level: str,
    sim_high: float = 85,
    sim_mid: float = 70,
) -> Tuple[str, str]:
    """综合所有信号输出核查结论和判定理由。

    返回: (结论, 理由)
    结论: "通过" | "需人工判断" | "异常"
    """
    reasons = []

    # 第1层判定
    if sim_score >= sim_high:
        reasons.append(f"地址高度相似({sim_score}%)")
        return "通过", " | ".join(reasons)

    # 第1.5层判定
    if distance is not None:
        if dist_passed_near:
            reasons.append(f"距离极近({round(distance)}m)，地址相似度{sim_score}%")
            return "通过", " | ".join(reasons)
        elif dist_passed_mid:
            reasons.append(f"距离较近({round(distance)}m)但地址相似度偏低({sim_score}%)")
            if sim_score >= sim_mid:
                return "需人工判断", " | ".join(reasons)

    # 进入第2层判定
    if search_result is None:
        reasons.append("搜索评估不可用")
        if risk_level == "低风险":
            return "需人工判断", " | ".join(reasons)
        else:
            return "异常", " | ".join(reasons)

    conclusion = search_result.get("conclusion", "")
    search_reason = search_result.get("reason", "")

    if conclusion == "confirmed":
        reasons.append(f"搜索佐证通过: {search_reason}")
        return "通过", " | ".join(reasons)
    elif conclusion == "suspicious":
        reasons.append(f"搜索来源可疑: {search_reason}")
        return "需人工判断", " | ".join(reasons)
    elif conclusion == "no_evidence":
        reasons.append(f"无权威来源佐证: {search_reason}")
        if risk_level == "高风险" or sim_score < 60:
            return "异常", " | ".join(reasons)
        else:
            return "需人工判断", " | ".join(reasons)

    reasons.append(f"搜索结论不明: {conclusion}")
    return "需人工判断", " | ".join(reasons)
