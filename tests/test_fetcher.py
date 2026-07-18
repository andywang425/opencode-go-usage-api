from __future__ import annotations

import httpx2

from opencode_go_usage_api.config import AccountConfig, FetchConfig
from opencode_go_usage_api.fetcher import fetch_html


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
