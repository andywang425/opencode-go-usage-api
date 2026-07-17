"""组装响应。"""

from __future__ import annotations

from .fetcher import AuthExpiredError, FetchError, fetch_html
from .formatter import build_data
from .parser import is_no_subscription, parse_usage


def build_response() -> dict:
    """执行一次抓取+解析，返回响应字典。任何失败都归一为 success:false。"""
    try:
        html = fetch_html()
    except AuthExpiredError:
        # cookie 缺失/失效被重定向到登录页：与普通抓取失败区分开，便于运维
        # 与第三方软件按「凭证已失效」关键词精准识别（换 cookie 即可恢复）
        return {
            "success": False,
            "reason": "登录凭证已失效，请重新获取 auth cookie",
            "data": "",
        }
    except FetchError as exc:
        return {
            "success": False,
            "reason": f"抓取失败：{exc}",
            "data": "",
        }

    usages = parse_usage(html)
    if not usages:
        # 一项都没解析出来：先看是不是无 Go 订阅（页面结构正常、只是没用量）
        if is_no_subscription(html):
            return {
                "success": False,
                "reason": "当前账号无 OpenCode Go 订阅",
                "data": "",
            }
        # 走到这里说明 HTML 是 200 且未跳登录页（cookie 失效已在 fetcher 阶段
        # 被 AuthExpiredError 截获），解析空更可能是页面结构变更而非凭证失效
        return {
            "success": False,
            "reason": "未能从页面解析出用量数据（页面结构可能已变更）",
            "data": "",
        }

    return {
        "success": True,
        "reason": "",
        "data": build_data(usages),
    }
