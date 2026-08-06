"""Fetch, parse, and assemble the response for a single account."""

from __future__ import annotations

import httpx2

from .config import AccountConfig, FetchConfig
from .fetcher import AuthExpiredError, FetchError, fetch_html
from .formatter import build_data
from .parser import is_no_subscription, parse_usage


def build_response(
    account: AccountConfig,
    fetch_config: FetchConfig,
    data_template: str,
    client: httpx2.Client,
) -> dict:
    """Live-query one account; any business failure is normalized to success:false."""
    try:
        html = fetch_html(account, fetch_config, client)
    except AuthExpiredError:
        return {
            "success": False,
            "reason": "auth cookie has expired, please re-fetch it; if the cookie is valid, check that workspace_id is correct",
            "data": "",
        }
    except FetchError as exc:
        return {
            "success": False,
            "reason": f"fetch failed: {exc}",
            "data": "",
        }

    usages = parse_usage(html)
    if not usages:
        if is_no_subscription(html):
            return {
                "success": False,
                "reason": "this account has no OpenCode Go subscription",
                "data": "",
            }
        return {
            "success": False,
            "reason": "failed to parse usage data from the page (the page structure may have changed)",
            "data": "",
        }

    return {
        "success": True,
        "reason": "",
        "data": build_data(usages, data_template),
    }
