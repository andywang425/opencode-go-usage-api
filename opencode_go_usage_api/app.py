"""FastAPI 应用。"""

from __future__ import annotations

import hmac

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from .config import API_TOKEN
from .service import build_response

app = FastAPI(title="OpenCode Go Usage API", docs_url=None, redoc_url=None)


def require_token(authorization: str = Header(default="")) -> None:
    """校验 Authorization: Bearer <token>。"""
    if not API_TOKEN:
        raise HTTPException(status_code=500, detail="服务端未配置 API_TOKEN")
    expected = f"Bearer {API_TOKEN}"
    # 常数时间比较，避免时序侧信道
    if not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="未授权")


@app.get("/usage", dependencies=[Depends(require_token)])
def usage() -> JSONResponse:
    return JSONResponse(build_response())


@app.get("/health")
def health() -> dict:
    """存活检查，免鉴权，不抓取、不暴露数据。"""
    return {"status": "ok"}
