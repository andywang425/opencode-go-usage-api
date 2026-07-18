"""用量响应格式化。"""

from __future__ import annotations

from .models import Usage

DEFAULT_DATA_TEMPLATE = (
    "滚动 {rolling_percent}% ({rolling_reset}) | "
    "周 {weekly_percent}% ({weekly_reset}) | "
    "月 {monthly_percent}% ({monthly_reset})"
)

_SECTIONS = ("rolling", "weekly", "monthly")
_FIELDS = ("percent", "reset", "status")
_MISSING = "—"


def fmt_reset(u: Usage) -> str:
    """倒计时展示：优先格式化秒数，否则使用 DOM 兜底文本。"""
    sec = u.reset_in_sec
    if sec is None:
        return u.reset_text or "?"
    if sec < 0:
        sec = 0
    days, rem = divmod(sec, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days > 0:
        return f"{days}d{hours}h"
    if hours > 0:
        return f"{hours}h{minutes}m" if minutes else f"{hours}h"
    return f"{minutes}m"


class _SafeDict(dict):
    """让未知占位符保留原样，便于发现模板拼写错误。"""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _build_values(usages: dict[str, Usage]) -> _SafeDict:
    values: dict[str, str] = {}
    for section in _SECTIONS:
        usage = usages.get(section)
        if usage is None:
            for field in _FIELDS:
                values[f"{section}_{field}"] = _MISSING
        else:
            values[f"{section}_percent"] = str(usage.percent)
            values[f"{section}_reset"] = fmt_reset(usage)
            values[f"{section}_status"] = usage.status or _MISSING
    return _SafeDict(values)


def validate_template(template: str) -> None:
    """验证模板语法；未知的简单占位符仍被允许并保留。"""
    probe = _SafeDict({f"{s}_{f}": "0" for s in _SECTIONS for f in _FIELDS})
    try:
        template.format_map(probe)
    except (ValueError, IndexError, AttributeError, TypeError) as exc:
        raise ValueError(str(exc)) from exc


def build_data(
    usages: dict[str, Usage], data_template: str = DEFAULT_DATA_TEMPLATE
) -> str:
    """按指定模板渲染 data 字段。"""
    values = _build_values(usages)
    try:
        return data_template.format_map(values)
    except (ValueError, IndexError, AttributeError, TypeError):
        return DEFAULT_DATA_TEMPLATE.format_map(values)
