"""service 模块单元测试。"""

from __future__ import annotations

from opencode_go_usage_api.config import AccountConfig, FetchConfig
from opencode_go_usage_api.fetcher import AuthExpiredError, FetchError
from opencode_go_usage_api.service import build_response

ACCOUNT = AccountConfig("test", "cookie", "wrk_test")
FETCH_CFG = FetchConfig(timeout=10, retries=1, locale="zh", user_agent="test")
TEMPLATE = "{rolling_percent}% | {weekly_percent}% | {monthly_percent}%"

INLINE_OK_HTML = """
<script>
rollingUsage: $R[1] = { status: "ok", resetInSec: 18000, usagePercent: 10 }
weeklyUsage: $R[2] = { status: "ok", resetInSec: 200000, usagePercent: 20 }
monthlyUsage: $R[3] = { status: "ok", resetInSec: 2000000, usagePercent: 30 }
</script>
"""

NO_SUB_HTML = """
<div data-slot="subscribe-button">订阅 Go</div>
<script>lite: null, liteSubscriptionID: null,</script>
"""


def _patch_fetch(monkeypatch, html: str | None = None, exc: Exception | None = None) -> None:
    def fake_fetch(account, settings):
        if exc:
            raise exc
        return html
    monkeypatch.setattr("opencode_go_usage_api.service.fetch_html", fake_fetch)


class TestBuildResponseSuccess:
    def test_success_with_inline_data(self, monkeypatch) -> None:
        _patch_fetch(monkeypatch, html=INLINE_OK_HTML)
        result = build_response(ACCOUNT, FETCH_CFG, TEMPLATE)
        assert result["success"] is True
        assert result["reason"] == ""
        assert result["data"] == "10% | 20% | 30%"

    def test_success_uses_default_template(self, monkeypatch) -> None:
        _patch_fetch(monkeypatch, html=INLINE_OK_HTML)
        from opencode_go_usage_api.formatter import DEFAULT_DATA_TEMPLATE
        result = build_response(ACCOUNT, FETCH_CFG, DEFAULT_DATA_TEMPLATE)
        assert result["success"] is True
        assert "10%" in result["data"]


class TestBuildResponseFetchErrors:
    def test_auth_expired(self, monkeypatch) -> None:
        _patch_fetch(monkeypatch, exc=AuthExpiredError("cookie 失效"))
        result = build_response(ACCOUNT, FETCH_CFG, TEMPLATE)
        assert result["success"] is False
        assert "凭证" in result["reason"]
        assert result["data"] == ""

    def test_fetch_error(self, monkeypatch) -> None:
        _patch_fetch(monkeypatch, exc=FetchError("超时"))
        result = build_response(ACCOUNT, FETCH_CFG, TEMPLATE)
        assert result["success"] is False
        assert "抓取失败" in result["reason"]
        assert result["data"] == ""


class TestBuildResponseParseErrors:
    def test_no_subscription(self, monkeypatch) -> None:
        _patch_fetch(monkeypatch, html=NO_SUB_HTML)
        result = build_response(ACCOUNT, FETCH_CFG, TEMPLATE)
        assert result["success"] is False
        assert "订阅" in result["reason"]

    def test_unparseable_page(self, monkeypatch) -> None:
        _patch_fetch(monkeypatch, html="<html>completely different structure</html>")
        result = build_response(ACCOUNT, FETCH_CFG, TEMPLATE)
        assert result["success"] is False
        assert "解析" in result["reason"]
        assert result["data"] == ""
