"""API 调用工具：重试、地理编码、LLM 对话。

替换所有 bare except Exception: pass，提供指数退避重试。
"""

import time
from typing import Any, Optional, Tuple

import requests

from audit_tools.common.logging import get_logger

logger = get_logger(__name__)

DEFAULT_RETRIES = 3
DEFAULT_TIMEOUT = 30
RETRY_BACKOFF_BASE = 1.5


def retry_request(
    method: str,
    url: str,
    *,
    max_retries: int = DEFAULT_RETRIES,
    timeout: int = DEFAULT_TIMEOUT,
    backoff_base: float = RETRY_BACKOFF_BASE,
    **kwargs,
) -> Optional[requests.Response]:
    """HTTP 请求，带指数退避重试。

    重试条件: ConnectionError, Timeout, HTTP 5xx, HTTP 429
    不重试: HTTP 4xx (除 429)

    Returns:
        Response 对象；全部重试失败返回 None
    """
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.request(method, url, timeout=timeout, **kwargs)
            if resp.status_code < 500 and resp.status_code != 429:
                return resp
            logger.warning(
                "HTTP %d on %s %s (attempt %d/%d)",
                resp.status_code, method, url[:80], attempt + 1, max_retries + 1
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.warning(
                "%s on %s %s (attempt %d/%d)",
                type(e).__name__, method, url[:80], attempt + 1, max_retries + 1
            )
            last_exception = e
        except requests.exceptions.RequestException as e:
            logger.error("Request failed on %s %s: %s", method, url[:80], e)
            return None

        if attempt < max_retries:
            delay = (backoff_base ** attempt)
            logger.debug("Retrying in %.1fs...", delay)
            time.sleep(delay)

    logger.error("All %d retries exhausted for %s %s", max_retries + 1, method, url[:80])
    return None


def geocode(address: str, map_key: str, *, timeout: int = 5) -> Optional[Tuple[float, float]]:
    """腾讯地图地理编码，返回 (lng, lat) 或 None。

    Args:
        address: 地址字符串
        map_key: 腾讯地图 API Key
        timeout: 超时秒数
    """
    url = "https://apis.map.qq.com/ws/geocoder/v1/"
    params = {"address": address, "key": map_key}

    resp = retry_request("GET", url, params=params, timeout=timeout)
    if resp is None:
        return None

    try:
        data = resp.json()
        if data.get("status") == 0:
            loc = data["result"]["location"]
            return (loc["lng"], loc["lat"])
        logger.debug("Geocoding API status=%s for: %s", data.get("status"), address[:30])
    except (ValueError, KeyError) as e:
        logger.warning("Geocoding parse error for %s: %s", address[:30], e)

    return None


def llm_chat(
    messages: list,
    api_key: str,
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-chat",
    *,
    max_tokens: int = 200,
    temperature: float = 0.1,
    timeout: int = 30,
) -> Optional[dict]:
    """调用 DeepSeek / OpenAI 兼容 Chat API。

    Args:
        messages: 消息列表 [{"role": "...", "content": "..."}]
        api_key: API Key
        base_url: API 地址
        model: 模型名称
        max_tokens: 最大 token 数
        temperature: 温度
        timeout: 超时秒数

    Returns:
        API 响应的完整 dict；失败返回 None
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    resp = retry_request(
        "POST",
        f"{base_url}/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    if resp is None:
        return None

    try:
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        logger.error("LLM API HTTP error: %s", e)
        return None
    except ValueError as e:
        logger.error("LLM API JSON parse error: %s", e)
        return None
