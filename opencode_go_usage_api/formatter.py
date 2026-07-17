"""格式化。"""

from __future__ import annotations

import sys

from .config import DATA_TEMPLATE, DEFAULT_DATA_TEMPLATE
from .models import Usage

# data 模板的用量分组与字段：占位符形如 {rolling_percent}、{weekly_reset}、{monthly_status}
_SECTIONS = ("rolling", "weekly", "monthly")
_FIELDS = ("percent", "reset", "status")
# 整项或单字段缺失时的占位兜底符
_MISSING = "—"


def fmt_reset(u: Usage) -> str:
    """倒计时展示：内联有秒则格式化为 3d16h/5h/30m；否则用 DOM 兜底原文；都没有给 ?。"""
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
    """format_map 用：未知占位符原样保留成 {name}，便于发现拼写错误而非静默丢数据。"""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _build_values(usages: dict[str, Usage]) -> _SafeDict:
    """把三组用量摊平成模板占位符（值统一为字符串），整项或字段缺失以 — 兜底。"""
    values: dict[str, str] = {}
    for section in _SECTIONS:
        u = usages.get(section)
        if u is None:
            for field in _FIELDS:
                values[f"{section}_{field}"] = _MISSING
        else:
            values[f"{section}_percent"] = str(u.percent)
            values[f"{section}_reset"] = fmt_reset(u)
            values[f"{section}_status"] = u.status or _MISSING
    return _SafeDict(values)


def build_data(usages: dict[str, Usage]) -> str:
    """按 DATA_TEMPLATE 渲染 data 字段。

    默认模板格式：滚动 0% (5h) | 周 7% (3d16h) | 月 3% (29d22h)。
    模板语法非法（花括号不配对、用了 {0} 位置参数、非法格式说明符等）时回退
    默认模板，保证对外接口不因用户模板而 500；未知占位符由 _SafeDict 原样保留。
    """
    values = _build_values(usages)
    try:
        return DATA_TEMPLATE.format_map(values)
    except (ValueError, IndexError, AttributeError, TypeError):
        return DEFAULT_DATA_TEMPLATE.format_map(values)


def _probe_template() -> None:
    """模块加载时试渲染一次 DATA_TEMPLATE，非法则告警（运行时仍会兜底回退默认）。

    只在进程启动 import 时执行一次，警告进 stderr/journalctl，便于部署者改完
    模板重启即发现问题，而非等到 data 静默变回默认格式才察觉。
    """
    if DATA_TEMPLATE == DEFAULT_DATA_TEMPLATE:
        return
    probe = _SafeDict({f"{s}_{f}": "0" for s in _SECTIONS for f in _FIELDS})
    try:
        DATA_TEMPLATE.format_map(probe)
    except (ValueError, IndexError, AttributeError, TypeError) as exc:
        print(
            f"警告：DATA_TEMPLATE 模板非法（{exc}），/usage 的 data 将回退默认格式",
            file=sys.stderr,
        )


_probe_template()
