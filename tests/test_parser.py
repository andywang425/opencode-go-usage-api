"""parser 模块单元测试。"""

from __future__ import annotations

from opencode_go_usage_api.parser import (
    is_no_subscription,
    parse_dom,
    parse_inline,
    parse_usage,
)

# ---------- 内联 JSON  fixtures ----------
# 基于真实抓包页面：lite.subscription.get 资源块

INLINE_HTML = """
<script>
self.$R = self.$R || [];
$R[28]($R[18], $R[31] = {
    mine: !0,
    useBalance: !1,
    region: $R[32] = ["us", "eu", "sg", "cn"],
    rollingUsage: $R[33] = {
        status: "ok",
        resetInSec: 18000,
        usagePercent: 0
    },
    weeklyUsage: $R[34] = {
        status: "ok",
        resetInSec: 189112,
        usagePercent: 5
    },
    monthlyUsage: $R[35] = {
        status: "ok",
        resetInSec: 2547316,
        usagePercent: 2
    }
});
</script>
"""

INLINE_PARTIAL_HTML = """
<script>
$R[28]($R[18], $R[31] = {
    mine: !0,
    useBalance: !1,
    region: $R[32] = ["us", "eu", "sg", "cn"],
    rollingUsage: $R[33] = {
        status: "ok",
        resetInSec: 14520,
        usagePercent: 10
    },
    weeklyUsage: $R[34] = {
        status: "ok",
        resetInSec: 345600,
        usagePercent: 55
    }
});
</script>
"""

# monthlyUsage 出现两次：billing 块里 null（订阅信息），subscription 块里真正的用量
INLINE_DUPLICATE_MONTHLY_HTML = """
<script>
$R[28]($R[22], $R[29] = {
    customerID: "cus_TEST000000001",
    paymentMethodType: "alipay",
    balance: 0,
    monthlyLimit: null,
    monthlyUsage: null,
    timeMonthlyUsageUpdated: null,
    subscription: null,
    subscriptionID: null,
    lite: $R[30] = {},
    liteSubscriptionID: "sub_TEST000000000000000000001"
});
$R[28]($R[18], $R[31] = {
    mine: !0,
    useBalance: !1,
    region: $R[32] = ["us", "eu", "sg", "cn"],
    rollingUsage: $R[33] = {
        status: "ok",
        resetInSec: 5400,
        usagePercent: 3
    },
    weeklyUsage: $R[34] = {
        status: "ok",
        resetInSec: 86400,
        usagePercent: 20
    },
    monthlyUsage: $R[35] = {
        status: "ok",
        resetInSec: 2547316,
        usagePercent: 60
    }
});
</script>
"""

# ---------- DOM fixtures ----------
# 基于真实抓包页面 DOM 结构（data-slot="usage" 区域内三个 usage-item）

DOM_HTML_ZH = """
<div data-slot="usage">
    <div data-hk="0000000100000000000100000500a14004210" data-slot="usage-item">
        <div data-slot="usage-header">
            <span data-slot="usage-label">滚动用量</span>
            <span data-slot="usage-value">
            <!--$-->
            0
            <!--/-->
            %</span>
        </div>
        <div data-slot="progress">
            <div data-slot="progress-bar" style="width:0%"></div>
        </div>
        <span data-slot="reset-time">
        <!--$-->
        重置于
        <!--/-->
        <!--$-->
        5 小时 0 分钟
        <!--/-->
        </span>
    </div>
    <div data-hk="0000000100000000000100000500a14004220" data-slot="usage-item">
        <div data-slot="usage-header">
            <span data-slot="usage-label">每周用量</span>
            <span data-slot="usage-value">
            <!--$-->
            5
            <!--/-->
            %</span>
        </div>
        <div data-slot="progress">
            <div data-slot="progress-bar" style="width:5%"></div>
        </div>
        <span data-slot="reset-time">
        <!--$-->
        重置于
        <!--/-->
        <!--$-->
        2 天 4 小时
        <!--/-->
        </span>
    </div>
    <div data-hk="0000000100000000000100000500a14004230" data-slot="usage-item">
        <div data-slot="usage-header">
            <span data-slot="usage-label">每月用量</span>
            <span data-slot="usage-value">
            <!--$-->
            2
            <!--/-->
            %</span>
        </div>
        <div data-slot="progress">
            <div data-slot="progress-bar" style="width:2%"></div>
        </div>
        <span data-slot="reset-time">
        <!--$-->
        重置于
        <!--/-->
        <!--$-->
        29 天 11 小时
        <!--/-->
        </span>
    </div>
</div>
"""

# 英文 locale 页面：标签文本不同，但 data-slot 结构一致
DOM_HTML_EN = """
<div data-slot="usage">
    <div data-hk="0000000100000000000100000500a14004210" data-slot="usage-item">
        <div data-slot="usage-header">
            <span data-slot="usage-label">Rolling usage</span>
            <span data-slot="usage-value">
            <!--$-->
            12
            <!--/-->
            %</span>
        </div>
        <div data-slot="progress">
            <div data-slot="progress-bar" style="width:12%"></div>
        </div>
        <span data-slot="reset-time">
        <!--$-->
        Resets in
        <!--/-->
        <!--$-->
        5 hours 0 minutes
        <!--/-->
        </span>
    </div>
    <div data-hk="0000000100000000000100000500a14004220" data-slot="usage-item">
        <div data-slot="usage-header">
            <span data-slot="usage-label">Weekly usage</span>
            <span data-slot="usage-value">
            <!--$-->
            44
            <!--/-->
            %</span>
        </div>
        <div data-slot="progress">
            <div data-slot="progress-bar" style="width:44%"></div>
        </div>
        <span data-slot="reset-time">
        <!--$-->
        Resets in
        <!--/-->
        <!--$-->
        2 days 7 hours
        <!--/-->
        </span>
    </div>
    <div data-hk="0000000100000000000100000500a14004230" data-slot="usage-item">
        <div data-slot="usage-header">
            <span data-slot="usage-label">Monthly usage</span>
            <span data-slot="usage-value">
            <!--$-->
            80
            <!--/-->
            %</span>
        </div>
        <div data-slot="progress">
            <div data-slot="progress-bar" style="width:80%"></div>
        </div>
        <span data-slot="reset-time">
        <!--$-->
        Resets in
        <!--/-->
        <!--$-->
        21 days 13 hours
        <!--/-->
        </span>
    </div>
</div>
"""

# 无订阅页面 —— 基于真实抓包（促销区 + billing 脚本块）
NO_SUBSCRIPTION_HTML = """
<section data-hk="0000000100000000000100000500a1400440" class="_root_9awwr_1">
    <p data-slot="promo-description">
        OpenCode Go 起价为 <strong>首月 $5</strong>，之后 $10/月。
    </p>
    <div data-slot="subscribe-actions">
        <button data-slot="subscribe-button" data-color="primary">订阅 Go</button>
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

# 有订阅页面 —— 基于真实抓包（订阅状态区 + billing 脚本块）
HAS_SUBSCRIPTION_HTML = """
<section data-hk="0000000100000000000100000500a1400420" class="_root_9awwr_1">
    <div data-slot="section-title">
        <div data-slot="title-row">
            <p>您已订阅 OpenCode Go。</p>
            <button data-color="primary">管理订阅</button>
        </div>
    </div>
</section>
<script>
$R[28]($R[22], $R[29] = {
    customerID: "cus_TEST000000001",
    paymentMethodType: "alipay",
    balance: 0,
    subscription: null,
    subscriptionID: null,
    lite: $R[30] = {},
    liteSubscriptionID: "sub_TEST000000000000000000001"
});
</script>
"""


# ---------- parse_inline tests ----------


class TestParseInline:
    def test_parses_all_three_sections(self) -> None:
        result = parse_inline(INLINE_HTML)
        assert len(result) == 3
        assert result["rolling"].percent == 0
        assert result["rolling"].reset_in_sec == 18000
        assert result["rolling"].status == "ok"
        assert result["weekly"].percent == 5
        assert result["weekly"].reset_in_sec == 189112
        assert result["monthly"].percent == 2
        assert result["monthly"].reset_in_sec == 2547316

    def test_partial_inline(self) -> None:
        result = parse_inline(INLINE_PARTIAL_HTML)
        assert len(result) == 2
        assert "rolling" in result
        assert result["rolling"].percent == 10
        assert result["rolling"].reset_in_sec == 14520
        assert "weekly" in result
        assert result["weekly"].percent == 55
        assert "monthly" not in result

    def test_duplicate_monthly_skips_null(self) -> None:
        result = parse_inline(INLINE_DUPLICATE_MONTHLY_HTML)
        assert len(result) == 3
        assert result["rolling"].percent == 3
        assert result["weekly"].percent == 20
        assert result["monthly"].percent == 60
        assert result["monthly"].reset_in_sec == 2547316

    def test_empty_html(self) -> None:
        assert parse_inline("") == {}
        assert parse_inline("<html>no usage here</html>") == {}


# ---------- parse_dom tests ----------


class TestParseDom:
    def test_parses_chinese_locale(self) -> None:
        result = parse_dom(DOM_HTML_ZH)
        assert len(result) == 3
        assert result["rolling"].percent == 0
        assert result["rolling"].reset_in_sec is None
        assert "5 小时 0 分钟" in (result["rolling"].reset_text or "")
        assert result["weekly"].percent == 5
        assert "2 天 4 小时" in (result["weekly"].reset_text or "")
        assert result["monthly"].percent == 2
        assert "29 天 11 小时" in (result["monthly"].reset_text or "")

    def test_parses_english_locale_by_structure(self) -> None:
        """DOM 解析不依赖标签文本，英文 locale 同样工作。"""
        result = parse_dom(DOM_HTML_EN)
        assert len(result) == 3
        assert result["rolling"].percent == 12
        assert result["weekly"].percent == 44
        assert result["monthly"].percent == 80
        assert "5 hours 0 minutes" in (result["rolling"].reset_text or "")

    def test_empty_html(self) -> None:
        assert parse_dom("") == {}

    def test_fallback_to_progress_bar_width(self) -> None:
        html = (
            '<div data-slot="usage-item">'
            '<div data-slot="progress"><div data-slot="progress-bar" style="width:66%"></div></div>'
            "</div>"
        )
        result = parse_dom(html)
        assert result["rolling"].percent == 66


# ---------- parse_usage (merged) tests ----------


class TestParseUsage:
    def test_inline_complete_skips_dom(self) -> None:
        result = parse_usage(INLINE_HTML)
        assert len(result) == 3
        # 内联路径有 reset_in_sec
        assert result["rolling"].reset_in_sec == 18000
        assert result["weekly"].reset_in_sec == 189112
        assert result["monthly"].reset_in_sec == 2547316

    def test_merges_dom_for_missing_inline(self) -> None:
        """内联只有 2 项时，DOM 补齐缺失项。"""
        html = INLINE_PARTIAL_HTML + DOM_HTML_ZH
        result = parse_usage(html)
        assert len(result) == 3
        # rolling/weekly 来自内联
        assert result["rolling"].reset_in_sec == 14520
        assert result["weekly"].reset_in_sec == 345600
        # monthly 来自 DOM 兜底
        assert result["monthly"].percent == 2
        assert result["monthly"].reset_in_sec is None

    def test_empty_returns_empty(self) -> None:
        assert parse_usage("<html>nothing</html>") == {}


# ---------- is_no_subscription tests ----------


class TestIsNoSubscription:
    def test_detects_no_subscription(self) -> None:
        assert is_no_subscription(NO_SUBSCRIPTION_HTML) is True

    def test_has_subscription(self) -> None:
        assert is_no_subscription(HAS_SUBSCRIPTION_HTML) is False

    def test_unrelated_html(self) -> None:
        assert is_no_subscription("<html>random</html>") is False
