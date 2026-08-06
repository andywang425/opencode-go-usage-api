"""Data structures."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Usage:
    """A single usage entry: percent used + seconds until next reset + status.

    The inline JSON path fills reset_in_sec (exact seconds); the DOM fallback path
    can't get the seconds, so it fills reset_text (the raw "resets in X days Y hours"
    text from the page) which fmt_reset displays directly.
    """

    percent: int
    reset_in_sec: int | None
    status: str | None
    reset_text: str | None = None
