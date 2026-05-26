---
name: address-verification
description: 函证地址核查自动化。对发函地址与工商注册地址进行三层过滤（文本相似度 → 地理距离 → 搜索佐证），输出三色分级报告。Use when user needs to verify confirmation letter addresses for audit.
version: 1.0.0
tags: [audit, address-verification, confirmation-letters]
status: stable
---

# 函证地址核查

## 触发方式

用户说"函证"、"地址核查"、"发函地址"、"核查地址"、"verify addresses"时加载。

## 工具位置

```bash
SCRIPT="./address_verification.py"
TEST="${SCRIPT%.py}_test.py"  # 27个单元测试
```

## 输入

用户提供含有以下列的 Excel（列名可模糊匹配）：
- 公司名称
- 发函地址
- 工商注册地址

## 三层过滤流程

```
第1层：地址清洗 + 多策略文本相似度（ratio/token_sort/partial 取最高）
  → ≥85% 直接绿色通过，<70% 标记关注

第1.5层：腾讯地图地理编码 → Haversine 距离
  → ≤1km 绿色通过，1-5km 黄色需人工，>5km 必须走第2层

第2层：AnySearch 搜索 + DeepSeek LLM 内容评估
  → confirmed/suspicious/no_evidence 三档判定
```

## 工作流

### 1. 确认输入

问用户 Excel 文件在哪。检查文件存在性。确认是否要跳过第2层搜索（`--no-search`）。

### 2. 确认数据格式

用 Python 快速读 Excel 检查列名。如果列名不完全匹配，告知用户我们支持模糊匹配（含"公司名称""发函地址"等关键词即可）。

### 3. 运行

```bash
cd <工具所在目录>
python address_verification.py <输入文件> -o <输出文件>
```

可选参数：
- `--no-search`：跳过第2层搜索，仅用地址清洗+相似度+地图距离
- `--map-key KEY`：覆盖 .env 中的腾讯地图 Key
- `--llm-key KEY`：覆盖 .env 中的 DeepSeek Key

### 4. 解读输出

脚本自动生成 `<输入>_核查结果.xlsx`，含14列：
- 核心列：相似度(%)、距离(米)、搜索评估、风险评分(0-100)、风险等级、核查结论
- 结论三色：绿色通过 / 黄色需人工判断 / 红色异常
- Excel 自带冻结首行、自动筛选器、条件格式

解读时重点关注：
- **黄色条目**：实习生优先查（地址相似但不完全确定，搜索也找不到确证）
- **红色条目**：重点风险，地址矛盾 + 无权威来源佐证
- **搜索评估列**：DeepSeek 给出的具体理由（如"均为招标平台，非公司官网"）

### 5. 跑测试（调试时）

```bash
cd <工具所在目录>
python -m pytest test_address_verification.py -v
```

27 个用例覆盖地址清洗（省/区/缩写/标点/空白/边界）、相似度（三档+策略回退+空值）。

## 依赖

- Python: pandas, openpyxl, thefuzz, requests, python-Levenshtein, python-dotenv, tqdm
- 外部服务：腾讯地图 API（免费额度）+ DeepSeek API + AnySearch CLI
- 配置：通过 `.env` 文件或环境变量（`TENCENT_MAP_KEY`, `DEEPSEEK_API_KEY`, `ANYSEARCH_CLI`）

## 故障排查

| 症状 | 原因 | 处理 |
|:-----|:-----|:-----|
| "API失败" 在距离列 | 腾讯地图 Key 配额用完(状态码121) | 等第二天重置，或用 `--map-key` 换 Key |
| 搜索无结果 | AnySearch CLI 路径不对或网络问题 | 用 `--no-search` 跳过，仅靠地址相似度判断 |
| LLM评估失败 | DeepSeek Key 过期或余额不足 | 自动降级为域名白名单（gov.cn + 百度百科） |
| 所有都是异常 | 输入Excel列名不匹配 | 检查列是否含"公司名称""发函地址""工商注册地址"关键词 |
