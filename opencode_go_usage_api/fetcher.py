"""抓取 OpenCode Go 工作区页面。"""

from __future__ import annotations

import httpx2

from .config import AccountConfig, FetchConfig


class FetchError(Exception):
    """抓取阶段失败（网络、超时或上游非 200）。"""


class AuthExpiredError(FetchError):
    """auth cookie 缺失或失效；重试无意义。"""


_LOGIN_PAGE_MARKER = "<title>OpenAuth</title>"


def _is_login_page(resp: httpx2.Response) -> bool:
    """判断响应是否落在登录或选择登录方式页面。"""
    final = resp.url
    if final.host == "auth.opencode.ai":
        return True
    if final.host == "opencode.ai" and final.path.startswith("/auth"):
        return True
    return _LOGIN_PAGE_MARKER in resp.text


def fetch_html(account: AccountConfig, settings: FetchConfig) -> str:
    """使用指定账号实时抓取一次工作区页面。"""
    cookies = {"auth": account.auth_cookie, "oc_locale": settings.locale}
    headers = {"User-Agent": settings.user_agent, "Accept": "text/html"}

    last_exc: Exception | None = None
    for _attempt in range(settings.retries + 1):
        try:
            with httpx2.Client(
                timeout=settings.timeout,
                follow_redirects=True,
                cookies=cookies,
                headers=headers,
            ) as client:
                resp = client.get(account.workspace_url)
            if _is_login_page(resp):
                raise AuthExpiredError("被重定向到登录页，登录凭证可能已失效")
            if resp.status_code != 200:
                raise FetchError(f"上游返回 HTTP {resp.status_code}")
            return resp.text
        except AuthExpiredError:
            raise
        except Exception as exc:  # noqa: BLE001 网络层及上游 HTTP 异常统一重试
            last_exc = exc
    raise FetchError(f"无法连接 OpenCode（超时或上游异常）：{last_exc}")
