#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""固定资产折旧年审测算工具。

读取客户固定资产明细，按直线法或月折旧率重新测算本年折旧，
并与客户账面本年折旧额对比，输出差异明细。
"""

import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter


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
DATE_FORMATS = ["%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日", "%Y-%m", "%Y/%m", "%Y年%m月"]


def to_number(value, default=0.0):
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
        .replace("¥", "")
        .replace("￥", "")
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


def parse_date(value):
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


def cell(row, config, key, default=None):
    col = config.get(key)
    if col is None or col >= len(row):
        return default
    return row[col]


def find_header(ws):
    for row_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=15, values_only=True), 1):
        values = [str(value).strip() if value is not None else "" for value in row]
        text = " ".join(value for value in values if value)
        keywords = ["资产", "卡片", "原值", "折旧", "残值", "入账"]
        if sum(1 for keyword in keywords if keyword in text) >= 3:
            return row_idx, values
    return None, None


def auto_match(header_row):
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


def ask_int(prompt, default):
    raw = input(prompt).strip()
    return int(raw) if raw.isdigit() else default


def build_config(ws, config_path, customer_name):
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
    config["data_start"] = ask_int(f"数据从第几行开始？[默认 {data_start_default}]：", data_start_default)
    config["grouped"] = input("同一资产是否会按月份出现在多行？[y/N]：").strip().lower() == "y"
    config["audit_year"] = ask_int("审计年度 [默认 2025]：", 2025)

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


def row_to_asset(row, config):
    orig_value = to_number(cell(row, config, "orig_value"))
    residual = to_number(cell(row, config, "residual"))
    residual_rate = to_number(cell(row, config, "residual_rate"))
    if residual == 0 and residual_rate:
        residual = round(orig_value * residual_rate / 100, 2)

    return {
        "name": str(cell(row, config, "name", "") or "").strip(),
        "entry_date": cell(row, config, "entry_date"),
        "life": normalize_life(to_number(cell(row, config, "life"))),
        "used_life_min": normalize_life(to_number(cell(row, config, "used_life"))),
        "orig_value": orig_value,
        "residual": residual,
        "residual_rate": residual_rate,
        "monthly_rate": to_number(cell(row, config, "monthly_rate")),
        "total_monthly": to_number(cell(row, config, "monthly_depr")),
        "rows": 1,
        "disposed": to_number(cell(row, config, "orig_decrease")) > 0,
        "disposal_month": 0,
    }


def normalize_life(value):
    """客户表可能填年限，也可能填月数。小于等于 50 的值按年换算成月。"""
    if value <= 0:
        return 0
    return value * 12 if value <= 50 else value


def collect_items(ws, config):
    rows = list(ws.iter_rows(min_row=config["data_start"], values_only=True))
    if not config.get("grouped"):
        items = []
        for index, row in enumerate(rows, 1):
            card = str(cell(row, config, "card", index) or index).strip()
            name = str(cell(row, config, "name", "") or "").strip()
            if not card and not name:
                continue
            items.append((card, row_to_asset(row, config)))
        return items

    groups = defaultdict(
        lambda: {
            "name": "",
            "entry_date": None,
            "life": 0,
            "used_life_min": None,
            "orig_value": 0,
            "residual": 0,
            "residual_rate": 0,
            "monthly_rate": 0,
            "total_monthly": 0,
            "rows": 0,
            "disposed": False,
            "disposal_month": 0,
        }
    )

    for index, row in enumerate(rows, 1):
        card = str(cell(row, config, "card", index) or index).strip()
        name = str(cell(row, config, "name", "") or "").strip()
        if not card and not name:
            continue
        asset = row_to_asset(row, config)
        group = groups[card]
        group["name"] = asset["name"] or group["name"]
        group["entry_date"] = asset["entry_date"] or group["entry_date"]
        group["life"] = asset["life"] or group["life"]
        group["orig_value"] = asset["orig_value"] or group["orig_value"]
        group["residual"] = asset["residual"] or group["residual"]
        group["residual_rate"] = asset["residual_rate"] or group["residual_rate"]
        group["monthly_rate"] = asset["monthly_rate"] or group["monthly_rate"]
        group["total_monthly"] += asset["total_monthly"]
        group["rows"] += 1

        used = asset["used_life_min"]
        if used:
            if group["used_life_min"] is None or used < group["used_life_min"]:
                group["used_life_min"] = used

        if asset["disposed"]:
            group["disposed"] = True
            group["disposal_month"] = group["rows"]

    return sorted(groups.items(), key=lambda item: item[0])


def expected_months(acq_date, audit_year, life, used_life_min, disposed, disposal_month, has_disposal):
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


def calculate(items, config):
    audit_year = int(config["audit_year"])
    results = []
    skipped = {"zero_value": 0, "no_date": 0, "invalid_life": 0}
    match = 0
    mismatch = 0

    for card, asset in items:
        orig_value = asset["orig_value"]
        life = asset["life"]
        if orig_value == 0:
            skipped["zero_value"] += 1
            continue
        if life <= 0:
            skipped["invalid_life"] += 1
            continue

        acq_date = parse_date(asset["entry_date"])
        if acq_date is None:
            skipped["no_date"] += 1
            continue

        if config.get("method") == "rate" and asset.get("monthly_rate"):
            monthly_depr = round(orig_value * asset["monthly_rate"] / 100, 2)
        else:
            monthly_depr = round((orig_value - asset["residual"]) / life, 2)

        months, tag = expected_months(
            acq_date,
            audit_year,
            life,
            asset["used_life_min"],
            asset["disposed"],
            asset["disposal_month"],
            config.get("has_disposal"),
        )
        if tag == "未来年度入账":
            continue

        calc_total = round(monthly_depr * months, 2)
        customer_total = round(asset["total_monthly"], 2)
        diff = round(calc_total - customer_total, 2)
        result_status = "一致" if abs(diff) < 0.01 else "有差异"
        status = f"{tag},{result_status}" if tag else result_status

        if result_status == "一致":
            match += 1
        else:
            mismatch += 1

        customer_months = asset["rows"]
        month_status = "一致" if customer_months == months else f"应提{months}月，客户{customer_months}月"

        results.append(
            [
                card,
                asset["name"],
                acq_date.strftime("%Y-%m-%d"),
                orig_value,
                asset["residual"],
                int(life),
                int(asset["used_life_min"]) if asset["used_life_min"] else "",
                customer_months,
                months,
                monthly_depr,
                calc_total,
                customer_total,
                diff,
                status,
                month_status,
            ]
        )

    return results, match, mismatch, skipped


def write_results(path, results):
    out_path = path.with_name(f"{path.stem}_折旧年审结果.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "折旧测算"

    headers = [
        "卡片编码",
        "资产名称",
        "入账日期",
        "期初原值",
        "残值",
        "使用寿命(月)",
        "年初已提月数",
        "客户实际月数",
        "应提月数",
        "月折旧额",
        "测算年折旧额",
        "客户年折旧额(汇总)",
        "差异",
        "结论",
        "月数核对",
    ]
    ws.append(headers)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(results) + 1}"

    red_font = Font(color="FF0000")
    header_fill = PatternFill("solid", fgColor="D9EAF7")
    for cell_obj in ws[1]:
        cell_obj.font = Font(bold=True)
        cell_obj.fill = header_fill

    for row in results:
        ws.append(row)
        if "有差异" in str(row[13]):
            for cell_obj in ws[ws.max_row]:
                cell_obj.font = red_font

    diff_ws = wb.create_sheet(title="差异汇总")
    diff_ws.append(["卡片编码", "资产名称", "测算年折旧额", "客户年折旧额", "差异", "备注"])
    total_diff = 0
    for row in results:
        if "有差异" not in str(row[13]):
            continue
        diff_ws.append([row[0], row[1], row[10], row[11], row[12], row[13]])
        total_diff += abs(row[12] or 0)

    diff_ws.append([])
    diff_ws.append(["差异绝对值合计", "", "", "", round(total_diff, 2), ""])
    diff_ws.freeze_panes = "A2"

    for sheet in [ws, diff_ws]:
        for col_idx in range(1, sheet.max_column + 1):
            letter = get_column_letter(col_idx)
            max_len = max(len(str(sheet.cell(row=row_idx, column=col_idx).value or "")) for row_idx in range(1, sheet.max_row + 1))
            sheet.column_dimensions[letter].width = min(max(max_len + 2, 10), 30)

    wb.save(out_path)
    return out_path


def main():
    print("请把客户固定资产明细 Excel 拖进终端，然后回车：")
    path = Path(input().strip().strip("'\""))
    if not path.exists():
        raise SystemExit(f"找不到文件：{path}")

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active

    config_dir = Path(__file__).resolve().parent / "客户配置"
    customer_name = path.stem
    config_path = config_dir / f"{customer_name}.json"
    config = build_config(ws, config_path, customer_name)

    print(f"正在测算 {config['audit_year']} 年折旧...")
    items = collect_items(ws, config)
    results, match, mismatch, skipped = calculate(items, config)
    out_path = write_results(path, results)

    print(f"完成：{out_path}")
    print(f"共处理 {len(results)} 条资产。")
    print(f"一致：{match}；有差异：{mismatch}。")
    print(
        "跳过："
        f"原值为 0 {skipped['zero_value']} 条；"
        f"无有效日期 {skipped['no_date']} 条；"
        f"寿命异常 {skipped['invalid_life']} 条。"
    )


if __name__ == "__main__":
    main()
