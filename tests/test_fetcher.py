from __future__ import annotations

import httpx2
import pytest

from opencode_go_usage_api.config import AccountConfig, FetchConfig
from opencode_go_usage_api.fetcher import FetchError, fetch_html


def test_fetches_each_account_with_its_own_url_and_cookie(monkeypatch) -> None:
    requests: list[tuple[str, dict[str, str]]] = []

    class FakeClient:
        def __init__(self, *, cookies, headers, **kwargs) -> None:
            self.cookies = cookies
            assert headers == {"User-Agent": "test-agent", "Accept": "text/html"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            pass

        def get(self, url):
            requests.append((url, self.cookies))
            request = httpx2.Request("GET", url)
            return httpx2.Response(200, text="usage page", request=request)

    monkeypatch.setattr("opencode_go_usage_api.fetcher.httpx2.Client", FakeClient)
    settings = FetchConfig(10, 1, "zh", "test-agent")
    main = AccountConfig("Main", "main-cookie", "wrk_main")
    backup = AccountConfig("backup", "backup-cookie", "wrk_backup")

    assert fetch_html(main, settings) == "usage page"
    assert fetch_html(backup, settings) == "usage page"
    assert requests == [
        (
            "https://opencode.ai/workspace/wrk_main/go",
            {"auth": "main-cookie", "oc_locale": "zh"},
        ),
        (
            "https://opencode.ai/workspace/wrk_backup/go",
            {"auth": "backup-cookie", "oc_locale": "zh"},
        ),
    ]


def _make_fake_client(get_impl):
    """构造最小 FakeClient，get 行为由 get_impl 提供。"""

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            pass

        def get(self, url):
            return get_impl(url)

    return FakeClient


def test_non_200_fails_immediately_without_retry(monkeypatch) -> None:
    """上游非 200（如 403/404/429）是明确失败，不应重试。"""
    attempts: list[str] = []

    def get_impl(url):
        attempts.append(url)
        request = httpx2.Request("GET", url)
        return httpx2.Response(429, text="rate limited", request=request)

    monkeypatch.setattr(
        "opencode_go_usage_api.fetcher.httpx2.Client", _make_fake_client(get_impl)
    )
    settings = FetchConfig(10, 3, "zh", "test-agent")

    with pytest.raises(FetchError, match="HTTP 429"):
        fetch_html(AccountConfig("main", "cookie", "wrk_main"), settings)
    assert len(attempts) == 1


def test_network_error_retries_then_succeeds(monkeypatch) -> None:
    """网络层异常（超时、连接失败）仍按 retries 重试。"""
    attempts: list[str] = []

    def get_impl(url):
        attempts.append(url)
        if len(attempts) == 1:
            raise httpx2.ConnectTimeout("timeout")
        request = httpx2.Request("GET", url)
        return httpx2.Response(200, text="usage page", request=request)

    monkeypatch.setattr(
        "opencode_go_usage_api.fetcher.httpx2.Client", _make_fake_client(get_impl)
    )
    settings = FetchConfig(10, 1, "zh", "test-agent")

    assert fetch_html(AccountConfig("main", "cookie", "wrk_main"), settings) == "usage page"
    assert len(attempts) == 2
