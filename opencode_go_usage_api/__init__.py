"""OpenCode Go 多账号用量 API。"""

from __future__ import annotations

from typing import Any

__all__ = ["app"]


def __getattr__(name: str) -> Any:
    """兼容 ``uvicorn opencode_go_usage_api:app``，并保持普通导入无副作用。"""
    if name != "app":
        raise AttributeError(name)

    from .app import create_app
    from .config import load_config

    application = create_app(load_config())
    globals()["app"] = application
    return application
