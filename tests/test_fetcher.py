from __future__ import annotations

import httpx

from opencode_go_usage_api.config import AccountConfig, FetchConfig
from opencode_go_usage_api.fetcher import fetch_html


def test_fetches_each_account_with_its_own_url_and_cookie(monkeypatch) -> None:
    requests: list[tuple[str, dict[str, str]]] = []

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            pass

        def get(self, url, *, cookies, headers):
            requests.append((url, cookies))
            request = httpx.Request("GET", url)
            return httpx.Response(200, text="usage page", request=request)

    monkeypatch.setattr("opencode_go_usage_api.fetcher.httpx.Client", FakeClient)
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
