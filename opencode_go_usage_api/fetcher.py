"""抓取。"""

from __future__ import annotations

import httpx

from .config import (
    AUTH_COOKIE,
    FETCH_RETRIES,
    FETCH_TIMEOUT,
    OC_LOCALE,
    USER_AGENT,
    WORKSPACE_URL,
)


class FetchError(Exception):
    """抓取阶段失败（网络/超时/上游非 200/被重定向到登录）。"""


class AuthExpiredError(FetchError):
    """auth cookie 缺失或失效，被上游重定向到登录页。重试无意义，应立即上抛。"""


# 登录页稳定锚点：OpenAuth（openauth.js.org）渲染的页面标题。host/路径变化时
# 仍可据此兜底识别，避免把登录页 HTML 当成用量页喂给 parser。
_LOGIN_PAGE_MARKER = "<title>OpenAuth</title>"


def _is_login_page(resp: httpx.Response) -> bool:
    """判断响应是否落在了登录/选择登录方式页（cookie 失效的典型表现）。

    双信号，任一命中即判失效：
      1. URL 信号（主）：final URL 的 host 落在 auth.opencode.ai（host 判定）。
      2. 页面信号（辅）：host 仍是 opencode.ai 但路径以 /auth 开头，或页面 HTML
         含登录页稳定锚点 <title>OpenAuth</title>，兜住未来 host/路径变化。
    """
    final = httpx.URL(resp.url)
    if final.host == "auth.opencode.ai":
        return True
    if final.host == "opencode.ai" and final.path.startswith("/auth"):
        return True
    return _LOGIN_PAGE_MARKER in resp.text


def fetch_html() -> str:
    # AUTH_COOKIE / WORKSPACE_ID 已在 config 导入期校验非空，此处不再重复检查
    cookies = {"auth": AUTH_COOKIE, "oc_locale": OC_LOCALE}
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}

    last_exc: Exception | None = None
    for attempt in range(FETCH_RETRIES + 1):
        try:
            with httpx.Client(
                timeout=FETCH_TIMEOUT, follow_redirects=True
            ) as client:
                resp = client.get(WORKSPACE_URL, cookies=cookies, headers=headers)
            # 被重定向到登录页通常意味着 cookie 失效
            if _is_login_page(resp):
                raise AuthExpiredError("被重定向到登录页，登录凭证可能已失效")
            if resp.status_code != 200:
                raise FetchError(f"上游返回 HTTP {resp.status_code}")
            return resp.text
        except AuthExpiredError:
            # 凭证失效重试无意义，立即上抛
            raise
        except FetchError:
            raise
        except Exception as exc:  # noqa: BLE001 网络层各类异常统一归类
            last_exc = exc
    raise FetchError(f"无法连接 OpenCode（超时或上游异常）：{last_exc}")
