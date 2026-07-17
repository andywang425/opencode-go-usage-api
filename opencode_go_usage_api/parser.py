"""解析：内联 JSON 主用，DOM 兜底。

内联数据形如：
  rollingUsage: $R[31] = { status: "ok", resetInSec: 18000, usagePercent: 0 }
三个键名固定，值块非严格 JSON（含 !0、new Date() 等），因此对每个用量块
单独用正则抽取三个数值字段，互不依赖字段出现顺序。
"""

from __future__ import annotations

import re

from .models import Usage

_USAGE_KEYS = {
    "rolling": "rollingUsage",
    "weekly": "weeklyUsage",
    "monthly": "monthlyUsage",
}

# 用量块的值紧跟在 `<key>:` 之后，形如 `<key>:$R[31]={...}` 或 `<key>:{...}`。
# 真实页面里 `monthlyUsage` 会出现两次：真正的用量块 `<key>:$R[n]={...}`，
# 以及订阅信息块里的 `<key>:null`（值是 null，非用量数据）。只匹配前者，
# 跳过 `:null`，否则约一半请求会错抓到 null 后面无关的空 {} 块、丢掉 resetInSec。
# `:` 与 `{` 之间允许出现 `$R[数字]=` 这种 hydration 赋值前缀，或仅空白。
_USAGE_VALUE_RE = r"\s*:\s*(?:\$R\[\d+\]\s*=\s*)?\{"


def _extract_usage_block(html: str, key: str) -> str | None:
    """从内联脚本里截出某个用量键对应的 {...} 块文本。"""
    # 定位 `<key>:` 之后紧跟 `{`（可带 $R[n]= 前缀）的位置，再做花括号配平找块结尾。
    m = re.search(re.escape(key) + _USAGE_VALUE_RE, html)
    if not m:
        return None
    brace_start = m.end() - 1  # 落在开括号 {
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
    """从内联 JSON 区解析三组用量；缺失的项不放入结果。"""
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


# 当内联区结构变化抽不到时，退回渲染后 DOM 抓百分比。
# DOM 里没有精确 resetInSec，但 reset-time span 有「重置于 X 天 Y 小时」原文，
# 直接抠出来原文返回（不反解析为秒、不依赖语言），仅百分比仍由 DOM 提供。

_DOM_LABELS = {
    "rolling": "滚动用量",
    "weekly": "每周用量",
    "monthly": "每月用量",
}


def _clean_reset_text(raw: str) -> str | None:
    """把 reset-time span 内文去掉 SSR 注释、压空白，得到展示用文本。"""
    cleaned = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def parse_dom(html: str) -> dict[str, Usage]:
    result: dict[str, Usage] = {}
    for name, label in _DOM_LABELS.items():
        # 在标签文本之后就近找 usage-value 里的百分比数字
        label_pos = html.find(label)
        if label_pos == -1:
            continue
        segment = html[label_pos: label_pos + 400]
        m = re.search(r'data-slot="usage-value">\s*(?:<!--.*?-->)?\s*(\d+)', segment, re.S)
        if not m:
            # 退一步：从 progress-bar 的 width:N% 抽
            m = re.search(r"width:\s*(\d+)%", segment)
        if not m:
            continue
        # 同一 usage-item 内就近抠 reset-time 原文（无则留空，fmt_reset 会给 ?）
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
    """先内联后 DOM；对内联缺失的单项用 DOM 补齐。"""
    inline = parse_inline(html)
    if len(inline) == 3:
        return inline
    dom = parse_dom(html)
    # 合并：内联优先，缺的项用 DOM 补
    merged = dict(dom)
    merged.update(inline)
    return merged


def is_no_subscription(html: str) -> bool:
    """识别「无 Go 订阅」页面：用量块整体缺失时的稳定兜底判定。

    无订阅页既没有内联用量对象，也没有
    DOM 用量节点，parse_usage 会返回空。此时需与真正的 cookie 失效/结构变更
    区分：无订阅页有明显的促销订阅区，且订阅状态字段为 null。

    主判据：DOM 存在「订阅 Go」按钮 data-slot="subscribe-button"（有订阅页
    对应的是「管理订阅」按钮，无此 slot）。辅以内联 lite: null 印证，避免
    某个无关促销横幅误触发。
    """
    if 'data-slot="subscribe-button"' not in html:
        return False
    # lite: null 出现在 billing 块；有订阅页此处是 lite: {...} 或带 liteSubscriptionID
    return bool(re.search(r"lite\s*:\s*null", html)) and bool(
        re.search(r"liteSubscriptionID\s*:\s*null", html)
    )
