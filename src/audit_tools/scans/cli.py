"""扫描件工具 - CLI 入口。"""

import click

from audit_tools.common.logging import setup_logging


@click.group()
def main():
    """扫描件工具 - 分组 / 重命名"""
    setup_logging()


@main.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False))
@click.option("--keyword", default="finger", help="分隔文件关键字")
@click.option("--mode", default="keyword", type=click.Choice(["keyword", "size", "none"]), help="分隔识别模式")
def group(folder, keyword, mode):
    """原始扫描件分组，生成 CSV 清单。"""
    from audit_tools.scans.process import process
    process(folder, keyword, mode)


@main.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False))
@click.option("--company", default="A公司", help="客户简称")
@click.option("--year", default="2025", help="年份")
@click.option("--keyword", default="finger", help="分隔文件关键字")
@click.option("--csv", "csv_file", default=None, help="CSV 清单路径（默认自动查找）")
@click.option("--dry-run", is_flag=True, help="仅预览，不实际重命名")
def rename(folder, company, year, keyword, csv_file, dry_run):
    """根据 CSV 清单重命名原始扫描件。"""
    from audit_tools.scans.rename import process
    process(folder, company, year, keyword, csv_file, dry_run)


if __name__ == "__main__":
    main()
