"""Fetch the OpenCode Go workspace page."""

from __future__ import annotations

import time

import httpx2

from .config import AccountConfig, FetchConfig


class FetchError(Exception):
    """Fetch-phase failure (network, timeout, or non-200 upstream)."""


class AuthExpiredError(FetchError):
    """Redirected to the login page: auth cookie expired, or workspace_id wrong/unreachable. Retrying is pointless."""


_LOGIN_PAGE_MARKER = "<title>OpenAuth</title>"

# Fixed backoff before retrying a network error, to avoid immediate retries
RETRY_BACKOFF_SECONDS = 0.5


class _FrozenCookies(httpx2.Cookies):
    """Cookie jar that ignores response Set-Cookie headers.

    A persistent Client's jar gets rewritten by upstream responses; freezing it
    means each request only carries the credentials from the config, matching the
    old "create a new Client per fetch" semantics.

    Official tracking issue for disabling cookie persistence (this implementation
    is the community workaround for it):
    https://github.com/pydantic/httpx2/issues/801

    TODO: if an official frozen-cookie option lands (e.g. httpx.NoCookies()),
    replace this class and the _cookies private-attribute assignment in
    create_client with the official API.
    """

    def extract_cookies(self, response: httpx2.Response) -> None:
        pass


def create_client(account: AccountConfig, settings: FetchConfig) -> httpx2.Client:
    """Create an app-lifetime persistent Client for one account, reusing the connection pool/TLS session.

    Each account gets its own Client so cookies never bleed between accounts;
    and since httpx2 drops request-level Cookie headers on redirects and rebuilds
    them from the Client jar, credentials must live at the Client level to survive
    in-site redirects.
    """
    client = httpx2.Client(
        timeout=settings.timeout,
        follow_redirects=True,
        headers={"User-Agent": settings.user_agent, "Accept": "text/html"},
    )
    # Both the Client constructor and the cookies setter re-wrap the value in a
    # plain Cookies, so a frozen jar can only be installed by replacing the
    # attribute after construction.
    client._cookies = _FrozenCookies(
        {"auth": account.auth_cookie, "oc_locale": settings.locale}
    )
    return client


def _is_login_page(resp: httpx2.Response) -> bool:
    """Return whether the response landed on the login or login-method page."""
    final = resp.url
    if final.host == "auth.opencode.ai":
        return True
    if final.host == "opencode.ai" and final.path.startswith("/auth"):
        return True
    return _LOGIN_PAGE_MARKER in resp.text


def fetch_html(
    account: AccountConfig, settings: FetchConfig, client: httpx2.Client
) -> str:
    """Live-fetch the workspace page once through the account's persistent Client."""
    last_exc: Exception | None = None
    for attempt in range(settings.retries + 1):
        if attempt:
            time.sleep(RETRY_BACKOFF_SECONDS)
        try:
            resp = client.get(account.workspace_url)
            if _is_login_page(resp):
                raise AuthExpiredError(
                    "redirected to the login page; the auth cookie may have expired, or workspace_id is wrong or unreachable"
                )
            if resp.status_code != 200:
                raise FetchError(f"upstream returned HTTP {resp.status_code}")
            return resp.text
        except FetchError:
            # Expired credentials and non-200 responses are definitive failures; retrying is pointless
            raise
        except Exception as exc:  # noqa: BLE001 network-layer errors (timeout, connect failure) all retry
            last_exc = exc
    raise FetchError(f"cannot connect to OpenCode (timeout or upstream error): {last_exc}")
