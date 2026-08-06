"""Parsing: inline JSON as the primary path, DOM as the fallback.

Inline data looks like:
  rollingUsage: $R[31] = { status: "ok", resetInSec: 18000, usagePercent: 0 }
The three keys have fixed names, but the value blocks are not strict JSON (they
contain !0, new Date(), etc.), so each usage block is matched separately with a
regex that extracts the three numeric fields regardless of field order.
"""

from __future__ import annotations

import re

from .models import Usage

_USAGE_KEYS = {
    "rolling": "rollingUsage",
    "weekly": "weeklyUsage",
    "monthly": "monthlyUsage",
}

# A usage block's value follows `<key>:` directly, like `<key>:$R[31]={...}` or `<key>:{...}`.
# On the real page `monthlyUsage` appears twice: the actual usage block `<key>:$R[n]={...}`,
# and a `:null` entry inside the subscription-info block (value is null, not usage data).
# Only match the former and skip `:null`; otherwise roughly half of requests would latch
# onto an unrelated empty {} block after the null and lose resetInSec.
# Between `:` and `{` there may be a `$R[<number>=` hydration prefix, or just whitespace.
_USAGE_VALUE_RE = r"\s*:\s*(?:\$R\[\d+\]\s*=\s*)?\{"


def _extract_usage_block(html: str, key: str) -> str | None:
    """Slice out the {...} block text for a given usage key from the inline script."""
    # Locate `<key>:` followed by `{` (optionally after a $R[n]= prefix), then brace-balance to the end.
    m = re.search(re.escape(key) + _USAGE_VALUE_RE, html)
    if not m:
        return None
    brace_start = m.end() - 1  # lands on the opening brace {
    depth = 0
    for i in range(brace_start, len(html)):
        c = html[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return html[brace_start: i + 1]
    return None


def _parse_int_field(block: str, field: str) -> int | None:
    m = re.search(re.escape(field) + r"\s*:\s*(-?\d+)", block)
    return int(m.group(1)) if m else None


def _parse_str_field(block: str, field: str) -> str | None:
    m = re.search(re.escape(field) + r'\s*:\s*"([^"]*)"', block)
    return m.group(1) if m else None


def parse_inline(html: str) -> dict[str, Usage]:
    """Parse the three usage groups from the inline JSON region; missing items are omitted."""
    result: dict[str, Usage] = {}
    for name, key in _USAGE_KEYS.items():
        block = _extract_usage_block(html, key)
        if not block:
            continue
        percent = _parse_int_field(block, "usagePercent")
        if percent is None:
            continue
        result[name] = Usage(
            percent=percent,
            reset_in_sec=_parse_int_field(block, "resetInSec"),
            status=_parse_str_field(block, "status"),
        )
    return result


# When the inline region's structure changes and nothing can be extracted, fall back to
# grabbing percentages from the rendered DOM. The DOM has no precise resetInSec, but the
# reset-time span carries the raw "resets in X days Y hours" text, which is returned
# verbatim (not re-parsed into seconds, not language-dependent); only the percentage
# still comes from the DOM.
#
# The page always contains 3 data-slot="usage-item" blocks in rolling -> weekly -> monthly
# order, located by structure rather than text labels, so it is locale-independent.

_DOM_ORDER = ("rolling", "weekly", "monthly")

_USAGE_ITEM_RE = re.compile(r'data-slot="usage-item"')


def _clean_reset_text(raw: str) -> str | None:
    """Strip SSR comments and collapse whitespace from the reset-time span for display."""
    cleaned = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def parse_dom(html: str) -> dict[str, Usage]:
    result: dict[str, Usage] = {}
    item_starts = [m.start() for m in _USAGE_ITEM_RE.finditer(html)]
    for idx, name in enumerate(_DOM_ORDER):
        if idx >= len(item_starts):
            break
        # Slice from the current item to the next one (or +800 chars as a fallback)
        seg_start = item_starts[idx]
        seg_end = item_starts[idx + 1] if idx + 1 < len(item_starts) else seg_start + 800
        segment = html[seg_start:seg_end]
        # Prefer the percentage from the usage-value slot
        m = re.search(r'data-slot="usage-value">\s*(?:<!--.*?-->)?\s*(\d+)', segment, re.S)
        if not m:
            # Fall back to the progress-bar width:N%
            m = re.search(r"width:\s*(\d+)%", segment)
        if not m:
            continue
        rt = re.search(r'data-slot="reset-time">\s*(.*?)</span>', segment, re.S)
        reset_text = _clean_reset_text(rt.group(1)) if rt else None
        result[name] = Usage(
            percent=int(m.group(1)),
            reset_in_sec=None,
            status=None,
            reset_text=reset_text,
        )
    return result


def parse_usage(html: str) -> dict[str, Usage]:
    """Inline first, DOM second; fill any item missing from inline with the DOM value."""
    inline = parse_inline(html)
    if len(inline) == 3:
        return inline
    dom = parse_dom(html)
    # Merge: inline wins, missing items are backfilled from the DOM
    merged = dict(dom)
    merged.update(inline)
    return merged


def is_no_subscription(html: str) -> bool:
    """Detect the "no Go subscription" page, the stable fallback when usage blocks are absent.

    The no-subscription page has neither inline usage objects nor DOM usage nodes, so
    parse_usage returns empty. At that point it must be distinguished from a genuinely
    expired cookie or a changed page structure: the no-subscription page has a prominent
    promo subscription section and its subscription status field is null.

    Primary signal: a "Subscribe to Go" button with data-slot="subscribe-button" exists
    (the subscribed page has a "Manage subscription" button without this slot). Backed up
    by an inline `lite: null`, to avoid an unrelated promo banner misfiring.
    """
    if 'data-slot="subscribe-button"' not in html:
        return False
    # lite: null appears in the billing block; the subscribed page has lite: {...} or a liteSubscriptionID
    return bool(re.search(r"lite\s*:\s*null", html)) and bool(
        re.search(r"liteSubscriptionID\s*:\s*null", html)
    )
