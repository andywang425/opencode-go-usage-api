"""抓取、解析并组装单个账号的响应。"""

from __future__ import annotations

from .config import AccountConfig, FetchConfig
from .fetcher import AuthExpiredError, FetchError, fetch_html
from .formatter import build_data
from .parser import is_no_subscription, parse_usage


def build_response(
    account: AccountConfig, fetch_config: FetchConfig, data_template: str
) -> dict:
    """实时查询一个账号；任何业务失败都归一为 success:false。"""
    try:
        html = fetch_html(account, fetch_config)
    except AuthExpiredError:
        return {
            "success": False,
            "reason": "登录凭证已失效，请重新获取 auth cookie；若 cookie 确认有效，请检查 workspace_id 是否正确",
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
        if is_no_subscription(html):
            return {
                "success": False,
                "reason": "当前账号无 OpenCode Go 订阅",
                "data": "",
            }
        return {
            "success": False,
            "reason": "未能从页面解析出用量数据（页面结构可能已变更）",
            "data": "",
        }

    return {
        "success": True,
        "reason": "",
        "data": build_data(usages, data_template),
    }
