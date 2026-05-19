#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
凭证PDF批量重命名脚本
用法：在终端里运行 python3 ~/Desktop/rename_vouchers.py


import os, re, csv, shutil
from datetime import datetime, timedelta

# ============================
# 1. 选择文件夹
# ============================
print("请把存放凭证PDF的文件夹拖进终端窗口，然后按回车：")
folder = input().strip()

# 去掉末尾可能带的多余字符
folder = folder.rstrip()
# 如果路径带引号（拖入时自动加的单引号），去掉
folder = folder.strip("'\"")

if not os.path.isdir(folder):
    print(f"❌ 找不到文件夹：{folder}")
    exit(1)

files = sorted([f for f in os.listdir(folder) if f.lower().endswith('.pdf')])
if not files:
    print("❌ 该文件夹内没有PDF文件")
    exit(1)

print(f"\n找到 {len(files)} 个PDF文件")
print("要处理哪个客户的凭证？（比如输入 A司 ）")
company = input().strip() or "A司"

print("年份是哪一年？（比如输入 2025 ）")
year = input().strip() or "2025"

# ============================
# 2. 解析文件名
# ============================
def parse_filename(filename):
    """从文件名中提取月份、日期、凭证字、凭证号、科目"""
    base = filename[:-4]  # 去掉.pdf
    result = {"month": "", "day": "", "type": "", "num": "", "subject": ""}

    # 模式1: "X月Y日 记-ZZZ 科目" 或 "X月Y 记-ZZZ 科目"
    m = re.match(r'(\d+)月(\d+)(?:日)?\s*(记|转|银|现)-(\d+)\s*(.*)', base)
    if m:
        result["month"], result["day"], result["type"], result["num"], result["subject"] = \
            m.group(1), m.group(2), m.group(3), m.group(4), m.group(5).strip()
        return result

    # 模式2: "X月Y日 ZZZ 科目"（无凭证字，如"6月26日 0357"）
    m = re.match(r'(\d+)月(\d+)(?:日)?\s+(\d+)\s*(.*)', base)
    if m:
        result["month"], result["day"], result["type"], result["num"], result["subject"] = \
            m.group(1), m.group(2), "记", m.group(3), m.group(4).strip()
        return result

    # 模式3: "X月ZZZZ科目"（无日期，如"1月0007长期待摊费用"）
    m = re.match(r'(\d+)月(\d{3,4})(.+)?', base)
    if m:
        result["month"], result["type"], result["num"] = m.group(1), "记", m.group(2)
        result["subject"] = (m.group(3) or "").strip()
        return result

    # 模式4: "X-ZZZ 科目"（如"6-119 销售费用宣传费"）
    m = re.match(r'(\d+)-(\d+)\s+(.*)', base)
    if m:
        result["month"], result["type"], result["num"], result["subject"] = \
            m.group(1), "记", m.group(2), m.group(3).strip()
        return result

    # 模式5: "药业 X月Y日 ..."（特殊文档）
    m = re.match(r'药业\s+(\d+)月(\d+)(?:日)?\s+(.*)', base)
    if m:
        result["month"], result["day"] = m.group(1), m.group(2)
        result["subject"] = "药业-" + (m.group(3) or "").strip()
        return result

    # 模式6: "投资 X月Y日 记-ZZ ..."
    m = re.match(r'投资\s+(\d+)月(\d+)(?:日)?\s+(记|转|银|现)-(\d+)\s*(.*)', base)
    if m:
        result["month"], result["day"], result["type"], result["num"] = \
            m.group(1), m.group(2), m.group(3), m.group(4)
        result["subject"] = "投资-" + (m.group(5) or "").strip()
        return result

    # 模式7: "三公仔 X月Y 记 Z ..."
    m = re.match(r'三公仔\s+(\d+)月(\d+)\s+记\s+(\d+)\s*(.*)', base)
    if m:
        result["month"], result["day"], result["type"], result["num"] = \
            m.group(1), m.group(2), "记", m.group(3)
        result["subject"] = "三公仔-" + (m.group(4) or "").strip()
        return result

    # 没匹配上，原样保留
    result["subject"] = base
    return result


def build_new_name(info, company, year):
    """根据解析结果生成新的文件名"""
    m = info["month"].zfill(2)
    d = info["day"].zfill(2) if info["day"] else "00"
    t = info["type"] if info["type"] else "记"
    n = info["num"]

    if info["subject"].startswith("药业-"):
        return f"{company}{year}{m}{d}_其他_{info['subject']}"

    if not n:
        return f"{company}{year}{m}{d}_未解析_{info['subject']}"

    return f"{company}{year}{m}{d}{t}{n}"


# ============================
# 3. 生成映射
# ============================
print("\n正在解析文件名...")
rows = []
unknown_date_count = 0
for f in files:
    info = parse_filename(f)
    new_name = build_new_name(info, company, year)
    rows.append((f, info, new_name))
    if not info["day"]:
        unknown_date_count += 1

# ============================
# 4. 处理无日期的文件
# ============================
if unknown_date_count > 0:
    print(f"\n⚠️  有 {unknown_date_count} 个文件无法识别日期（已标为 00）")
    print("建议：在生成的Excel里手动补充日期后，告诉我一声，我再帮你")
    print("      写个根据Excel重命名的脚本，比手工改快多了。\n")

# ============================
# 5. 生成时间戳（模拟扫描全能王格式）
# ============================
scan_base = datetime(int(year) if year.isdigit() else 2025, 5, 19, 9, 0)

# ============================
# 6. 导出CSV清单
# ============================
csv_path = os.path.join(os.path.dirname(folder) or folder, "凭证清单.csv")
with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(["序号", "原始文件名", "扫描时间", "月份", "日", "凭证字", "凭证号", "科目/摘要", "建议新文件名"])
    for i, (orig, info, new_name) in enumerate(rows, 1):
        ts = scan_base + timedelta(minutes=i - 1)
        scan_time = ts.strftime("%Y-%m-%d %H.%M")
        w.writerow([i, orig, f"扫描全能王 {scan_time}",
                     info["month"], info["day"], info["type"],
                     info["num"], info["subject"], new_name])

print(f"✅ 凭证清单已导出：{csv_path}")

# ============================
# 7. 开始重命名
# ============================
print(f"\n即将重命名 {len(rows)} 个文件，原文件将备份到「原文件备份」文件夹")
print("是否继续？(输入 y 继续，其他取消)")
confirm = input().strip().lower()
if confirm != 'y':
    print("已取消，文件未做任何修改")
    exit(0)

# 创建备份目录
backup_dir = os.path.join(folder, "原文件备份")
os.makedirs(backup_dir, exist_ok=True)
print(f"备份文件夹：{backup_dir}")

success = 0
for orig, info, new_name in rows:
    src = os.path.join(folder, orig)
    dst = os.path.join(folder, f"{new_name}.pdf")
    bak = os.path.join(backup_dir, orig)

    if not os.path.exists(src):
        print(f"  ⚠️ 找不到源文件：{orig}")
        continue

    # 备份
    if not os.path.exists(bak):
        shutil.copy2(src, bak)

    # 重命名
    if os.path.exists(dst) and src != dst:
        print(f"  ⚠️ 目标文件已存在，跳过：{new_name}.pdf")
        continue

    os.rename(src, dst)
    success += 1

print(f"\n✅ 完成！成功重命名 {success} 个文件（共 {len(rows)} 个）")
print(f"📂 重命名后的文件仍在原文件夹中")
print(f"📂 原文件备份在：{backup_dir}")
print(f"📊 清单Excel：{csv_path}")
print("\n提示：以后要按日期重跑，只需修改CSV里的日期列，然后运行另一个脚本就行")
