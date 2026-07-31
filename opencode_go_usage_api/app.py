"""FastAPI 应用工厂。"""

from __future__ import annotations

import hmac
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import httpx2
from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse

from .config import AccountConfig, AppConfig, FetchConfig
from .fetcher import create_client
from .service import build_response

ResponseBuilder = Callable[[AccountConfig, FetchConfig, str, httpx2.Client], dict]


class UnauthorizedError(Exception):
    """鉴权失败，由全局异常处理器统一返回 JSON。"""


def create_app(
    config: AppConfig, response_builder: ResponseBuilder = build_response
) -> FastAPI:
    """使用已校验配置创建应用，便于启动和测试共用同一条路径。"""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # 每个账号一个应用生命周期内常驻的 Client，复用连接池/TLS 会话
        app.state.http_clients = {
            account_id: create_client(account, config.fetch)
            for account_id, account in config.accounts.items()
        }
        try:
            yield
        finally:
            for client in app.state.http_clients.values():
                client.close()

    app = FastAPI(
        title="OpenCode Go Usage API", docs_url=None, redoc_url=None, lifespan=lifespan
    )

    def require_token(authorization: str = Header(default="")) -> None:
        expected = f"Bearer {config.server.api_token}"
        # 请求头按 latin-1 解码可能含非 ASCII 字符，而 compare_digest 不支持
        # 非 ASCII 字符串（抛 TypeError 变成 500），因此统一编码为 bytes 再比较。
        if not hmac.compare_digest(
            authorization.encode("utf-8"), expected.encode("utf-8")
        ):
            raise UnauthorizedError()

    def response_for(account: AccountConfig) -> JSONResponse:
        return JSONResponse(
            response_builder(
                account,
                config.fetch,
                config.response.data_template,
                app.state.http_clients[account.account_id],
            )
        )

    @app.get("/usage", dependencies=[Depends(require_token)])
    def default_usage() -> JSONResponse:
        return response_for(config.accounts[config.default_account])

    @app.get("/usage/{account_id}", dependencies=[Depends(require_token)])
    def account_usage(account_id: str) -> JSONResponse:
        account = config.accounts.get(account_id)
        if account is None:
            return JSONResponse(
                {"success": False, "reason": "账号不存在", "data": ""},
                status_code=404,
            )
        return response_for(account)

    @app.get("/health")
    def health() -> dict:
        """存活检查不鉴权、不抓取，也不检查上游账号状态。"""
        return {"status": "ok"}

    @app.exception_handler(UnauthorizedError)
    def handle_unauthorized(request: Request, exc: UnauthorizedError) -> JSONResponse:
        return JSONResponse(
            {"success": False, "reason": "未授权", "data": ""},
            status_code=401,
        )

    return app
