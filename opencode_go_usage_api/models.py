"""数据结构。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Usage:
    """单项用量：已用百分比 + 距下次重置的秒数 + 状态。

    内联 JSON 路径填 reset_in_sec（精确秒数）；DOM 兜底路径拿不到秒数，
    填 reset_text（页面上「重置于 X 天 Y 小时」原文）由 fmt_reset 直接展示。
    """

    percent: int
    reset_in_sec: int | None
    status: str | None
    reset_text: str | None = None
