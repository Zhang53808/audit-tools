"""凭证 PDF 批量重命名。

从文件名识别月份/凭证号，统一命名格式：客户简称+年月日+凭证字+凭证号.pdf
"""

import csv
import os
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from audit_tools.common.text import sanitize_filename, unique_path
from audit_tools.common.logging import get_logger

logger = get_logger(__name__)


VOUCHER_TYPES = "记转银现收付"


def parse_filename(filename: str) -> dict:
    """从文件名中提取月份、日期、凭证字、凭证号和摘要。"""
    base = Path(filename).stem.strip()
    result = {"month": "", "day": "", "type": "", "num": "", "subject": ""}

    patterns = [
        r"^(?P<month>\d{1,2})月(?P<day>\d{1,2})日?\s*(?P<type>[记转银现收付])?-?(?P<num>\d{1,5})\s*(?P<subject>.*)$",
        r"^(?P<month>\d{1,2})-(?P<num>\d{1,5})\s*(?P<subject>.*)$",
        r"^(?P<month>\d{1,2})月(?P<num>\d{3,5})\s*(?P<subject>.*)$",
        r"^(?P<month>\d{1,2})\.(?P<day>\d{1,2})\s*(?P<type>[记转银现收付])?-?(?P<num>\d{1,5})\s*(?P<subject>.*)$",
    ]

    for pattern in patterns:
        match = re.match(pattern, base)
        if not match:
            continue
        data = match.groupdict()
        result["month"] = data.get("month") or ""
        result["day"] = data.get("day") or ""
        result["type"] = data.get("type") or "记"
        result["num"] = data.get("num") or ""
        result["subject"] = (data.get("subject") or "").strip()
        return result

    result["subject"] = base
    return result


def build_new_name(info: dict, company: str, year: str) -> str:
    """构建标准化新文件名。"""
    month = info["month"].zfill(2) if info["month"] else "00"
    day = info["day"].zfill(2) if info["day"] else "00"
    voucher_type = info["type"] or "记"
    number = info["num"]

    if number:
        return f"{company}{year}{month}{day}{voucher_type}{number}"

    subject = sanitize_filename(info["subject"]) or "未解析"
    return f"{company}{year}{month}{day}_未解析_{subject}"


def process(
    folder: str,
    company: str = "A公司",
    year: str = "2025",
    dry_run: bool = False,
) -> str:
    """批量重命名凭证 PDF。

    Args:
        folder: 文件夹路径
        company: 客户简称
        year: 年份
        dry_run: True 时仅预览，不实际修改

    Returns:
        CSV 清单路径
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"找不到文件夹：{folder}")

    files = sorted(path for path in folder.iterdir() if path.suffix.lower() == ".pdf")
    if not files:
        raise SystemExit("该文件夹内没有 PDF 文件。")

    logger.info("找到 %d 个 PDF 文件。", len(files))

    rows = []
    unknown_date_count = 0
    for file_path in files:
        info = parse_filename(file_path.name)
        new_name = build_new_name(info, company, year)
        rows.append((file_path, info, new_name))
        if not info["day"]:
            unknown_date_count += 1

    csv_path = folder.parent / "凭证清单.csv"
    scan_base = datetime(int(year) if year.isdigit() else 2025, 1, 1, 9, 0)
    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["序号", "原始文件名", "扫描时间", "月份", "日期", "凭证字", "凭证号", "科目/摘要", "建议新文件名"])
        for index, (orig, info, new_name) in enumerate(rows, 1):
            scan_time = (scan_base + timedelta(minutes=index - 1)).strftime("%Y-%m-%d %H.%M")
            writer.writerow([
                index, orig.name, f"扫描全能王 {scan_time}",
                info["month"], info["day"], info["type"],
                info["num"], info["subject"], new_name,
            ])

    logger.info("凭证清单已导出：%s", csv_path)
    if unknown_date_count:
        logger.warning("有 %d 个文件未识别出日期，文件名日期会使用 00。", unknown_date_count)

    if dry_run:
        logger.info("[DRY-RUN] 将重命名 %d 个文件（未实际操作）", len(rows))
        for orig, _info, new_name in rows[:10]:
            logger.info("  %s -> %s.pdf", orig.name, sanitize_filename(new_name))
        if len(rows) > 10:
            logger.info("  ... 以及其他 %d 个文件", len(rows) - 10)
        return str(csv_path)

    backup_dir = folder / "原文件备份"
    backup_dir.mkdir(exist_ok=True)

    success = 0
    for src, _info, new_name in rows:
        backup_path = backup_dir / src.name
        if not backup_path.exists():
            shutil.copy2(src, backup_path)

        dst = unique_path(folder / f"{sanitize_filename(new_name)}.pdf")
        if src.resolve() == dst.resolve():
            continue
        os.rename(src, dst)
        success += 1

    logger.info("完成：成功重命名 %d 个文件。", success)
    logger.info("原文件备份：%s", backup_dir)
    return str(csv_path)
