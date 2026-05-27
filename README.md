# 审计自动化工具包

> 逆向狗(nigo)方法论复现 + 年审现场实用小工具

---

## 安装

```bash
pip install -e .
```

或手动安装依赖：

```bash
pip install -r requirements.txt
```

---

## 统一 CLI

```bash
audit-tools --help

# 函证地址核查
audit-tools address-verify 名单.xlsx --map-key YOUR_KEY --llm-key YOUR_KEY

# 关联方识别（演示模式）
audit-tools related-party

# 关联方识别（真实数据）
audit-tools related-party 企业名单.xlsx -o 结果.xlsx

# 折旧测算（非交互模式）
audit-tools depreciation 固定资产.xlsx --year 2025 --method straight

# 折旧测算（交互模式）
audit-tools depreciation

# 凭证清洗
audit-tools vouchers clean 明细.xlsx

# 凭证 PDF 重命名
audit-tools vouchers rename 文件夹/ --company A公司 --year 2025 --dry-run

# 扫描件分组
audit-tools scans group 文件夹/

# 扫描件重命名
audit-tools scans rename 文件夹/ --company A公司 --year 2025 --dry-run
```

---

## 工具一览

| 类别 | 入口 | 用途 |
|:-----|:-----|:-----|
| 函证地址 | `audit-tools address-verify` | 三层过滤核查发函地址（文本相似度 → 地图距离 → AI搜索佐证） |
| 关联方 | `audit-tools related-party` | 12维度交叉比对识别隐性关联方 |
| 折旧 | `audit-tools depreciation` | 固定资产折旧年审测算 |
| 凭证 | `audit-tools vouchers clean` | 清洗凭证/明细类 Excel |
| 凭证 | `audit-tools vouchers rename` | 已整理凭证 PDF 批量重命名 |
| 扫描件 | `audit-tools scans group` | 原始扫描件按分隔标记分组 |
| 扫描件 | `audit-tools scans rename` | 根据分组清单重命名原始扫描件 |

---

## 也可以用原始脚本（向后兼容）

```bash
python address_verification.py 名单.xlsx
python related_party_check.py
python depreciation_check.py
python clean_vouchers.py
python rename_vouchers.py
python process_raw_scans.py
python rename_from_csv.py
```

---

## 函证地址核查

```bash
audit-tools address-verify 名单.xlsx --map-key KEY --llm-key KEY
```

输入：Excel（公司名称 / 发函地址 / 工商注册地址）

三层过滤：
1. 地址清洗 + 多策略文本相似度（≥85% 直接放行）
2. 腾讯地图地理编码 + Haversine 距离
3. AnySearch 搜索 + DeepSeek LLM 内容评估

输出：`名单_核查结果.xlsx`（绿/黄/红三色 + 风险评分0-100 + 14列详情）

详细说明见 `SKILL-address-verification.md`

---

## 关联方识别

```bash
# 演示（内置模拟数据）
audit-tools related-party

# 从Excel加载企业名单
audit-tools related-party 输入.xlsx -o 结果.xlsx
```

12维度交叉比对：股权穿透、共同股东、实际控制人、高管重叠、法人交叉、法人变更、同址经营、联系方式共用、变更时间窗口、名称相似、参保异常、人员关联

输出：`关联方核查结果.xlsx`（12维矩阵 + 证据文字 + 三色风险等级）

详细说明见 `SKILL-related-party-check.md`

---

## 固定资产折旧测算

```bash
# 交互模式（原始工作流）
audit-tools depreciation

# 命令行模式
audit-tools depreciation 固定资产.xlsx --year 2025 --method straight
```

自动识别客户折旧表表头，支持直线法和月折旧率法。

---

## 测试

```bash
pip install -e ".[dev]"
pytest tests/ -v                           # 全部 125 个用例
pytest tests/test_common.py -v             # 公共模块
pytest tests/test_depreciation.py -v       # 折旧测算
pytest tests/test_address_verification.py -v
pytest tests/test_related_party.py -v
```

---

## 配置

复制 `.env.example` 为 `.env`，填入你的 Key：

```bash
TENCENT_MAP_KEY=你的腾讯地图Key
DEEPSEEK_API_KEY=你的DeepSeek Key
```

`.env` 已被 `.gitignore` 保护，不会上传。

---

## 项目结构

```
src/audit_tools/
├── cli.py                    # 统一 CLI 入口
├── common/                   # 公共模块
│   ├── address.py            # 地址清洗 + 相似度
│   ├── amount.py             # 金额/日期解析
│   ├── excel_output.py       # Excel 三色输出
│   ├── api.py                # API 重试/地理编码/LLM
│   ├── logging.py            # 统一日志
│   └── text.py               # 文件名处理
├── address_verification/     # 函证地址核查
├── related_party/            # 关联方识别
├── depreciation/             # 折旧测算
├── vouchers/                 # 凭证工具
└── scans/                    # 扫描件工具
tests/                        # 测试（125 用例）
```

---

## 安全

- `.env`（含真实 Key）→ gitignore 拦截
- 客户数据 Excel → gitignore 拦截
- `__pycache__/`、`*.egg-info/` → gitignore 拦截
