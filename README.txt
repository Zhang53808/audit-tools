📸 审计自动化工具包

放在桌面「拍凭重命名」文件夹里，所有脚本都在Mac终端运行：
cd ~/Desktop/拍凭重命名 && python3 脚本名.py


1. 折旧年审测算（depreciation_check.py）
读取客户折旧明细表，自动算一遍全年折旧，跟客户数据对比，标出差异。
支持按月分组和一行一条两种格式，自动识别表头列名。
输出Excel带差异汇总sheet，差异行自动标红。

2. 凭证照片重命名
- rename_vouchers.py：已经整理好的文件，批量重命名
- process_raw_scans.py：原始扫描件，按分隔标记自动分组，出清单让你填凭证号
- rename_from_csv.py：填好清单后，自动重命名

3. 数据清洗（clean_vouchers.py）
脏格式Excel拖进去，自动跳过空行、统一月份格式、洗金额、删合计行。

