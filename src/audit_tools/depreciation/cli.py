"""固定资产折旧测算 - CLI 入口。

支持交互和非交互两种模式：
  - 不传参数：进入交互模式（原始工作流）
  - 传 input_file：非交互模式（适合批量/CI）
"""

import click

from audit_tools.common.logging import setup_logging, get_logger

logger = get_logger(__name__)


@click.command()
@click.argument("input_file", required=False, type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="输出 Excel 路径")
@click.option("--config", "config_file", default=None, help="已保存的配置 JSON 路径")
@click.option("--year", type=int, default=2025, help="审计年度")
@click.option("--method", type=click.Choice(["straight", "rate"]), default="straight", help="折旧方法")
@click.option("--grouped", is_flag=True, help="同一资产按月份出现在多行")
@click.option("--has-disposal", is_flag=True, help="本年度有资产处置/报废")
@click.option("--data-start", type=int, default=None, help="数据起始行号")
@click.option("--header-row", type=int, default=None, help="表头行号")
@click.option("--verbose", "-v", is_flag=True, help="详细日志")
def main(input_file, output, config_file, year, method, grouped, has_disposal, data_start, header_row, verbose):
    """固定资产折旧年审测算。

    支持直线法和月折旧率法。自动识别客户折旧表表头。

    INPUT_FILE: 客户固定资产明细 Excel。
    不提供则进入交互模式。
    """
    setup_logging(level="DEBUG" if verbose else "INFO")

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


if __name__ == "__main__":
    main()
