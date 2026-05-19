#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原始扫描件整理脚本（拍手指版）

import os, re, csv, shutil
from datetime import datetime

# ============================
# 1. 选文件夹
# ============================
print("=" * 50)
print("📸 原始扫描件整理脚本")
print("=" * 50)

print("\n请把存放原始扫描件（扫描全能王导出的照片/PDF）的文件夹")
print("拖进终端窗口，然后回车：")
folder = input().strip().strip("'\"")

if not os.path.isdir(folder):
    print(f"❌ 找不到文件夹：{folder}")
    exit(1)

# 支持图片和PDF
exts = ('.jpg', '.jpeg', '.png', '.heic', '.pdf')
files = sorted([f for f in os.listdir(folder) if f.lower().endswith(exts)])

if not files:
    print("❌ 该文件夹内没有图片或PDF文件")
    exit(1)

print(f"\n找到 {len(files)} 个文件")
print("\n客户简称是什么？（比如 A司、B公司）")
company = input().strip()
print("年份？（比如 2025）")
year = input().strip()

# ============================
# 2. 找出分隔文件
# ============================
print("\n现在需要告诉脚本，哪些文件是"分隔标记"（你拍的手指/白纸）")
print("分隔文件的特征是什么？")
print("  1) 文件名包含某个关键词（如 'finger', 'sep', '分隔'）")
print("  2) 文件特别小（空白照片文件很小）")
print("  3) 我自己手动在Excel里标")
print("  4) 我来选模式：文件名包含以下文字")
choice = input("请选 1/2/3/4 [默认 1]：").strip() or "1"

separator_indices = set()
if choice == "1":
    keyword = input("请输入分隔文件名的关键词（默认 finger）：").strip() or "finger"
    for i, f in enumerate(files):
        if keyword.lower() in f.lower():
            separator_indices.add(i)
            print(f"  ✅ 标记为分隔：{f}")
elif choice == "2":
    # 按文件大小检测
    size_threshold = input("空白文件的大小上限(KB)？[默认 50]：").strip() or "50"
    try:
        size_threshold = int(size_threshold) * 1024
    except:
        size_threshold = 50 * 1024
    for i, f in enumerate(files):
        fp = os.path.join(folder, f)
        sz = os.path.getsize(fp)
        if sz < size_threshold:
            separator_indices.add(i)
            print(f"  ✅ 标记为分隔（{sz//1024}KB）：{f}")
elif choice == "3":
    print("\n跳过自动检测，稍后生成Excel让你手动标记")
else:
    keyword = input("请输入分隔文件名包含的文字：").strip()
    for i, f in enumerate(files):
        if keyword in f:
            separator_indices.add(i)
            print(f"  ✅ 标记为分隔：{f}")

# ============================
# 3. 按分隔分组
# ============================
groups = []
current_group = []

for i, f in enumerate(files):
    if i in separator_indices:
        if current_group:
            groups.append(current_group)
            current_group = []
    else:
        current_group.append(f)

if current_group:
    groups.append(current_group)

print(f"\n📦 共识别出 {len(groups)} 笔凭证")
for idx, g in enumerate(groups):
    print(f"  第 {idx+1:2d} 笔：{len(g)} 张文件（首张：{g[0][:30]}...）")

# ============================
# 4. 生成分组清单Excel
# ============================
csv_path = os.path.join(os.path.dirname(folder) or folder, "凭证分组清单.xlsx")
# 先用CSV，用户可以在Excel里打开
csv_path_simple = csv_path.replace('.xlsx', '.csv')

with open(csv_path_simple, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(["分组序号", "文件数量", "首张文件", "凭证字(记/转/银/现)", "凭证号", "日期(日)", "科目/摘要", "备注"])
    for idx, g in enumerate(groups):
        w.writerow([idx + 1, len(g), g[0], "记", "", "", "", ""])

print(f"\n📊 分组清单已生成：{csv_path_simple}")
print("请在Excel中打开，填写「凭证字、凭证号、日期、科目」这几列")
print("填好后保存，然后告诉我，我再给你写一个按清单重命名的脚本")

# 顺便生成一个重命名脚本框架（等用户填完Excel后再用）
backup_dir = os.path.join(folder, "原文件备份")
print(f"\n📂 原文件备份位置（如有需要）：{backup_dir}")
print("💡 后续流程：填Excel → 跑重命名脚本 → 搞定")

print("\n✅ 第一步完成！去填Excel吧，填完了叫我 🦞")
