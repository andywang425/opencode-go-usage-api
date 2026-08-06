"""OpenCode Go multi-account usage API."""

from __future__ import annotations

from typing import Any

__all__ = ["app"] # type: ignore


def __getattr__(name: str) -> Any:
    """Support ``uvicorn opencode_go_usage_api:app`` while keeping plain imports side-effect free."""
    if name != "app":
        raise AttributeError(name)

    from .app import create_app
    from .config import load_config

    application = create_app(load_config())
    globals()["app"] = application
    return application
