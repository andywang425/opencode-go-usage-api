"""Unit tests for the service module."""

from __future__ import annotations

from opencode_go_usage_api.config import AccountConfig, FetchConfig
from opencode_go_usage_api.fetcher import AuthExpiredError, FetchError
from opencode_go_usage_api.service import build_response

ACCOUNT = AccountConfig("test", "cookie", "wrk_test")
FETCH_CFG = FetchConfig(timeout=10, retries=1, locale="en", user_agent="test")
TEMPLATE = "{rolling_percent}% | {weekly_percent}% | {monthly_percent}%"
# build_response only passes it through to the mocked fetch_html; a placeholder object is enough
CLIENT = object()

INLINE_OK_HTML = """
<script>
$R[28]($R[18], $R[31] = {
    mine: !0,
    useBalance: !1,
    region: $R[32] = ["us", "eu", "sg", "cn"],
    rollingUsage: $R[33] = {
        status: "ok",
        resetInSec: 18000,
        usagePercent: 10
    },
    weeklyUsage: $R[34] = {
        status: "ok",
        resetInSec: 189112,
        usagePercent: 20
    },
    monthlyUsage: $R[35] = {
        status: "ok",
        resetInSec: 2547316,
        usagePercent: 30
    }
});
</script>
"""

NO_SUB_HTML = """
<section data-hk="0000000100000000000100000500a1400440" class="_root_9awwr_1">
    <p data-slot="promo-description">
        OpenCode Go starts at <strong>$5 for the first month</strong>, then $10/month.
    </p>
    <div data-slot="subscribe-actions">
        <button data-slot="subscribe-button" data-color="primary">Subscribe to Go</button>
    </div>
</section>
<script>
$R[28]($R[22], $R[31] = {
    customerID: "cus_TEST000000002",
    paymentMethodType: "alipay",
    balance: 0,
    subscription: null,
    subscriptionID: null,
    lite: null,
    liteSubscriptionID: null
});
$R[28]($R[18], null);
$R[28]($R[20], null);
</script>
"""


def _patch_fetch(monkeypatch, html: str | None = None, exc: Exception | None = None) -> None:
    def fake_fetch(account, settings, client):
        if exc:
            raise exc
        return html
    monkeypatch.setattr("opencode_go_usage_api.service.fetch_html", fake_fetch)


class TestBuildResponseSuccess:
    def test_success_with_inline_data(self, monkeypatch) -> None:
        _patch_fetch(monkeypatch, html=INLINE_OK_HTML)
        result = build_response(ACCOUNT, FETCH_CFG, TEMPLATE, CLIENT)
        assert result["success"] is True
        assert result["reason"] == ""
        assert result["data"] == "10% | 20% | 30%"

    def test_success_uses_default_template(self, monkeypatch) -> None:
        _patch_fetch(monkeypatch, html=INLINE_OK_HTML)
        from opencode_go_usage_api.formatter import DEFAULT_DATA_TEMPLATE
        result = build_response(ACCOUNT, FETCH_CFG, DEFAULT_DATA_TEMPLATE, CLIENT)
        assert result["success"] is True
        assert "10%" in result["data"]


class TestBuildResponseFetchErrors:
    def test_auth_expired(self, monkeypatch) -> None:
        _patch_fetch(monkeypatch, exc=AuthExpiredError("cookie expired"))
        result = build_response(ACCOUNT, FETCH_CFG, TEMPLATE, CLIENT)
        assert result["success"] is False
        assert "cookie" in result["reason"]
        assert result["data"] == ""

    def test_fetch_error(self, monkeypatch) -> None:
        _patch_fetch(monkeypatch, exc=FetchError("timeout"))
        result = build_response(ACCOUNT, FETCH_CFG, TEMPLATE, CLIENT)
        assert result["success"] is False
        assert "fetch failed" in result["reason"]
        assert result["data"] == ""


class TestBuildResponseParseErrors:
    def test_no_subscription(self, monkeypatch) -> None:
        _patch_fetch(monkeypatch, html=NO_SUB_HTML)
        result = build_response(ACCOUNT, FETCH_CFG, TEMPLATE, CLIENT)
        assert result["success"] is False
        assert "subscription" in result["reason"]

    def test_unparseable_page(self, monkeypatch) -> None:
        _patch_fetch(monkeypatch, html="<html>completely different structure</html>")
        result = build_response(ACCOUNT, FETCH_CFG, TEMPLATE, CLIENT)
        assert result["success"] is False
        assert "parse" in result["reason"]
        assert result["data"] == ""
