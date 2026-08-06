from __future__ import annotations

import httpx2
import pytest

from opencode_go_usage_api.config import AccountConfig, FetchConfig
from opencode_go_usage_api.fetcher import (
    RETRY_BACKOFF_SECONDS,
    FetchError,
    create_client,
    fetch_html,
)

SETTINGS = FetchConfig(10, 1, "en", "test-agent")


def _make_client(account: AccountConfig, handler, settings=SETTINGS) -> httpx2.Client:
    """Build a test client that uses the real persistent-Client path, only intercepting the network layer."""
    client = create_client(account, settings)
    client._transport = httpx2.MockTransport(handler)
    return client


def _parse_cookie_header(value: str) -> dict[str, str]:
    return dict(part.split("=", 1) for part in value.split("; "))


def test_each_account_client_sends_own_url_and_cookie() -> None:
    """Each account has its own Client that carries its own credentials, invisible to the others."""
    requests: list[tuple[str, dict[str, str]]] = []

    def handler(request):
        requests.append(
            (str(request.url), _parse_cookie_header(request.headers["cookie"]))
        )
        return httpx2.Response(200, text="usage page")

    main = AccountConfig("Main", "main-cookie", "wrk_main")
    backup = AccountConfig("backup", "backup-cookie", "wrk_backup")

    assert fetch_html(main, SETTINGS, _make_client(main, handler)) == "usage page"
    assert fetch_html(backup, SETTINGS, _make_client(backup, handler)) == "usage page"
    assert requests == [
        (
            "https://opencode.ai/workspace/wrk_main/go",
            {"auth": "main-cookie", "oc_locale": "en"},
        ),
        (
            "https://opencode.ai/workspace/wrk_backup/go",
            {"auth": "backup-cookie", "oc_locale": "en"},
        ),
    ]


def test_upstream_set_cookie_does_not_pollute_client_jar() -> None:
    """When the persistent Client is reused, upstream Set-Cookie must not rewrite the configured credentials."""

    def handler(request):
        return httpx2.Response(
            200,
            text="usage page",
            headers={"set-cookie": "auth=hijacked; Path=/"},
        )

    account = AccountConfig("main", "cookie", "wrk_main")
    client = _make_client(account, handler)

    fetch_html(account, SETTINGS, client)
    fetch_html(account, SETTINGS, client)

    assert dict(client.cookies) == {"auth": "cookie", "oc_locale": "en"}


def test_non_200_fails_immediately_without_retry() -> None:
    """A non-200 upstream response (e.g. 403/404/429) is a definitive failure and should not be retried."""
    attempts: list[str] = []

    def handler(request):
        attempts.append(str(request.url))
        return httpx2.Response(429, text="rate limited")

    settings = FetchConfig(10, 3, "en", "test-agent")
    account = AccountConfig("main", "cookie", "wrk_main")
    client = _make_client(account, handler, settings)

    with pytest.raises(FetchError, match="HTTP 429"):
        fetch_html(account, settings, client)
    assert len(attempts) == 1


def test_network_error_retries_with_backoff_then_succeeds(monkeypatch) -> None:
    """Network-layer errors (timeout, connect failure) retry per the retries setting, with a small backoff first."""
    sleeps: list[float] = []
    monkeypatch.setattr("opencode_go_usage_api.fetcher.time.sleep", sleeps.append)
    attempts: list[str] = []

    def handler(request):
        attempts.append(str(request.url))
        if len(attempts) == 1:
            raise httpx2.ConnectTimeout("timeout")
        return httpx2.Response(200, text="usage page")

    account = AccountConfig("main", "cookie", "wrk_main")
    client = _make_client(account, handler)

    assert fetch_html(account, SETTINGS, client) == "usage page"
    assert len(attempts) == 2
    assert sleeps == [RETRY_BACKOFF_SECONDS]
