"""parser 模块单元测试。"""

from __future__ import annotations

from opencode_go_usage_api.parser import (
    is_no_subscription,
    parse_dom,
    parse_inline,
    parse_usage,
)

# ---------- 内联 JSON  fixtures ----------

INLINE_HTML = """
<script>
rollingUsage: $R[31] = { status: "ok", resetInSec: 18000, usagePercent: 42 }
weeklyUsage: $R[32] = { status: "ok", resetInSec: 200674, usagePercent: 15 }
monthlyUsage: $R[33] = { status: "ok", resetInSec: 1864311, usagePercent: 25 }
</script>
"""

INLINE_PARTIAL_HTML = """
<script>
rollingUsage: $R[31] = { status: "ok", resetInSec: 9000, usagePercent: 10 }
weeklyUsage: $R[32] = { status: "ok", resetInSec: 100000, usagePercent: 55 }
</script>
"""

# monthlyUsage 出现两次：一次 null（订阅信息），一次真正的用量块
INLINE_DUPLICATE_MONTHLY_HTML = """
<script>
rollingUsage: $R[10] = { status: "ok", resetInSec: 5000, usagePercent: 3 }
weeklyUsage: $R[11] = { status: "ok", resetInSec: 80000, usagePercent: 20 }
monthlyUsage: null,
monthlyUsage: $R[12] = { status: "ok", resetInSec: 2000000, usagePercent: 60 }
</script>
"""

# ---------- DOM fixtures ----------

DOM_HTML_ZH = """
<div data-slot="usage-item"><div data-slot="usage-header">\
<span data-slot="usage-label">滚动用量</span>\
<span data-slot="usage-value"><!--$-->7<!--/-->%</span></div>\
<div data-slot="progress"><div data-slot="progress-bar" style="width:7%"></div></div>\
<span data-slot="reset-time"><!--$-->重置于<!--/--> <!--$-->3 小时 0 分钟<!--/--></span></div>
<div data-slot="usage-item"><div data-slot="usage-header">\
<span data-slot="usage-label">每周用量</span>\
<span data-slot="usage-value"><!--$-->30<!--/-->%</span></div>\
<div data-slot="progress"><div data-slot="progress-bar" style="width:30%"></div></div>\
<span data-slot="reset-time"><!--$-->重置于<!--/--> <!--$-->1 天 7 小时<!--/--></span></div>
<div data-slot="usage-item"><div data-slot="usage-header">\
<span data-slot="usage-label">每月用量</span>\
<span data-slot="usage-value"><!--$-->50<!--/-->%</span></div>\
<div data-slot="progress"><div data-slot="progress-bar" style="width:50%"></div></div>\
<span data-slot="reset-time"><!--$-->重置于<!--/--> <!--$-->21 天 13 小时<!--/--></span></div>
"""

# 英文 locale 页面：标签文本不同，但 data-slot 结构一致
DOM_HTML_EN = """
<div data-slot="usage-item"><div data-slot="usage-header">\
<span data-slot="usage-label">Rolling usage</span>\
<span data-slot="usage-value"><!--$-->12<!--/-->%</span></div>\
<div data-slot="progress"><div data-slot="progress-bar" style="width:12%"></div></div>\
<span data-slot="reset-time"><!--$-->Resets in<!--/--> <!--$-->5 hours 0 minutes<!--/--></span></div>
<div data-slot="usage-item"><div data-slot="usage-header">\
<span data-slot="usage-label">Weekly usage</span>\
<span data-slot="usage-value"><!--$-->44<!--/-->%</span></div>\
<div data-slot="progress"><div data-slot="progress-bar" style="width:44%"></div></div>\
<span data-slot="reset-time"><!--$-->Resets in<!--/--> <!--$-->2 days 7 hours<!--/--></span></div>
<div data-slot="usage-item"><div data-slot="usage-header">\
<span data-slot="usage-label">Monthly usage</span>\
<span data-slot="usage-value"><!--$-->80<!--/-->%</span></div>\
<div data-slot="progress"><div data-slot="progress-bar" style="width:80%"></div></div>\
<span data-slot="reset-time"><!--$-->Resets in<!--/--> <!--$-->21 days 13 hours<!--/--></span></div>
"""

# 无订阅页面
NO_SUBSCRIPTION_HTML = """
<div data-slot="subscribe-button">订阅 Go</div>
<script>lite: null, liteSubscriptionID: null,</script>
"""

HAS_SUBSCRIPTION_HTML = """
<div data-slot="manage-button">管理订阅</div>
<script>lite: { id: "sub_123" }, liteSubscriptionID: "sub_123",</script>
"""


# ---------- parse_inline tests ----------


class TestParseInline:
    def test_parses_all_three_sections(self) -> None:
        result = parse_inline(INLINE_HTML)
        assert len(result) == 3
        assert result["rolling"].percent == 42
        assert result["rolling"].reset_in_sec == 18000
        assert result["rolling"].status == "ok"
        assert result["weekly"].percent == 15
        assert result["monthly"].percent == 25

    def test_partial_inline(self) -> None:
        result = parse_inline(INLINE_PARTIAL_HTML)
        assert len(result) == 2
        assert "rolling" in result
        assert "weekly" in result
        assert "monthly" not in result

    def test_duplicate_monthly_skips_null(self) -> None:
        result = parse_inline(INLINE_DUPLICATE_MONTHLY_HTML)
        assert len(result) == 3
        assert result["monthly"].percent == 60
        assert result["monthly"].reset_in_sec == 2000000

    def test_empty_html(self) -> None:
        assert parse_inline("") == {}
        assert parse_inline("<html>no usage here</html>") == {}


# ---------- parse_dom tests ----------


class TestParseDom:
    def test_parses_chinese_locale(self) -> None:
        result = parse_dom(DOM_HTML_ZH)
        assert len(result) == 3
        assert result["rolling"].percent == 7
        assert result["rolling"].reset_in_sec is None
        assert "3 小时 0 分钟" in (result["rolling"].reset_text or "")
        assert result["weekly"].percent == 30
        assert result["monthly"].percent == 50

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

    def test_merges_dom_for_missing_inline(self) -> None:
        """内联只有 2 项时，DOM 补齐缺失项。"""
        html = INLINE_PARTIAL_HTML + DOM_HTML_ZH
        result = parse_usage(html)
        assert len(result) == 3
        # rolling/weekly 来自内联
        assert result["rolling"].reset_in_sec == 9000
        assert result["weekly"].reset_in_sec == 100000
        # monthly 来自 DOM 兜底
        assert result["monthly"].percent == 50
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
