"""formatter 模块单元测试。"""

from __future__ import annotations

import pytest

from opencode_go_usage_api.formatter import (
    DEFAULT_DATA_TEMPLATE,
    build_data,
    fmt_reset,
    validate_template,
)
from opencode_go_usage_api.models import Usage


def _usage(percent: int, reset_in_sec: int | None = None, status: str | None = "ok", reset_text: str | None = None) -> Usage:
    return Usage(percent=percent, reset_in_sec=reset_in_sec, status=status, reset_text=reset_text)


# ---------- fmt_reset tests ----------


class TestFmtReset:
    def test_days_and_hours(self) -> None:
        assert fmt_reset(_usage(0, reset_in_sec=90000)) == "1d1h"

    def test_hours_and_minutes(self) -> None:
        assert fmt_reset(_usage(0, reset_in_sec=5400)) == "1h30m"

    def test_hours_only(self) -> None:
        assert fmt_reset(_usage(0, reset_in_sec=7200)) == "2h"

    def test_minutes_only(self) -> None:
        assert fmt_reset(_usage(0, reset_in_sec=300)) == "5m"

    def test_zero_seconds(self) -> None:
        assert fmt_reset(_usage(0, reset_in_sec=0)) == "0m"

    def test_negative_clamped_to_zero(self) -> None:
        assert fmt_reset(_usage(0, reset_in_sec=-100)) == "0m"

    def test_none_uses_reset_text(self) -> None:
        assert fmt_reset(_usage(0, reset_text="重置于 2 天 7 小时")) == "重置于 2 天 7 小时"

    def test_none_no_text_returns_question(self) -> None:
        assert fmt_reset(_usage(0)) == "?"


# ---------- build_data tests ----------


class TestBuildData:
    def test_default_template_full(self) -> None:
        usages = {
            "rolling": _usage(10, reset_in_sec=18000),
            "weekly": _usage(25, reset_in_sec=200674),
            "monthly": _usage(50, reset_in_sec=1864311),
        }
        result = build_data(usages)
        assert "10%" in result
        assert "25%" in result
        assert "50%" in result
        assert "5h" in result
        assert "2d7h" in result
        assert "21d13h" in result

    def test_custom_template(self) -> None:
        usages = {
            "rolling": _usage(42, reset_in_sec=3600),
            "weekly": _usage(0, reset_in_sec=86400),
            "monthly": _usage(0, reset_in_sec=86400 * 30),
        }
        result = build_data(usages, "R:{rolling_percent}% W:{weekly_percent}%")
        assert result == "R:42% W:0%"

    def test_missing_section_shows_dash(self) -> None:
        usages = {"rolling": _usage(5, reset_in_sec=100)}
        result = build_data(usages)
        assert "5%" in result
        assert "—" in result  # weekly/monthly 缺失显示 —

    def test_unknown_placeholder_preserved(self) -> None:
        usages = {"rolling": _usage(1, reset_in_sec=60)}
        result = build_data(usages, "{unknown_field} {rolling_percent}%")
        assert "{unknown_field}" in result
        assert "1%" in result

    def test_broken_template_falls_back_to_default(self) -> None:
        usages = {
            "rolling": _usage(10, reset_in_sec=60),
            "weekly": _usage(20, reset_in_sec=120),
            "monthly": _usage(30, reset_in_sec=180),
        }
        # 带属性访问的模板会触发 AttributeError
        result = build_data(usages, "{rolling_percent.attr}")
        # 回退到默认模板，仍能渲染
        assert "10%" in result


# ---------- validate_template tests ----------


class TestValidateTemplate:
    def test_valid_template(self) -> None:
        validate_template(DEFAULT_DATA_TEMPLATE)

    def test_unknown_placeholder_is_valid(self) -> None:
        validate_template("{rolling_percent}% {custom_thing}")

    def test_broken_brace_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_template("broken {")

    def test_attribute_access_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_template("{rolling_percent.nonexistent_attr}")
