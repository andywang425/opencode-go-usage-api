"""FastAPI 应用工厂。"""

from __future__ import annotations

import hmac
from collections.abc import Callable

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from .config import AccountConfig, AppConfig, FetchConfig
from .service import build_response

ResponseBuilder = Callable[[AccountConfig, FetchConfig, str], dict]


def create_app(
    config: AppConfig, response_builder: ResponseBuilder = build_response
) -> FastAPI:
    """使用已校验配置创建应用，便于启动和测试共用同一条路径。"""
    app = FastAPI(title="OpenCode Go Usage API", docs_url=None, redoc_url=None)

    def require_token(authorization: str = Header(default="")) -> None:
        expected = f"Bearer {config.server.api_token}"
        if not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="未授权")

    def response_for(account: AccountConfig) -> JSONResponse:
        return JSONResponse(
            response_builder(
                account, config.fetch, config.response.data_template
            )
        )

    @app.get("/usage", dependencies=[Depends(require_token)])
    def default_usage() -> JSONResponse:
        return response_for(config.accounts[config.default_account])

    @app.get("/usage/{account_id}", dependencies=[Depends(require_token)])
    def account_usage(account_id: str) -> JSONResponse:
        account = config.accounts.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="账号不存在")
        return response_for(account)

    @app.get("/health")
    def health() -> dict:
        """存活检查不鉴权、不抓取，也不检查上游账号状态。"""
        return {"status": "ok"}

    return app
