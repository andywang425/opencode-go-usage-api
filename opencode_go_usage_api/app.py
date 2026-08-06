"""FastAPI application factory."""

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
    """Auth failure, returned as JSON by the global exception handler."""


def create_app(
    config: AppConfig, response_builder: ResponseBuilder = build_response
) -> FastAPI:
    """Build the app from an already-validated config, so startup and tests share one path."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # One persistent Client per account for the app's lifetime, reusing connection pool / TLS session
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
        # The header is decoded as latin-1 and may contain non-ASCII bytes, which
        # compare_digest does not accept (raises TypeError -> 500). Encode both
        # sides as bytes so the comparison is always safe.
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
                {"success": False, "reason": "account not found", "data": ""},
                status_code=404,
            )
        return response_for(account)

    @app.get("/health")
    def health() -> dict:
        """Liveness probe: no auth, no fetch, no upstream account check."""
        return {"status": "ok"}

    @app.exception_handler(UnauthorizedError)
    def handle_unauthorized(request: Request, exc: UnauthorizedError) -> JSONResponse:
        return JSONResponse(
            {"success": False, "reason": "unauthorized", "data": ""},
            status_code=401,
        )

    return app
