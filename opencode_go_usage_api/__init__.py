"""OpenCode Go 用量抓取 API。

被访问时实时抓取一次 OpenCode Go 工作区页面，解析用量数据，返回 JSON。

响应格式：
    {
      "success": bool,          # 解析出至少一组用量则 true（单项只要解析到用量百分比即算成功，重置时间允许解析失败；一项都没解析出才 false）
      "reason": str,            # success 为 false 时说明原因
      "data": str               # 紧凑单行：滚动 0% (5h) | 周 7% (3d16h) | 月 3% (29d22h)
    }

数据来源：
    GET https://opencode.ai/workspace/<WORKSPACE_ID>/go
    需带 Cookie：auth、oc_locale
"""


from __future__ import annotations

from .app import app

__all__ = ["app"]
