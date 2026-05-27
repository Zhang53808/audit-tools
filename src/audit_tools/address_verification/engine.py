"""函证地址核查 - 三层过滤主引擎。

从 address_verification.py 提取，使用 common 模块消除重复代码。
"""

import math
import os
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
from tqdm import tqdm

from audit_tools.common.address import clean_address, multi_strategy_similarity
from audit_tools.common.api import geocode
from audit_tools.common.logging import get_logger
from audit_tools.common.excel_output import write_dataframe_to_excel
from audit_tools.address_verification.search import search_and_evaluate
from audit_tools.address_verification.risk import calculate_risk_score, determine_verdict

logger = get_logger(__name__)

# 默认配置
DEFAULT_CONFIG = {
    "sim_high": 85,
    "sim_mid": 70,
    "dist_near": 1000,
    "dist_mid": 5000,
}


def haversine_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """Haversine 公式计算两点间直线距离（米）。"""
    lng1, lat1 = coord1
    lng2, lat2 = coord2
    R = 6371000

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = (math.sin(delta_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def check_geocode_distance(addr1: str, addr2: str, map_key: str):
    """调地图 API 算两个地址的直线距离。

    返回: (距离米数或None, 坐标1, 坐标2)
    """
    coord1 = geocode(addr1, map_key)
    coord2 = geocode(addr2, map_key)

    if coord1 is None or coord2 is None:
        return None, coord1, coord2

    distance = haversine_distance(coord1, coord2)
    return distance, coord1, coord2


def verify_addresses(
    input_file,
    output_file=None,
    skip_search=False,
    map_key="",
    llm_key="",
    llm_base_url="https://api.deepseek.com",
    llm_model="deepseek-chat",
    anysearch_cli="",
    config=None,
) -> Optional[pd.DataFrame]:
    """三层过滤主函数。

    Args:
        input_file: 输入 Excel 路径
        output_file: 输出 Excel 路径（默认：输入_核查结果.xlsx）
        skip_search: True 时跳过第2层搜索
        map_key: 腾讯地图 API Key
        llm_key: LLM API Key
        llm_base_url: LLM 服务地址
        llm_model: LLM 模型名称
        anysearch_cli: AnySearch CLI 路径
        config: 阈值配置 dict（可选，覆盖默认值）
    """
    if config is None:
        config = DEFAULT_CONFIG
    sim_high = config.get("sim_high", 85)
    sim_mid = config.get("sim_mid", 70)
    dist_near = config.get("dist_near", 1000)
    dist_mid = config.get("dist_mid", 5000)

    # 读入数据
    if str(input_file).endswith('.csv'):
        df = pd.read_csv(input_file)
    else:
        df = pd.read_excel(input_file)

    required_cols = ["公司名称", "发函地址", "工商注册地址"]
    col_map = {}
    for c in required_cols:
        if c in df.columns:
            col_map[c] = c
            continue
        for col in df.columns:
            if c in col:
                col_map[c] = col
                break

    if len(col_map) == len(required_cols):
        df = df.rename(columns={v: k for k, v in col_map.items()})
    else:
        missing = [c for c in required_cols if c not in col_map]
        logger.error("缺少列: %s", missing)
        logger.error("现有列: %s", list(df.columns))
        logger.error("请确保Excel包含：公司名称 | 发函地址 | 工商注册地址")
        return None

    df["公司名称"] = df["公司名称"].fillna("").astype(str)
    df["发函地址"] = df["发函地址"].fillna("").astype(str)
    df["工商注册地址"] = df["工商注册地址"].fillna("").astype(str)

    logger.info("读取到 %d 条记录，开始核查...", len(df))

    # 初始化结果列
    df["清洗后_发函"] = ""
    df["清洗后_工商"] = ""
    df["相似度(%)"] = 0.0
    df["匹配策略"] = ""
    df["距离(米)"] = ""
    df["搜索来源"] = ""
    df["搜索评估"] = ""
    df["风险评分"] = 0
    df["风险等级"] = ""
    df["判定理由"] = ""
    df["核查结论"] = ""

    total = len(df)
    stats = {"通过": 0, "需人工判断": 0, "异常": 0}

    for idx, row in tqdm(df.iterrows(), total=total, desc="核查进度", ncols=80):
        company = str(row["公司名称"])
        send_addr = str(row["发函地址"])
        reg_addr = str(row["工商注册地址"])

        if not company or company == "nan":
            continue

        # 清洗地址
        clean_send = clean_address(send_addr)
        clean_reg = clean_address(reg_addr)
        df.at[idx, "清洗后_发函"] = clean_send
        df.at[idx, "清洗后_工商"] = clean_reg

        # 第1层：多策略相似度
        sim_score, sim_strategy = multi_strategy_similarity(send_addr, reg_addr)
        df.at[idx, "相似度(%)"] = sim_score
        df.at[idx, "匹配策略"] = sim_strategy

        distance = None
        dist_passed_near = False
        dist_passed_mid = False
        search_result = None

        # 第1层判定：≥85% 直接通过
        if sim_score >= sim_high:
            df.at[idx, "距离(米)"] = "0"
            df.at[idx, "搜索来源"] = "无需搜索"
            df.at[idx, "搜索评估"] = "N/A"
            df.at[idx, "风险评分"] = 0
            df.at[idx, "风险等级"] = "低风险"
            df.at[idx, "判定理由"] = f"地址高度相似({sim_score}%, {sim_strategy})"
            df.at[idx, "核查结论"] = "通过"
            stats["通过"] += 1
            logger.debug("%s: 第1层通过 (相似度: %d%%, 策略: %s)", company, sim_score, sim_strategy)
            continue

        logger.debug("%s: 第1层未通过 (相似度: %d%%)", company, sim_score)

        # 第1.5层：地理距离
        if map_key:
            distance, coord1, coord2 = check_geocode_distance(send_addr, reg_addr, map_key)

        if distance is not None:
            df.at[idx, "距离(米)"] = round(distance)
            dist_passed_near = distance <= dist_near
            dist_passed_mid = distance <= dist_mid
        else:
            df.at[idx, "距离(米)"] = "API失败" if map_key else "未配置Key"

        # 第1.5层判定
        if dist_passed_near:
            df.at[idx, "搜索来源"] = "无需搜索"
            df.at[idx, "搜索评估"] = "N/A"
            score, level = calculate_risk_score(sim_score, distance, None, sim_mid, sim_high, dist_mid)
            df.at[idx, "风险评分"] = score
            df.at[idx, "风险等级"] = level
            verdict, reason = determine_verdict(
                sim_score, distance, True, True, None, level, sim_high, sim_mid
            )
            df.at[idx, "判定理由"] = reason
            df.at[idx, "核查结论"] = verdict
            stats[verdict] = stats.get(verdict, 0) + 1
            logger.debug("%s: 第1.5层通过 (距离: %dm)", company, round(distance))
            continue

        if dist_passed_mid and sim_score >= sim_mid:
            df.at[idx, "搜索来源"] = "跳过搜索"
            df.at[idx, "搜索评估"] = "N/A"
            score, level = calculate_risk_score(sim_score, distance, None, sim_mid, sim_high, dist_mid)
            df.at[idx, "风险评分"] = score
            df.at[idx, "风险等级"] = level
            df.at[idx, "判定理由"] = f"距离较近({round(distance)}m)但地址相似度偏低({sim_score}%)"
            df.at[idx, "核查结论"] = "需人工判断"
            stats["需人工判断"] += 1
            logger.debug("%s: 需人工判断 (距离: %dm, 相似度: %d%%)", company, round(distance), sim_score)
            continue

        # 第2层：搜索 + 评估
        if skip_search:
            score, level = calculate_risk_score(sim_score, distance, None, sim_mid, sim_high, dist_mid)
            df.at[idx, "搜索来源"] = "已跳过"
            df.at[idx, "搜索评估"] = "N/A"
            df.at[idx, "风险评分"] = score
            df.at[idx, "风险等级"] = level
            if sim_score >= sim_mid:
                df.at[idx, "核查结论"] = "需人工判断"
                df.at[idx, "判定理由"] = "跳过搜索，地址相似度中等，建议人工复核"
            else:
                df.at[idx, "核查结论"] = "异常"
                df.at[idx, "判定理由"] = "跳过搜索，地址相似度低且距离远"
            verdict = df.at[idx, "核查结论"]
            stats[verdict] = stats.get(verdict, 0) + 1
            logger.debug("%s: %s (搜索已跳过)", company, verdict)
            continue

        logger.debug("%s: 进入第2层搜索评估...", company)

        search_result = search_and_evaluate(
            company, send_addr,
            cli_path=anysearch_cli,
            api_key=llm_key,
            base_url=llm_base_url,
            model=llm_model,
        )
        df.at[idx, "搜索来源"] = search_result.get("mode", "fallback")
        df.at[idx, "搜索评估"] = search_result.get("reason", "")

        score, level = calculate_risk_score(sim_score, distance, search_result, sim_mid, sim_high, dist_mid)
        df.at[idx, "风险评分"] = score
        df.at[idx, "风险等级"] = level

        verdict, reason = determine_verdict(
            sim_score, distance, False, dist_passed_mid, search_result, level, sim_high, sim_mid
        )
        df.at[idx, "判定理由"] = reason
        df.at[idx, "核查结论"] = verdict
        stats[verdict] = stats.get(verdict, 0) + 1

        icon = {"通过": "✅", "需人工判断": "⚠️", "异常": "❌"}
        logger.info("  %s %s: %s", icon.get(verdict, "?"), company, reason)

    # 输出
    if output_file is None:
        input_path = Path(input_file)
        output_file = input_path.parent / f"{input_path.stem}_核查结果{input_path.suffix}"

    output_columns = [
        "公司名称", "发函地址", "工商注册地址",
        "清洗后_发函", "清洗后_工商",
        "相似度(%)", "匹配策略",
        "距离(米)",
        "搜索来源", "搜索评估",
        "风险评分", "风险等级",
        "判定理由", "核查结论",
    ]
    output_columns = [c for c in output_columns if c in df.columns]

    col_widths = {
        "公司名称": 22, "发函地址": 32, "工商注册地址": 32,
        "清洗后_发函": 28, "清洗后_工商": 28,
        "相似度(%)": 10, "匹配策略": 12,
        "距离(米)": 10,
        "搜索来源": 10, "搜索评估": 40,
        "风险评分": 8, "风险等级": 8,
        "判定理由": 45, "核查结论": 12,
    }

    write_dataframe_to_excel(
        df[output_columns],
        str(output_file),
        sheet_name="核查结果",
        col_widths=col_widths,
        conclusion_col="核查结论",
        risk_col="风险等级",
    )

    # 统计
    logger.info("=" * 55)
    logger.info("核查完成")
    logger.info("  总数: %d", total)
    logger.info("  ✅ 通过: %d 条 (可直接发函)", stats.get("通过", 0))
    logger.info("  ⚠️ 需人工判断: %d 条 (建议实习生优先查)", stats.get("需人工判断", 0))
    logger.info("  ❌ 异常: %d 条 (重点风险)", stats.get("异常", 0))
    logger.info("  报告已保存: %s", output_file)

    return df
