#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第二步：根据填好的分组Excel批量重命名

流程：
1. 先用 process_raw_scans.py 生成分组清单CSV
2. 在Excel里填好凭证字、凭证号、日期、科目
3. 运行本脚本，自动重命名

数据全程本地处理，不上传。
"""

import os, csv, shutil, re

print("=" * 50)
print("第二步：根据分组清单重命名")
print("=" * 50)

# 选文件夹
print("\n请把照片文件夹（里面要有填好的CSV）拖进终端，回车：")
folder = input().strip().strip("'\"")

if not os.path.isdir(folder):
    print("找不到文件夹")
    exit(1)

# 找CSV
csv_files = [f for f in os.listdir(folder) if f.endswith('.csv')]
if not csv_files:
    print("文件夹内找不到CSV，请先跑 process_raw_scans.py")
    exit(1)

csv_path = os.path.join(folder, csv_files[0])
print(f"找到清单：{csv_files[0]}")

# 读CSV
groups = []
with open(csv_path, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        t = row.get("凭证字(记/转/银/现)", "").strip()
        n = row.get("凭证号", "").strip()
        d = row.get("日期(日)", "").strip()
        s = row.get("科目/摘要", "").strip()
        c = row.get("文件数量", "0")
        groups.append({
            "type": t or "记",
            "num": n,
            "day": d,
            "subject": s,
            "count": int(c) if c.isdigit() else 0
        })

filled = sum(1 for g in groups if g["num"])
print(f"共 {len(groups)} 组，已填凭证号：{filled} 组")

# 客户名和年份
company = input("客户简称？（默认 A司）：").strip() or "A司"
year = input("年份？（默认 2025）：").strip() or "2025"

# 读文件列表
files = sorted([f for f in os.listdir(folder)
               if f.lower().endswith(('.jpg','.jpeg','.png','.heic','.pdf'))
               and not f.startswith('.')
               and not f.endswith('.csv')])

# 分隔关键词
keyword = input("分隔关键词？（默认 finger）：").strip() or "finger"

# 开始处理
backup_dir = os.path.join(folder, "原文件备份")
os.makedirs(backup_dir, exist_ok=True)

group_idx = 0
sub_idx = 0
total = 0
skipped = 0

for f in files:
    fp = os.path.join(folder, f)
    sz = os.path.getsize(fp)
    
    # 跳过分隔文件
    if keyword.lower() in f.lower() or sz < 50 * 1024:
        print(f"  跳过（分隔）：{f}")
        skipped += 1
        continue
    
    # 找对应组
    while group_idx < len(groups):
        g = groups[group_idx]
        if g["num"]:
            break
        group_idx += 1
    
    if group_idx >= len(groups):
        # 没组了，剩下的文件跳过
        print(f"  跳过（无对应组）：{f}")
        skipped += 1
        continue
    
    g = groups[group_idx]
    
    # 从文件名解析月份
    month = "01"
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', f)
    if m:
        month = m.group(2)
    
    day = g["day"].zfill(2) if g["day"] else (m.group(3) if m else "00")
    
    sub_idx += 1
    
    # 组内多张，加序号
    suffix = f"_{sub_idx}" if g["count"] > 1 else ""
    
    new_name = f"{company}{year}{month}{day}{g['type']}{g['num']}{suffix}"
    ext = os.path.splitext(f)[1]
    dst = os.path.join(folder, new_name + ext)
    
    # 防重名
    n = 1
    while os.path.exists(dst):
        n += 1
        dst = os.path.join(folder, f"{new_name}_{n}{ext}")
    
    shutil.copy2(fp, os.path.join(backup_dir, f))
    os.rename(fp, dst)
    total += 1
    print(f"  {f[:25]:25s} -> {os.path.basename(dst)}")
    
    # 判断是否切换到下一组
    if sub_idx >= g["count"]:
        group_idx += 1
        sub_idx = 0

print(f"\n完成！重命名 {total} 个，跳过 {skipped} 个（分隔文件+无对应组）")
print(f"原文件备份在：{backup_dir}")
