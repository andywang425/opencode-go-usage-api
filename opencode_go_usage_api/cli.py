"""CLI 入口：uv run opencode-go-usage-api 启动 HTTPS API。"""

from __future__ import annotations

import uvicorn

from opencode_go_usage_api.config import HOST, PORT, SSL_CERTFILE, SSL_KEYFILE


def main() -> None:
    uvicorn.run("opencode_go_usage_api:app", host=HOST, port=PORT, ssl_certfile=SSL_CERTFILE, ssl_keyfile=SSL_KEYFILE)


if __name__ == "__main__":
    main()
