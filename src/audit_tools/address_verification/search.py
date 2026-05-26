"""第2层：Web 搜索 + LLM 内容评估。

从 address_verification.py 提取。
"""

import json
import re
import subprocess
import sys
from typing import Optional

from audit_tools.common.api import llm_chat
from audit_tools.common.logging import get_logger

logger = get_logger(__name__)

FALLBACK_AUTHORITATIVE_DOMAINS = [
    "gov.cn",
    "baike.baidu.com",
]


def run_anysearch(query: str, cli_path: str, max_results: int = 2) -> str:
    """调 AnySearch CLI 搜索，返回原始输出文本。"""
    if not cli_path:
        logger.warning("AnySearch CLI 路径未配置")
        return ""

    cmd = [
        sys.executable,
        cli_path,
        "search", query,
        "--max_results", str(max_results),
        "--zone", "cn",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        logger.warning("AnySearch 搜索超时 [%s]", query[:40])
        return ""
    except Exception as e:
        logger.warning("AnySearch 调用失败: %s", e)
        return ""


def parse_search_results(raw_output: str) -> list:
    """从 AnySearch 输出中提取搜索结果（标题+URL）。"""
    results = []
    urls = re.findall(r'\*\*URL\*\*: (https?://[^\s\n]+)', raw_output)
    titles = re.findall(r'### \d+\. (.+?)(?:\n|$)', raw_output)

    for i in range(len(urls)):
        result = {"url": urls[i]}
        if i < len(titles):
            result["title"] = titles[i].strip()
        results.append(result)

    return results


def llm_evaluate(
    company: str,
    send_addr: str,
    search_results: list,
    api_key: str,
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-chat",
) -> Optional[dict]:
    """调 LLM API 评估搜索结果能否佐证发函地址。

    返回: {"conclusion": "confirmed"|"suspicious"|"no_evidence",
           "reason": "...", "authoritative": bool, "address_mentioned": bool}
    """
    if not api_key:
        return None

    results_text = ""
    for i, r in enumerate(search_results[:5]):
        results_text += (
            f"[{i+1}] 标题: {r.get('title', '无标题')}\n"
            f"    URL: {r.get('url', '')}\n\n"
        )

    if not results_text.strip():
        return {
            "conclusion": "no_evidence",
            "reason": "搜索无结果",
            "authoritative": False,
            "address_mentioned": False,
        }

    prompt = f"""你是一个审计助理，评估以下搜索结果能否证明公司发函地址有效。

公司名：{company}
发函地址：{send_addr}

搜索结果：
{results_text}

请判断：
1. 这些结果是权威来源吗？（政府公告/公司官网/权威媒体/百度百科=权威；
   B2B平台/聚合信息站/自媒体=不权威）
2. 搜索结果是否明确提到了该公司的地址信息？
3. 综合判断：能佐证发函地址吗？

返回**纯JSON**（不要markdown代码块），格式：
{{"authoritative": true/false, "address_mentioned": true/false, "conclusion": "confirmed|suspicious|no_evidence", "reason": "一句话中文理由"}}"""

    resp_data = llm_chat(
        [
            {"role": "system", "content": "你是一个审计助理。只返回JSON，不要加任何解释。"},
            {"role": "user", "content": prompt},
        ],
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_tokens=200,
        temperature=0.1,
    )

    if resp_data is None:
        return None

    try:
        text = resp_data["choices"][0]["message"]["content"].strip()
        if text.startswith("```"):
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)

        result = json.loads(text)
        for key in ["conclusion", "reason", "authoritative", "address_mentioned"]:
            if key not in result:
                result[key] = False if key != "reason" else "LLM返回格式异常"
        return result
    except Exception as e:
        logger.warning("LLM评估解析失败: %s", e)
        return None


def fallback_domain_check(search_results: list) -> dict:
    """降级策略：LLM 不可用时，用域名白名单判定。"""
    has_auth = False
    matched_urls = []

    for r in search_results:
        url = r.get("url", "")
        for domain in FALLBACK_AUTHORITATIVE_DOMAINS:
            if domain in url:
                has_auth = True
                matched_urls.append(url)
                break

    if has_auth:
        return {
            "conclusion": "confirmed",
            "reason": f"域名白名单匹配（降级模式）: {', '.join(matched_urls[:2])}",
            "authoritative": True,
            "address_mentioned": True,
        }
    elif len(search_results) > 0:
        return {
            "conclusion": "suspicious",
            "reason": "降级模式：有搜索结果但非gov.cn/百度百科",
            "authoritative": False,
            "address_mentioned": False,
        }
    else:
        return {
            "conclusion": "no_evidence",
            "reason": "降级模式：搜索无结果",
            "authoritative": False,
            "address_mentioned": False,
        }


def search_and_evaluate(
    company: str,
    send_addr: str,
    cli_path: str = "",
    api_key: str = "",
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-chat",
) -> dict:
    """第2层：搜索 + 评估。

    返回: {"conclusion": "confirmed"|"suspicious"|"no_evidence",
           "reason": "...", "authoritative": bool, "address_mentioned": bool,
           "mode": "llm"|"fallback", "search_snippet": str}
    """
    queries = [
        f'"{company}" "{send_addr[:10]}"',
        f'"{company}" "{send_addr[:6]}" 项目',
        f'"{company}" 地址',
    ]

    all_results = []
    for query in queries:
        raw = run_anysearch(query, cli_path, max_results=2)
        parsed = parse_search_results(raw)
        all_results.extend(parsed)

    # 去重
    seen = set()
    unique_results = []
    for r in all_results:
        url = r.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique_results.append(r)

    # 搜索摘要
    snippet_parts = []
    for r in unique_results[:5]:
        snippet_parts.append(f"- {r.get('title', '?')}: {r.get('url', '?')}")
    search_snippet = "\n".join(snippet_parts) if snippet_parts else "无搜索结果"

    # 先尝试 LLM 评估
    llm_result = llm_evaluate(company, send_addr, unique_results, api_key, base_url, model)

    if llm_result is not None:
        llm_result["mode"] = "llm"
        llm_result["search_snippet"] = search_snippet
        return llm_result

    fallback = fallback_domain_check(unique_results)
    fallback["mode"] = "fallback"
    fallback["search_snippet"] = search_snippet
    return fallback
