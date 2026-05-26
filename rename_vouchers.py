#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按文件名解析凭证信息，并批量重命名 PDF。"""

import csv
import os
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path


VOUCHER_TYPES = "记转银现收付"


def sanitize_filename(value):
    value = re.sub(r'[\\/:*?"<>|]', "_", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_filename(filename):
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


def build_new_name(info, company, year):
    month = info["month"].zfill(2) if info["month"] else "00"
    day = info["day"].zfill(2) if info["day"] else "00"
    voucher_type = info["type"] or "记"
    number = info["num"]

    if number:
        return f"{company}{year}{month}{day}{voucher_type}{number}"

    subject = sanitize_filename(info["subject"]) or "未解析"
    return f"{company}{year}{month}{day}_未解析_{subject}"


def unique_path(path):
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    index = 2
    while True:
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def main():
    print("请把存放凭证 PDF 的文件夹拖进终端，然后回车：")
    folder = Path(input().strip().strip("'\""))
    if not folder.is_dir():
        raise SystemExit(f"找不到文件夹：{folder}")

    files = sorted(path for path in folder.iterdir() if path.suffix.lower() == ".pdf")
    if not files:
        raise SystemExit("该文件夹内没有 PDF 文件。")

    print(f"找到 {len(files)} 个 PDF 文件。")
    company = input("客户简称（例如 A公司）：").strip() or "A公司"
    year = input("年份（例如 2025）：").strip() or "2025"

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
                index,
                orig.name,
                f"扫描全能王 {scan_time}",
                info["month"],
                info["day"],
                info["type"],
                info["num"],
                info["subject"],
                new_name,
            ])

    print(f"凭证清单已导出：{csv_path}")
    if unknown_date_count:
        print(f"有 {unknown_date_count} 个文件未识别出日期，文件名日期会使用 00。")

    confirm = input(f"即将重命名 {len(rows)} 个文件，并备份原文件。输入 y 继续：").strip().lower()
    if confirm != "y":
        print("已取消，文件未修改。")
        return

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

    print(f"完成：成功重命名 {success} 个文件。")
    print(f"原文件备份：{backup_dir}")


if __name__ == "__main__":
    main()
