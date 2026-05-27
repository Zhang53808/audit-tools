"""根据凭证分组清单 CSV 批量重命名原始扫描件。"""

import csv
import os
import re
import shutil
from pathlib import Path

from audit_tools.common.text import sanitize_filename, unique_path
from audit_tools.common.logging import get_logger

logger = get_logger(__name__)

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".pdf"}


def find_csv(folder: Path) -> Path:
    """自动查找分组清单 CSV。"""
    preferred = folder / "凭证分组清单.csv"
    if preferred.exists():
        return preferred
    csv_files = sorted(path for path in folder.iterdir() if path.suffix.lower() == ".csv")
    return csv_files[0] if csv_files else None


def read_groups(csv_path: Path) -> list:
    """从 CSV 读取分组信息。"""
    groups = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            count_text = (row.get("文件数量") or "0").strip()
            groups.append({
                "type": (row.get("凭证字") or "记").strip() or "记",
                "num": (row.get("凭证号") or "").strip(),
                "day": (row.get("日期(日)") or "").strip(),
                "subject": (row.get("科目/摘要") or "").strip(),
                "count": int(count_text) if count_text.isdigit() else 0,
            })
    return groups


def extract_month(filename: str) -> tuple:
    """从文件名提取月份和日期。"""
    match = re.search(r"(\d{4})[-_.](\d{1,2})[-_.](\d{1,2})", filename)
    if match:
        return match.group(2).zfill(2), match.group(3).zfill(2)
    match = re.search(r"(\d{1,2})月(\d{1,2})日?", filename)
    if match:
        return match.group(1).zfill(2), match.group(2).zfill(2)
    return "01", "00"


def process(
    folder: str,
    company: str = "A公司",
    year: str = "2025",
    keyword: str = "finger",
    csv_file: str = None,
    dry_run: bool = False,
) -> None:
    """根据 CSV 清单重命名扫描件。

    Args:
        folder: 扫描件文件夹路径
        company: 客户简称
        year: 年份
        keyword: 分隔文件关键字
        csv_file: CSV 路径（默认自动查找）
        dry_run: True 时仅预览
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"找不到文件夹：{folder}")

    csv_path = Path(csv_file) if csv_file else find_csv(folder)
    if not csv_path or not csv_path.exists():
        raise SystemExit("文件夹内找不到 CSV，请先运行 scan-group。")

    groups = read_groups(csv_path)
    filled = sum(1 for group in groups if group["num"])
    logger.info("找到清单：%s。共 %d 组，已填写凭证号 %d 组。", csv_path.name, len(groups), filled)

    files = sorted(
        path for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS and not path.name.startswith(".")
    )

    group_idx = 0
    sub_idx = 0
    renamed = 0
    skipped = 0

    plan = []

    for src in files:
        if keyword.lower() in src.name.lower() or src.stat().st_size < 50 * 1024:
            logger.debug("  跳过分隔文件：%s", src.name)
            skipped += 1
            continue

        while group_idx < len(groups) and not groups[group_idx]["num"]:
            group_idx += 1

        if group_idx >= len(groups):
            logger.debug("  跳过，无对应清单组：%s", src.name)
            skipped += 1
            continue

        group = groups[group_idx]
        month, filename_day = extract_month(src.name)
        day = group["day"].zfill(2) if group["day"] else filename_day
        sub_idx += 1
        suffix = f"_{sub_idx}" if group["count"] > 1 else ""
        subject = f"_{sanitize_filename(group['subject'])}" if group["subject"] else ""
        new_name = f"{company}{year}{month}{day}{group['type']}{group['num']}{suffix}{subject}{src.suffix.lower()}"
        plan.append((src, new_name))

        if sub_idx >= group["count"]:
            group_idx += 1
            sub_idx = 0

    if dry_run:
        logger.info("[DRY-RUN] 将重命名 %d 个文件（未实际操作）", len(plan))
        for src, new_name in plan[:10]:
            logger.info("  %s -> %s", src.name, new_name)
        if len(plan) > 10:
            logger.info("  ... 以及其他 %d 个文件", len(plan) - 10)
        return

    backup_dir = folder / "原文件备份"
    backup_dir.mkdir(exist_ok=True)

    for src, new_name in plan:
        shutil.copy2(src, backup_dir / src.name)
        dst = unique_path(folder / sanitize_filename(new_name))
        os.rename(src, dst)
        renamed += 1
        logger.info("  %s -> %s", src.name, dst.name)

    logger.info("完成：重命名 %d 个，跳过 %d 个。", renamed, skipped)
    logger.info("原文件备份：%s", backup_dir)
