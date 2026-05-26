"""关联方识别 - CLI 入口。"""

import re
import sys

import click
import pandas as pd

from audit_tools.common.logging import setup_logging, get_logger
from audit_tools.related_party.fixture import build_fixture

logger = get_logger(__name__)


def load_targets_from_excel(filepath: str) -> list:
    """从 Excel 加载目标企业。"""
    df = pd.read_excel(filepath)

    col_map = {
        "name": ["企业名称", "公司名称", "name", "名称"],
        "shareholders": ["股东", "股东信息", "shareholders"],
        "actual_controller": ["实际控制人", "最终受益人", "actual_controller"],
        "executives": ["高管", "关键管理人员", "executives"],
        "legal_rep": ["法定代表人", "法人", "legal_rep"],
        "address": ["注册地址", "地址", "address"],
        "phone": ["电话", "联系电话", "phone"],
        "email": ["邮箱", "email"],
        "insured_employees": ["参保人数", "insured_employees"],
        "transaction_amount": ["交易金额", "transaction_amount"],
        "historical_legal_reps": ["历史法人", "historical_legal_reps"],
    }

    targets = []
    for _, row in df.iterrows():
        t = {}
        for key, candidates in col_map.items():
            for c in candidates:
                if c in df.columns:
                    val = row[c]
                    if pd.notna(val):
                        if key in ("shareholders", "executives", "historical_legal_reps"):
                            raw = str(val)
                            t[key] = [x.strip() for x in re.split(r'[;\n]', raw) if x.strip()]
                        elif key in ("insured_employees", "transaction_amount"):
                            t[key] = int(float(val))
                        else:
                            t[key] = str(val)
                    break
        if not t.get("name"):
            continue
        targets.append(t)

    return targets


@click.command()
@click.argument("input_file", required=False, type=click.Path(exists=True))
@click.option("-o", "--output", default="关联方核查结果.xlsx", help="输出 Excel 路径")
@click.option("--audit-file", default=None, type=click.Path(exists=True), help="审计方数据 Excel")
@click.option("--personnel-file", default=None, type=click.Path(exists=True), help="补充人员名单 Excel")
@click.option("--verbose", "-v", is_flag=True, help="详细日志")
def main(input_file, output, audit_file, personnel_file, verbose):
    """关联方识别 - 12维度交叉比对引擎。

    INPUT_FILE: 含「企业名称」「股东」「实际控制人」「高管」等列的 Excel。
    不提供则使用内置模拟数据演示。
    """
    setup_logging(level="DEBUG" if verbose else "INFO")

    from audit_tools.related_party.engine import run_check

    # 加载审计方数据
    audit = None
    if audit_file:
        entries = load_targets_from_excel(audit_file)
        if entries:
            audit = entries[0]
            logger.info("审计方: %s (从文件加载)", audit['name'])

    # 加载补充人员
    personnel = None
    if personnel_file:
        pdf = pd.read_excel(personnel_file)
        name_cols = ["姓名", "name", "名称", "人员"]
        for nc in name_cols:
            if nc in pdf.columns:
                personnel = pdf[nc].dropna().astype(str).tolist()
                break
        logger.info("补充人员名单: %d 人", len(personnel) if personnel else 0)

    # 加载目标企业
    if input_file:
        targets = load_targets_from_excel(input_file)
        logger.info("从文件加载 %d 家企业", len(targets))
    else:
        if audit is None:
            audit, targets = build_fixture()
            logger.info("使用内置模拟数据（模拟案例）")
        else:
            _, targets = build_fixture()
            logger.info("使用内置模拟数据（模拟案例）")

    if not targets:
        logger.error("未找到任何待核查企业，退出。")
        sys.exit(1)

    df = run_check(audit, targets, personnel, output_file=output)


if __name__ == "__main__":
    main()
