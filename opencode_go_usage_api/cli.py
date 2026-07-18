"""CLI 入口：读取 config.toml 并启动 API。"""

from __future__ import annotations

import sys

import uvicorn

from .app import create_app
from .config import ConfigError, load_config


def main() -> None:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    uvicorn.run(
        create_app(config),
        host=config.server.host,
        port=config.server.port,
        ssl_certfile=config.server.ssl_certfile,
        ssl_keyfile=config.server.ssl_keyfile,
    )


if __name__ == "__main__":
    main()
