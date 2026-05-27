"""关联方识别 - 12维度检测函数。

从 related_party_check.py 提取，使用 common.address 消除重复。
"""

import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from thefuzz import fuzz

from audit_tools.common.address import clean_address as _clean_address_common

CheckResult = Tuple[bool, str]


# ---- 工具函数 ----

def _clean_address(addr: str) -> str:
    """地址清洗（委托给 common.address）。"""
    return _clean_address_common(addr)


def _address_similarity(addr1: str, addr2: str) -> float:
    """地址多策略相似度。"""
    s1 = _clean_address(addr1)
    s2 = _clean_address(addr2)
    if not s1 or not s2:
        return 0.0
    return max(fuzz.ratio(s1, s2), fuzz.token_sort_ratio(s1, s2), fuzz.partial_ratio(s1, s2))


def _name_similarity(name1: str, name2: str) -> float:
    """企业名称相似度（去除通用后缀后比较）。"""
    if not name1 or not name2:
        return 0.0
    suffixes = [
        "股份有限公司", "有限责任公司", "有限公司", "股份公司",
        "(特殊普通合伙)", "(普通合伙)", "(有限合伙)",
    ]
    n1, n2 = name1, name2
    for s in suffixes:
        n1 = n1.replace(s, "")
        n2 = n2.replace(s, "")
    return max(fuzz.ratio(n1, n2), fuzz.token_sort_ratio(n1, n2))


def _extract_names(items: List[str]) -> set:
    """从 '张某某(30%)' 格式中提取纯人名/企业名集合。"""
    names = set()
    for item in items:
        if isinstance(item, str):
            name = re.sub(r'\(.*?\)', '', item).strip()
            if name:
                names.add(name)
    return names


# ---- D01 股权穿透 ----

def check_D01_equity(audit: dict, target: dict) -> CheckResult:
    """审计方与客户是否有股权关系。

    三种情况:
      1. 共同股东
      2. 客户是审计方的股东（母公司）
      3. 审计方是客户的股东（子公司/投资企业）
    """
    audit_holders = _extract_names(audit.get("shareholders", []))
    target_holders = _extract_names(target.get("shareholders", []))

    common = audit_holders & target_holders
    if common:
        return True, f"共同股东: {', '.join(sorted(common))}"

    audit_name = audit.get("name", "")
    target_name = target.get("name", "")

    for holder_name in audit_holders:
        sim = _name_similarity(target_name, holder_name)
        if sim >= 70:
            return True, f"客户「{target_name}」是审计方股东「{holder_name}」(相似度{sim}%)"

    for holder_name in target_holders:
        sim = _name_similarity(audit_name, holder_name)
        if sim >= 70:
            return True, f"审计方「{audit_name}」是客户股东「{holder_name}」(相似度{sim}%)"

    return False, ""


# ---- D02 共同股东 ----

def check_D02_common_shareholders(targets: List[dict]) -> Dict[str, CheckResult]:
    """多家客户背后是否有同一批人。"""
    results: Dict[str, CheckResult] = {}
    n = len(targets)
    triggered = set()

    for i in range(n):
        for j in range(i + 1, n):
            si = _extract_names(targets[i].get("shareholders", []))
            sj = _extract_names(targets[j].get("shareholders", []))
            common = si & sj
            if common:
                triggered.add(targets[i]["name"])
                triggered.add(targets[j]["name"])
                names_str = ', '.join(sorted(common))
                for t in [targets[i], targets[j]]:
                    name = t["name"]
                    old_evidence = results.get(name, (False, ""))[1]
                    other = targets[i]["name"] if targets[j]["name"] == name else targets[j]["name"]
                    new_ev = f"与「{other}」共同股东: {names_str}"
                    combined = "; ".join([e for e in [old_evidence, new_ev] if e])
                    results[name] = (True, combined)

    for t in targets:
        if t["name"] not in results:
            results[t["name"]] = (False, "")

    return results


# ---- D03 实际控制人 ----

def check_D03_actual_controller(audit: dict, target: dict) -> CheckResult:
    """最终受益人是否相同。"""
    audit_ctrl = audit.get("actual_controller", "")
    target_ctrl = target.get("actual_controller", "")
    if audit_ctrl and target_ctrl and audit_ctrl == target_ctrl:
        return True, f"实际控制人相同: {audit_ctrl}"
    return False, ""


# ---- D04 关键管理人员重叠 ----

def check_D04_executive_overlap(audit: dict, target: dict) -> CheckResult:
    """同一人在两边当高管。"""
    audit_execs = _extract_names(audit.get("executives", []))
    target_execs = _extract_names(target.get("executives", []))
    common = audit_execs & target_execs
    if common:
        return True, f"高管重叠: {', '.join(sorted(common))}"
    return False, ""


# ---- D05 法定代表人交叉 ----

def check_D05_legal_rep_cross(targets: List[dict]) -> Dict[str, CheckResult]:
    """同一人当多家企业法人。"""
    results: Dict[str, CheckResult] = {}
    legal_map: Dict[str, List[str]] = defaultdict(list)

    for t in targets:
        lr = t.get("legal_rep", "")
        if lr:
            legal_map[lr].append(t["name"])

    for lr, companies in legal_map.items():
        if len(companies) > 1:
            for name in companies:
                others = [c for c in companies if c != name]
                results[name] = (True, f"与「{'」「'.join(others)}」共用法人: {lr}")

    for t in targets:
        if t["name"] not in results:
            results[t["name"]] = (False, "")

    return results


# ---- D06 法人变更轨迹 ----

def check_D06_legal_rep_trajectory(audit: dict, target: dict) -> CheckResult:
    """客户前任法人是否 = 审计方高管/监事。"""
    audit_people = _extract_names(audit.get("executives", []))
    audit_people.add(audit.get("legal_rep", ""))
    target_historical = _extract_names(target.get("historical_legal_reps", []))

    common = audit_people & target_historical
    if common:
        return True, f"前法人「{', '.join(sorted(common))}」现为审计方人员"
    return False, ""


# ---- D07 同址经营 ----

def check_D07_same_address(audit: dict, target: dict) -> CheckResult:
    """注册地址相同或高度相似（≥70%）。"""
    a1 = audit.get("address", "")
    a2 = target.get("address", "")
    sim = _address_similarity(a1, a2)
    if sim >= 70:
        return True, f"地址相似度 {sim}%: 「{a1}」vs「{a2}」"
    return False, ""


# ---- D08 联系方式共用 ----

PUBLIC_EMAIL_DOMAINS = {
    "qq.com", "163.com", "126.com", "139.com", "sina.com",
    "sohu.com", "yeah.net", "gmail.com", "outlook.com",
    "hotmail.com", "foxmail.com", "189.cn", "wo.cn",
    "aliyun.com", "vip.qq.com", "vip.163.com",
}


def check_D08_shared_contact(targets: List[dict]) -> Dict[str, CheckResult]:
    """电话或邮箱域名相同（排除公共邮箱）。"""
    results: Dict[str, CheckResult] = {}
    phone_map: Dict[str, List[str]] = defaultdict(list)
    email_domain_map: Dict[str, List[str]] = defaultdict(list)

    for t in targets:
        phone = t.get("phone", "")
        email = t.get("email", "")
        if phone:
            phone_map[phone].append(t["name"])
        if email and "@" in email:
            domain = email.split("@")[1].strip().lower()
            if domain not in PUBLIC_EMAIL_DOMAINS:
                email_domain_map[domain].append(t["name"])

    for phone, companies in phone_map.items():
        if len(companies) > 1:
            for name in companies:
                others = [c for c in companies if c != name]
                results[name] = (True, f"与「{'」「'.join(others)}」共用电话: {phone}")

    for domain, companies in email_domain_map.items():
        if len(companies) > 1:
            for name in companies:
                existing = results.get(name)
                others = [c for c in companies if c != name]
                evidence = f"与「{'」「'.join(others)}」共用邮箱域名: @{domain}"
                if existing:
                    results[name] = (True, f"{existing[1]}; {evidence}")
                else:
                    results[name] = (True, evidence)

    for t in targets:
        if t["name"] not in results:
            results[t["name"]] = (False, "")

    return results


# ---- D09 变更时间窗口 ----

def check_D09_change_window(
    audit: dict, target: dict, transaction_date: Optional[str] = None
) -> CheckResult:
    """交易前后N天内有工商变更（暂未实现，留接口）。"""
    return False, ""


# ---- D10 名称相似 ----

def check_D10_name_similarity(audit: dict, target: dict) -> CheckResult:
    """企业名称相似（≥50%）或含有关键共用字。"""
    a_name = audit.get("name", "")
    t_name = target.get("name", "")
    sim = _name_similarity(a_name, t_name)
    if sim >= 50:
        return True, f"名称相似度 {sim}%: 「{a_name}」vs「{t_name}」"

    a_clean = a_name
    t_clean = t_name
    for s in ["股份有限公司", "有限责任公司", "有限公司", "股份公司"]:
        a_clean = a_clean.replace(s, "")
        t_clean = t_clean.replace(s, "")

    blocked = {"有限", "公司", "股份", "责任", "科技", "企业", "集团", "实业", "发展", "限公", "份有", "司股"}
    for i in range(len(a_clean) - 1):
        chunk = a_clean[i:i+2]
        if chunk not in blocked and chunk in t_clean:
            return True, f"名称含共同片段「{chunk}」"

    a_stripped = a_name
    t_stripped = t_name
    for s in ["股份有限公司", "有限责任公司", "有限公司", "股份公司"]:
        a_stripped = a_stripped.replace(s, "")
        t_stripped = t_stripped.replace(s, "")

    common_chars = set(a_stripped) & set(t_stripped)
    trivial = {"科", "技", "信", "息", "商", "贸", "工", "实", "业", "发", "展"}
    meaningful = common_chars - trivial
    if meaningful:
        return True, f"名称含共同特征字「{'」「'.join(sorted(meaningful))}」"

    return False, ""


# ---- D11 参保人数异常 ----

def check_D11_insured_anomaly(target: dict, threshold: int = 5000000) -> CheckResult:
    """0人参保但交易额巨大。"""
    insured = target.get("insured_employees", 0)
    amount = target.get("transaction_amount", 0)
    if insured == 0 and amount >= threshold:
        return True, f"0人参保但交易额达 {amount/10000:.0f}万"
    return False, ""


# ---- D12 补充人员关联 ----

def check_D12_supplement_personnel(
    target: dict,
    personnel_list: Optional[List[str]] = None,
) -> CheckResult:
    """补充名单匹配客户高管/股东。"""
    if not personnel_list:
        return False, ""

    target_people = _extract_names(target.get("executives", []))
    target_people |= _extract_names(target.get("shareholders", []))
    target_people.add(target.get("legal_rep", ""))

    personnel_set = set(p.strip() for p in personnel_list if p.strip())
    matches = target_people & personnel_set

    if matches:
        return True, f"补充名单匹配: {', '.join(sorted(matches))}"
    return False, ""
