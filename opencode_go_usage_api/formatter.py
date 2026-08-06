"""Usage response formatting."""

from __future__ import annotations

from .models import Usage

DEFAULT_DATA_TEMPLATE = (
    "Rolling {rolling_percent}% ({rolling_reset}) | "
    "Weekly {weekly_percent}% ({weekly_reset}) | "
    "Monthly {monthly_percent}% ({monthly_reset})"
)

_SECTIONS = ("rolling", "weekly", "monthly")
_FIELDS = ("percent", "reset", "status")
_MISSING = "—"


def fmt_reset(u: Usage) -> str:
    """Countdown display: prefer formatting the seconds, otherwise fall back to the DOM text."""
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
    """Leave unknown placeholders intact so template typos are easy to spot."""

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
    """Validate template syntax; unknown simple placeholders are still allowed and preserved."""
    probe = _SafeDict({f"{s}_{f}": "0" for s in _SECTIONS for f in _FIELDS})
    try:
        template.format_map(probe)
    except (ValueError, IndexError, AttributeError, TypeError) as exc:
        raise ValueError(str(exc)) from exc


def build_data(
    usages: dict[str, Usage], data_template: str = DEFAULT_DATA_TEMPLATE
) -> str:
    """Render the data field using the given template."""
    values = _build_values(usages)
    try:
        return data_template.format_map(values)
    except (ValueError, IndexError, AttributeError, TypeError):
        return DEFAULT_DATA_TEMPLATE.format_map(values)
