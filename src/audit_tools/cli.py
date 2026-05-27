"""审计自动化工具包 - 统一 CLI 入口。

用法:
    audit-tools address-verify INPUT [--map-key KEY] [--llm-key KEY]
    audit-tools related-party [INPUT] [-o OUTPUT]
    audit-tools depreciation [INPUT] [--year YEAR] [--method straight|rate]
    audit-tools vouchers clean INPUT
    audit-tools vouchers rename FOLDER [--dry-run]
    audit-tools scans group FOLDER
    audit-tools scans rename FOLDER [--dry-run]
"""

import click

from audit_tools.common.logging import setup_logging


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="详细日志")
@click.pass_context
def main(ctx, verbose):
    """审计自动化工具包 - 函证/关联方/折旧/凭证/扫描件

    一套面向审计师的生产力工具，包含函证地址核查、关联方识别、
    固定资产折旧测算、凭证明细清洗和扫描件管理。
    """
    ctx.ensure_object(dict)
    setup_logging(level="DEBUG" if verbose else "INFO")


# ---- 函证地址核查 ----
@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="输出 Excel 路径")
@click.option("--map-key", default=None, help="腾讯地图 API Key")
@click.option("--llm-key", default=None, help="LLM API Key (DeepSeek/OpenAI 兼容)")
@click.option("--llm-model", default=None, help="LLM 模型名称")
@click.option("--no-search", is_flag=True, help="跳过第2层搜索")
@click.pass_context
def address_verify(ctx, input_file, output, map_key, llm_key, llm_model, no_search):
    """函证地址核查 - 三层过滤异常初筛器。

    INPUT_FILE: 含「公司名称」「发函地址」「工商注册地址」的 Excel。
    """
    import os
    from audit_tools.address_verification.engine import verify_addresses

    map_key = map_key or os.getenv("TENCENT_MAP_KEY", "")
    llm_key = llm_key or os.getenv("DEEPSEEK_API_KEY", "")

    verify_addresses(
        input_file,
        output_file=output,
        skip_search=no_search,
        map_key=map_key,
        llm_key=llm_key,
        llm_model=llm_model or os.getenv("LLM_MODEL", "deepseek-chat"),
    )


# ---- 关联方识别 ----
@main.command()
@click.argument("input_file", required=False, type=click.Path(exists=True))
@click.option("-o", "--output", default="关联方核查结果.xlsx", help="输出 Excel 路径")
@click.option("--audit-file", default=None, type=click.Path(exists=True), help="审计方数据 Excel")
@click.option("--personnel-file", default=None, type=click.Path(exists=True), help="补充人员名单 Excel")
@click.pass_context
def related_party(ctx, input_file, output, audit_file, personnel_file):
    """关联方识别 - 12维度交叉比对。

    INPUT_FILE: 含「企业名称」「股东」「高管」等列的 Excel。
    不提供则使用内置模拟数据演示。
    """
    from audit_tools.related_party.cli import load_targets_from_excel
    from audit_tools.related_party.fixture import build_fixture
    from audit_tools.related_party.engine import run_check
    from audit_tools.common.logging import get_logger
    import pandas as pd
    import sys

    logger = get_logger(__name__)

    audit = None
    if audit_file:
        entries = load_targets_from_excel(audit_file)
        if entries:
            audit = entries[0]

    personnel = None
    if personnel_file:
        pdf = pd.read_excel(personnel_file)
        for nc in ["姓名", "name", "名称", "人员"]:
            if nc in pdf.columns:
                personnel = pdf[nc].dropna().astype(str).tolist()
                break

    if input_file:
        targets = load_targets_from_excel(input_file)
    else:
        if audit is None:
            audit, targets = build_fixture()
        else:
            _, targets = build_fixture()

    if not targets:
        logger.error("未找到任何待核查企业")
        sys.exit(1)

    run_check(audit, targets, personnel, output_file=output)


# ---- 折旧测算 ----
@main.command()
@click.argument("input_file", required=False, type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="输出路径")
@click.option("--config", "config_file", default=None, help="配置 JSON 路径")
@click.option("--year", type=int, default=2025, help="审计年度")
@click.option("--method", type=click.Choice(["straight", "rate"]), default="straight", help="折旧方法")
@click.option("--grouped", is_flag=True, help="同一资产多行出现")
@click.option("--has-disposal", is_flag=True, help="有资产处置/报废")
@click.option("--data-start", type=int, default=None, help="数据起始行")
@click.option("--header-row", type=int, default=None, help="表头行号")
@click.pass_context
def depreciation(ctx, input_file, output, config_file, year, method, grouped, has_disposal, data_start, header_row):
    """固定资产折旧年审测算。

    INPUT_FILE: 客户固定资产明细 Excel。不提供则进入交互模式。
    """
    from audit_tools.depreciation.engine import run_interactive, run_non_interactive

    if input_file is None:
        run_interactive()
    else:
        run_non_interactive(
            input_file=input_file,
            output_file=output,
            config_file=config_file,
            audit_year=year,
            method=method,
            grouped=grouped,
            has_disposal=has_disposal,
            data_start=data_start,
            header_row=header_row,
        )


# ---- 凭证工具 ----
@main.group()
def vouchers():
    """凭证工具 - 清洗 / 重命名"""
    pass


@vouchers.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="输出路径")
def clean(input_file, output):
    """清洗凭证明细 Excel。"""
    from audit_tools.vouchers.clean import process
    process(input_file, output)


@vouchers.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False))
@click.option("--company", default="A公司", help="客户简称")
@click.option("--year", default="2025", help="年份")
@click.option("--dry-run", is_flag=True, help="仅预览")
def rename(folder, company, year, dry_run):
    """凭证 PDF 批量重命名。"""
    from audit_tools.vouchers.rename import process
    process(folder, company, year, dry_run)


# ---- 扫描件工具 ----
@main.group()
def scans():
    """扫描件工具 - 分组 / 重命名"""
    pass


@scans.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False))
@click.option("--keyword", default="finger", help="分隔关键字")
@click.option("--mode", default="keyword", type=click.Choice(["keyword", "size", "none"]))
def group(folder, keyword, mode):
    """生成扫描件分组清单 CSV。"""
    from audit_tools.scans.process import process
    process(folder, keyword, mode)


@scans.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False))
@click.option("--company", default="A公司", help="客户简称")
@click.option("--year", default="2025", help="年份")
@click.option("--keyword", default="finger", help="分隔关键字")
@click.option("--csv", "csv_file", default=None, help="CSV 路径")
@click.option("--dry-run", is_flag=True, help="仅预览")
def scan_rename(folder, company, year, keyword, csv_file, dry_run):
    """根据 CSV 清单重命名扫描件。"""
    from audit_tools.scans.rename import process
    process(folder, company, year, keyword, csv_file, dry_run)


if __name__ == "__main__":
    main()
