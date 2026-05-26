#  审计自动化工具包

> 逆向狗(nigo)方法论复现 + 年审现场实用小工具

---

## 工具一览

| 类别 | 脚本 | 用途 |
|:-----|:-----|:-----|
| 🆕 函证地址 | `address_verification.py` | 三层过滤核查发函地址（文本相似度 → 地图距离 → AI搜索佐证） |
| 🆕 关联方 | `related_party_check.py` | 12维度交叉比对识别隐性关联方 |
| 🆕 关联方 | `run_qichacha.py` | 企查查导出数据 → 关联方引擎适配 |
| 折旧 | `depreciation_check.py` | 固定资产折旧年审测算 |
| 凭证 | `clean_vouchers.py` | 清洗凭证/明细类 Excel |
| 凭证 | `rename_vouchers.py` | 已整理凭证 PDF 批量重命名 |
| 扫描件 | `process_raw_scans.py` | 原始扫描件按分隔标记分组 |
| 扫描件 | `rename_from_csv.py` | 根据分组清单重命名原始扫描件 |

---

## 函证地址核查

```bash
pip install pandas openpyxl thefuzz requests python-Levenshtein python-dotenv tqdm
python address_verification.py 名单.xlsx
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
# 演示（内置卓朗科技案模拟数据）
python related_party_check.py

# 企查查导出数据
python run_qichacha.py 金控物产.xlsx -o 结果.xlsx
```

12维度交叉比对：股权穿透、共同股东、实际控制人、高管重叠、法人交叉、法人变更、同址经营、联系方式共用、变更时间窗口、名称相似、参保异常、人员关联

输出：`关联方核查结果.xlsx`（12维矩阵 + 证据文字 + 三色风险等级）

详细说明见 `SKILL-related-party-check.md` 和 `关联方核查结果-阅读指南.md`

---

## 函证地址核查 Skill

```bash
# 将 SKILL-address-verification.md 复制到 Claude Code skills 目录
cp SKILL-address-verification.md ~/.claude/skills/address-verification/SKILL.md
```

触发词：函证、地址核查、发函地址、verify address

---

## 关联方识别 Skill

```bash
# 将 SKILL-related-party-check.md 复制到 Claude Code skills 目录
cp SKILL-related-party-check.md ~/.claude/skills/related-party-check/SKILL.md
```

触发词：关联方、12维度、隐性关联、related party、客户供应商核查

---

## 测试

```bash
python -m pytest test_address_verification.py -v   # 27 个用例
python -m pytest test_related_party.py -v           # 36 个用例
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

## 固定资产折旧测算

```bash
python depreciation_check.py
```

自动识别客户折旧表表头，支持直线法和月折旧率法。

---

## 凭证 Excel 清洗

```bash
python clean_vouchers.py
```

统一月份格式、清洗金额字段、删除空行/合计行。

---

## 凭证 PDF 重命名

```bash
python rename_vouchers.py
```

从文件名识别月份/凭证号，统一命名格式：`客户简称+年月日+凭证字+凭证号.pdf`

---

## 扫描件分组与重命名

```bash
# 第一步：生成分组清单
python process_raw_scans.py

# 在 CSV 中填写凭证信息

# 第二步：批量重命名
python rename_from_csv.py
```

---

## 安全

- `.env`（含真实 Key）→ gitignore 拦截
- 客户数据 Excel → gitignore 拦截
- `__pycache__/`、`.DS_Store` → gitignore 拦截

---

## 联系方式

🦞 大傻虾
