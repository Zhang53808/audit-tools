"""凭证工具 - CLI 入口。"""

import click

from audit_tools.common.logging import setup_logging


@click.group()
def main():
    """凭证工具 - 清洗 / 重命名"""
    setup_logging()


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="输出路径")
def clean(input_file, output):
    """清洗凭证明细 Excel。"""
    from audit_tools.vouchers.clean import process
    process(input_file, output)


@main.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False))
@click.option("--company", default="A公司", help="客户简称")
@click.option("--year", default="2025", help="年份")
@click.option("--dry-run", is_flag=True, help="仅预览，不实际重命名")
def rename(folder, company, year, dry_run):
    """凭证 PDF 批量重命名。"""
    from audit_tools.vouchers.rename import process
    process(folder, company, year, dry_run)


if __name__ == "__main__":
    main()
