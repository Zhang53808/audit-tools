#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""原始扫描件分组清单生成工具。

适用于一批照片/PDF 中夹有分隔标记的情况。脚本会按分隔标记切分成多笔凭证，
并生成 CSV 清单，后续由 rename_from_csv.py 根据清单重命名。
"""

import csv
from pathlib import Path


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".pdf"}


def is_supported(path):
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTS and not path.name.startswith(".")


def detect_separators(files):
    print("请选择分隔文件识别方式：")
    print("  1 - 文件名包含关键字（默认 finger）")
    print("  2 - 文件小于指定大小")
    print("  3 - 不自动识别，全部按连续文件处理")
    choice = input("请输入 1/2/3 [默认 1]：").strip() or "1"

    separators = set()
    if choice == "1":
        keyword = input("分隔文件名关键字 [默认 finger]：").strip() or "finger"
        for index, path in enumerate(files):
            if keyword.lower() in path.name.lower():
                separators.add(index)
                print(f"  标记为分隔：{path.name}")
    elif choice == "2":
        raw = input("分隔文件大小上限 KB [默认 50]：").strip() or "50"
        try:
            threshold = int(raw) * 1024
        except ValueError:
            threshold = 50 * 1024
        for index, path in enumerate(files):
            if path.stat().st_size < threshold:
                separators.add(index)
                print(f"  标记为分隔：{path.name}")
    return separators


def split_groups(files, separator_indices):
    groups = []
    current = []
    for index, path in enumerate(files):
        if index in separator_indices:
            if current:
                groups.append(current)
                current = []
            continue
        current.append(path)

    if current:
        groups.append(current)
    return groups


def main():
    print("请把存放原始扫描件的文件夹拖进终端，然后回车：")
    folder = Path(input().strip().strip("'\""))
    if not folder.is_dir():
        raise SystemExit(f"找不到文件夹：{folder}")

    files = sorted(path for path in folder.iterdir() if is_supported(path))
    if not files:
        raise SystemExit("该文件夹内没有图片或 PDF 文件。")

    print(f"找到 {len(files)} 个文件。")
    separators = detect_separators(files)
    groups = split_groups(files, separators)

    print(f"识别出 {len(groups)} 笔凭证：")
    for index, group in enumerate(groups, 1):
        print(f"  第 {index:02d} 笔：{len(group)} 个文件，首张 {group[0].name}")

    csv_path = folder / "凭证分组清单.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["分组序号", "文件数量", "首张文件", "凭证字", "凭证号", "日期(日)", "科目/摘要", "备注"])
        for index, group in enumerate(groups, 1):
            writer.writerow([index, len(group), group[0].name, "记", "", "", "", ""])

    print(f"分组清单已生成：{csv_path}")
    print("请在 Excel 中打开清单，填好凭证字、凭证号、日期和摘要后，再运行 rename_from_csv.py。")


if __name__ == "__main__":
    main()
