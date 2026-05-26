#!/usr/bin/env python3
"""
企查查导出数据 → 关联方识别引擎 适配脚本
======================================
将企查查多sheet格式解析为引擎期望的数据结构并运行。
"""

import sys
import pandas as pd

import os

# 自动定位脚本所在目录，无需硬编码路径
_TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _TOOL_DIR)
from related_party_check import run_check


def parse_qichacha(filepath: str, audit_name: str):
    """
    解析企查查多sheet导出Excel。
    返回: (审计方, [目标企业列表])
    """
    # === 1. 基本信息 ===
    df1 = pd.read_excel(filepath, sheet_name="基本信息（企业）", header=1)
    companies = {}
    for _, row in df1.iterrows():
        name = str(row["企业名称"])
        insured = 0
        try:
            insured = int(float(row.get("员工人数", 0)))
        except (ValueError, TypeError):
            pass
        companies[name] = {
            "name": name,
            "legal_rep": str(row.get("法定代表人", "")),
            "address": str(row.get("住所", "")),
            "email": str(row.get("邮箱", "")),
            "insured_employees": insured,
            "shareholders": [],
            "executives": [],
            "actual_controller": "",
            "historical_legal_reps": [],
            "change_dates": [],
            "transaction_amount": 0,
            "phone": "",
        }

    # === 2. 主要人员 ===
    df2 = pd.read_excel(filepath, sheet_name="主要人员关联方查询", header=1)
    for _, row in df2.iterrows():
        name = str(row.get("企业名称", ""))
        exec_name = str(row.get("名称", ""))
        exec_title = str(row.get("职务", ""))
        if name in companies and exec_name and exec_name != "nan":
            entry = f"{exec_name}({exec_title})" if exec_title and exec_title != "nan" else exec_name
            if entry not in companies[name]["executives"]:
                companies[name]["executives"].append(entry)

    # === 3. 工商股东 ===
    df3 = pd.read_excel(filepath, sheet_name="工商股东", header=1)
    for _, row in df3.iterrows():
        name = str(row.get("企业名称", ""))
        holder = str(row.get("股东名称", ""))
        if name in companies and holder and holder != "nan":
            companies[name]["shareholders"].append(holder)

    # === 分离 ===
    audit = companies.pop(audit_name, None)
    if audit is None:
        print(f"❌ 未找到被审计单位「{audit_name}」")
        print(f"   可用企业: {list(companies.keys())[:10]}...")
        sys.exit(1)

    return audit, list(companies.values())


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="企查查数据 → 关联方识别")
    parser.add_argument("filepath", help="企查查导出的Excel文件路径")
    parser.add_argument("audit_name", nargs="?", default="A司",
                        help="被审计单位名称（默认: A司）")
    parser.add_argument("-o", "--output", default=None, help="输出Excel路径")
    args = parser.parse_args()

    audit, targets = parse_qichacha(args.filepath, args.audit_name)

    output = args.output or f"{audit['name']}_关联方核查结果.xlsx"
    df = run_check(audit, targets, output_file=output)
