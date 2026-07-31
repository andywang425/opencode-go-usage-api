"""抓取 OpenCode Go 工作区页面。"""

from __future__ import annotations

import time

import httpx2

from .config import AccountConfig, FetchConfig


class FetchError(Exception):
    """抓取阶段失败（网络、超时或上游非 200）。"""


class AuthExpiredError(FetchError):
    """被重定向到登录页：auth cookie 失效，或 workspace_id 错误/无权访问。重试无意义。"""


_LOGIN_PAGE_MARKER = "<title>OpenAuth</title>"

# 网络异常重试前的固定退避，避免立即重试
RETRY_BACKOFF_SECONDS = 0.5


class _FrozenCookies(httpx2.Cookies):
    """忽略响应 Set-Cookie 的 cookie jar。

    常驻 Client 的 jar 会被上游响应改写；冻结后每次请求只携带配置里的
    凭据，与旧的"每次抓取新建 Client"语义一致。

    官方对禁用 cookie 持久化的跟踪 issue（本实现即其中的社区 workaround）：
    https://github.com/pydantic/httpx2/issues/801

    TODO: 若官方落地冻结 Cookie 的方案（如 httpx.NoCookies()），
    用官方 API 替换本类及 create_client 中的 _cookies 私有属性赋值。
    """

    def extract_cookies(self, response: httpx2.Response) -> None:
        pass


def create_client(account: AccountConfig, settings: FetchConfig) -> httpx2.Client:
    """为一个账号创建应用生命周期内常驻的 Client，复用连接池/TLS 会话。

    每个账号独立 Client，cookie 互不可见，避免共享 jar 串号；且 httpx2
    跨重定向时会丢弃请求级 Cookie 头、只用 Client jar 重建，凭据必须放
    Client 级才能在站内重定向后仍然有效。
    """
    client = httpx2.Client(
        timeout=settings.timeout,
        follow_redirects=True,
        headers={"User-Agent": settings.user_agent, "Accept": "text/html"},
    )
    # Client 构造器和 cookies setter 都会把传入值重新包成普通 Cookies，
    # 想用冻结 jar 只能在构造后直接替换。
    client._cookies = _FrozenCookies(
        {"auth": account.auth_cookie, "oc_locale": settings.locale}
    )
    return client


def _is_login_page(resp: httpx2.Response) -> bool:
    """判断响应是否落在登录或选择登录方式页面。"""
    final = resp.url
    if final.host == "auth.opencode.ai":
        return True
    if final.host == "opencode.ai" and final.path.startswith("/auth"):
        return True
    return _LOGIN_PAGE_MARKER in resp.text


def fetch_html(
    account: AccountConfig, settings: FetchConfig, client: httpx2.Client
) -> str:
    """通过该账号的常驻 Client 实时抓取一次工作区页面。"""
    last_exc: Exception | None = None
    for attempt in range(settings.retries + 1):
        if attempt:
            time.sleep(RETRY_BACKOFF_SECONDS)
        try:
            resp = client.get(account.workspace_url)
            if _is_login_page(resp):
                raise AuthExpiredError(
                    "被重定向到登录页，登录凭证可能已失效，或 workspace_id 错误/无权访问"
                )
            if resp.status_code != 200:
                raise FetchError(f"上游返回 HTTP {resp.status_code}")
            return resp.text
        except FetchError:
            # 凭证失效和上游非 200 都是明确失败，重试无意义，直接上报
            raise
        except Exception as exc:  # noqa: BLE001 网络层异常（超时、连接失败）统一重试
            last_exc = exc
    raise FetchError(f"无法连接 OpenCode（超时或上游异常）：{last_exc}")
