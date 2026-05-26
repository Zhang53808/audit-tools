# 🦞 审计自动化工具包

> 逆向狗(nigo)方法论复现
> 整理日期：2026-05-25

## 文件说明

| 文件 | 说明 | 状态 |
|:----|:----|:----:|
| address_verification.py | 函证地址核查 - 三层过滤 | ✅ 已写好，等数据 |
| related_party_check.py | 关联方识别 - 12维度分析 | ⏳ 等中注协账号 |
| agent_tars_guide.md | Agent TARS 自动化操作指南 | ⏳ 等中注协账号 |

## 函证地址核查 - 直接用

### 1. 准备数据

搞一个Excel，三列：
```
公司名称 | 发函地址 | 工商注册地址
```

### 2. 获取腾讯地图API Key

1. 打开 https://lbs.qq.com/
2. 注册 -> 创建应用 -> 获取Key（免费额度够用）

### 3. 安装依赖

```bash
pip install pandas openpyxl thefuzz requests python-Levenshtein
```

### 4. 运行

```bash
cd <工具所在目录>
python address_verification.py 你的名单.xlsx --map-key 你的腾讯地图Key
```

### 5. 拿到结果

脚本自动生成 `你的名单_核查结果.xlsx`，通过标绿，异常标红。

## 关联方识别 - 等账号

拿到中注协账号后找我，一步到位跑通。

## 联系方式

🦞 大傻虾 - 直接微信喊我
