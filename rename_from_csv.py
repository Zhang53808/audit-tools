#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根据凭证分组清单 CSV 批量重命名原始扫描件。"""

import csv
import os
import re
import shutil
from pathlib import Path


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".pdf"}


def sanitize_filename(value):
    value = re.sub(r'[\\/:*?"<>|]', "_", value)
    return re.sub(r"\s+", " ", value).strip()


def find_csv(folder):
    preferred = folder / "凭证分组清单.csv"
    if preferred.exists():
        return preferred
    csv_files = sorted(path for path in folder.iterdir() if path.suffix.lower() == ".csv")
    return csv_files[0] if csv_files else None


def read_groups(csv_path):
    groups = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            count_text = (row.get("文件数量") or "0").strip()
            groups.append(
                {
                    "type": (row.get("凭证字") or "记").strip() or "记",
                    "num": (row.get("凭证号") or "").strip(),
                    "day": (row.get("日期(日)") or "").strip(),
                    "subject": (row.get("科目/摘要") or "").strip(),
                    "count": int(count_text) if count_text.isdigit() else 0,
                }
            )
    return groups


def extract_month(filename):
    match = re.search(r"(\d{4})[-_.](\d{1,2})[-_.](\d{1,2})", filename)
    if match:
        return match.group(2).zfill(2), match.group(3).zfill(2)
    match = re.search(r"(\d{1,2})月(\d{1,2})日?", filename)
    if match:
        return match.group(1).zfill(2), match.group(2).zfill(2)
    return "01", "00"


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
    print("请把扫描件文件夹拖进终端，文件夹内应有填好的 CSV 清单：")
    folder = Path(input().strip().strip("'\""))
    if not folder.is_dir():
        raise SystemExit(f"找不到文件夹：{folder}")

    csv_path = find_csv(folder)
    if not csv_path:
        raise SystemExit("文件夹内找不到 CSV，请先运行 process_raw_scans.py。")

    groups = read_groups(csv_path)
    filled = sum(1 for group in groups if group["num"])
    print(f"找到清单：{csv_path.name}。共 {len(groups)} 组，已填写凭证号 {filled} 组。")

    company = input("客户简称 [默认 A公司]：").strip() or "A公司"
    year = input("年份 [默认 2025]：").strip() or "2025"
    keyword = input("分隔文件关键字 [默认 finger]：").strip() or "finger"

    files = sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS and not path.name.startswith(".")
    )

    backup_dir = folder / "原文件备份"
    backup_dir.mkdir(exist_ok=True)

    group_idx = 0
    sub_idx = 0
    renamed = 0
    skipped = 0

    for src in files:
        if keyword.lower() in src.name.lower() or src.stat().st_size < 50 * 1024:
            print(f"  跳过分隔文件：{src.name}")
            skipped += 1
            continue

        while group_idx < len(groups) and not groups[group_idx]["num"]:
            group_idx += 1

        if group_idx >= len(groups):
            print(f"  跳过，无对应清单组：{src.name}")
            skipped += 1
            continue

        group = groups[group_idx]
        month, filename_day = extract_month(src.name)
        day = group["day"].zfill(2) if group["day"] else filename_day
        sub_idx += 1
        suffix = f"_{sub_idx}" if group["count"] > 1 else ""
        subject = f"_{sanitize_filename(group['subject'])}" if group["subject"] else ""
        new_name = f"{company}{year}{month}{day}{group['type']}{group['num']}{suffix}{subject}{src.suffix.lower()}"
        dst = unique_path(folder / sanitize_filename(new_name))

        shutil.copy2(src, backup_dir / src.name)
        os.rename(src, dst)
        renamed += 1
        print(f"  {src.name} -> {dst.name}")

        if sub_idx >= group["count"]:
            group_idx += 1
            sub_idx = 0

    print(f"完成：重命名 {renamed} 个，跳过 {skipped} 个。")
    print(f"原文件备份：{backup_dir}")


if __name__ == "__main__":
    main()
