"""折旧表头识别与配置构建。

支持交互和非交互两种模式。
"""

import json
from pathlib import Path

from audit_tools.common.logging import get_logger

logger = get_logger(__name__)

AUTO_MAP = {
    "card": ["卡片编码", "卡片编号", "资产编码", "资产编号", "固定资产编码"],
    "name": ["资产名称", "固定资产名称", "设备名称", "名称"],
    "entry_date": ["入账日期", "入账日", "启用日期", "开始使用日期", "购入日期"],
    "life": ["使用寿命", "使用年限", "折旧年限", "折旧期限", "预计使用月数", "预计使用年限"],
    "used_life": ["已使用寿命", "已使用月数", "已提月数", "已使用年限", "累计已提月数"],
    "residual": ["残值", "预计净残值", "净残值", "残值额"],
    "residual_rate": ["残值率", "净残值率", "预计净残值率"],
    "orig_value": ["期初原值", "原值", "资产原值", "固定资产原值", "原值(期初)", "原值期初"],
    "monthly_depr": ["本期折旧额", "月折旧额", "本期折旧", "当月折旧", "本年累计折旧额"],
    "monthly_rate": ["月折旧率"],
    "orig_decrease": ["原值减少", "原值调出", "本期减少原值", "减少原值"],
}

REQUIRED_FIELDS = ["orig_value", "life", "entry_date"]


def find_header(ws):
    """在 work sheet 中定位表头行。"""
    for row_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=15, values_only=True), 1):
        values = [str(value).strip() if value is not None else "" for value in row]
        text = " ".join(value for value in values if value)
        keywords = ["资产", "卡片", "原值", "折旧", "残值", "入账"]
        if sum(1 for keyword in keywords if keyword in text) >= 3:
            return row_idx, values
    return None, None


def auto_match(header_row):
    """自动匹配表头到字段。"""
    config = {}
    unmatched = []
    for field, keywords in AUTO_MAP.items():
        for col, header in enumerate(header_row):
            if header and any(keyword in header for keyword in keywords):
                config[field] = col
                break
        else:
            unmatched.append(field)
    return config, unmatched


def build_config(ws, config_path, customer_name):
    """交互式构建配置（原始工作流）。"""
    if config_path.exists():
        use_saved = input(f"发现已保存配置 {config_path.name}，直接使用？[y/N]：").strip().lower()
        if use_saved == "y":
            with config_path.open("r", encoding="utf-8") as file:
                return json.load(file)

    header_row_idx, header_row = find_header(ws)
    if header_row is None:
        raise SystemExit("找不到表头行，请确认文件格式。")

    print(f"识别到表头在第 {header_row_idx} 行，共 {len(header_row)} 列：")
    for col, header in enumerate(header_row):
        if header:
            print(f"  {col}: {header}")

    config, unmatched = auto_match(header_row)
    print("\n自动匹配结果：")
    for field, col in sorted(config.items(), key=lambda item: item[1]):
        print(f"  {field} -> 第 {col} 列（{header_row[col]}）")

    optional_fields = {"card", "name", "used_life", "residual", "residual_rate", "monthly_depr", "monthly_rate", "orig_decrease"}
    for field in unmatched:
        is_required = field in REQUIRED_FIELDS
        if not is_required and field in optional_fields:
            continue
        raw = input(f"{field} 未匹配到。请输入列号（0 开始，直接回车跳过）：").strip()
        if raw.isdigit():
            config[field] = int(raw)

    missing_required = [field for field in REQUIRED_FIELDS if field not in config]
    if missing_required:
        raise SystemExit(f"缺少必要字段：{', '.join(missing_required)}")

    data_start_default = header_row_idx + 1
    config["data_start"] = _ask_int(f"数据从第几行开始？[默认 {data_start_default}]：", data_start_default)
    config["grouped"] = input("同一资产是否会按月份出现在多行？[y/N]：").strip().lower() == "y"
    config["audit_year"] = _ask_int("审计年度 [默认 2025]：", 2025)

    print("折旧方法：1 - 直线法；2 - 按月折旧率")
    config["method"] = "rate" if input("请选择 1/2 [默认 1]：").strip() == "2" else "straight"
    config["has_disposal"] = input("本年度是否有资产处置/报废？[y/N]：").strip().lower() == "y"

    save = input("保存配置，便于下次直接使用？[y/N]：").strip().lower() == "y"
    if save:
        config_path.parent.mkdir(exist_ok=True)
        with config_path.open("w", encoding="utf-8") as file:
            json.dump(config, file, ensure_ascii=False, indent=2)
        print(f"已保存配置：{config_path}")

    return config


def build_config_from_args(
    ws,
    audit_year=2025,
    method="straight",
    grouped=False,
    has_disposal=False,
    data_start=None,
    header_row_idx=None,
    config_path=None,
):
    """非交互式构建配置（CLI 参数传入）。"""
    if header_row_idx is None:
        header_row_idx_detected, header_row = find_header(ws)
        if header_row_idx_detected is None:
            raise SystemExit("找不到表头行，请确认文件格式。")
    else:
        header_row_idx_detected = header_row_idx
        _, header_row = find_header(ws)  # still need header values
        if header_row is None:
            # reconstruct header from specified row
            header_row = [str(v).strip() if v is not None else "" for v in next(
                ws.iter_rows(min_row=header_row_idx, max_row=header_row_idx, values_only=True)
            )]

    config, unmatched = auto_match(header_row)
    logger.info("自动匹配结果：")
    for field, col in sorted(config.items(), key=lambda item: item[1]):
        logger.info("  %s -> 第 %d 列（%s）", field, col, header_row[col])

    for field in unmatched:
        if field in REQUIRED_FIELDS:
            raise SystemExit(f"必要字段 {field} 未匹配到，请检查表头。")

    missing_required = [field for field in REQUIRED_FIELDS if field not in config]
    if missing_required:
        raise SystemExit(f"缺少必要字段：{', '.join(missing_required)}")

    config["data_start"] = data_start or (header_row_idx_detected + 1)
    config["grouped"] = grouped
    config["audit_year"] = audit_year
    config["method"] = method
    config["has_disposal"] = has_disposal

    # 保存配置（如果指定了路径）
    if config_path:
        config_path = Path(config_path)
        config_path.parent.mkdir(exist_ok=True)
        with config_path.open("w", encoding="utf-8") as file:
            json.dump(config, file, ensure_ascii=False, indent=2)
        logger.info("已保存配置：%s", config_path)

    return config


def _ask_int(prompt, default):
    raw = input(prompt).strip()
    return int(raw) if raw.isdigit() else default
