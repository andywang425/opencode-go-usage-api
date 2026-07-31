from __future__ import annotations

from types import MappingProxyType

import httpx2
from fastapi.testclient import TestClient

from opencode_go_usage_api.app import create_app
from opencode_go_usage_api.config import (
    AccountConfig,
    AppConfig,
    FetchConfig,
    ResponseConfig,
    ServerConfig,
)


def make_config() -> AppConfig:
    accounts = {
        "Main": AccountConfig("Main", "main-cookie", "wrk_main"),
        "backup": AccountConfig("backup", "backup-cookie", "wrk_backup"),
    }
    return AppConfig(
        server=ServerConfig("127.0.0.1", 18443, "api-secret", None, None),
        fetch=FetchConfig(10, 1, "zh", "test-agent"),
        response=ResponseConfig("{rolling_percent}"),
        default_account="Main",
        accounts=MappingProxyType(accounts),
    )


AUTH_HEADER = {"Authorization": "Bearer api-secret"}


def test_default_and_named_routes_select_isolated_accounts() -> None:
    calls: list[tuple[str, str, str]] = []

    def fake_builder(account, fetch_config, data_template, http_client):
        calls.append((account.account_id, account.auth_cookie, account.workspace_id))
        return {"success": True, "reason": "", "data": account.account_id}

    with TestClient(create_app(make_config(), fake_builder)) as client:
        default_response = client.get("/usage", headers=AUTH_HEADER)
        backup_response = client.get("/usage/backup", headers=AUTH_HEADER)

    assert default_response.status_code == 200
    assert default_response.json()["data"] == "Main"
    assert backup_response.status_code == 200
    assert backup_response.json()["data"] == "backup"
    assert calls == [
        ("Main", "main-cookie", "wrk_main"),
        ("backup", "backup-cookie", "wrk_backup"),
    ]


def test_lifespan_creates_per_account_clients_and_closes_them_on_shutdown() -> None:
    """每个账号一个常驻 Client 挂在 app.state，路由拿到对应实例，关停时全部关闭。"""
    seen_clients: list[httpx2.Client] = []

    def fake_builder(account, fetch_config, data_template, http_client):
        seen_clients.append(http_client)
        return {"success": True, "reason": "", "data": ""}

    app = create_app(make_config(), fake_builder)
    with TestClient(app) as client:
        client.get("/usage", headers=AUTH_HEADER)
        client.get("/usage/backup", headers=AUTH_HEADER)
        clients = dict(app.state.http_clients)

    assert set(clients) == {"Main", "backup"}
    assert seen_clients == [clients["Main"], clients["backup"]]
    assert clients["Main"] is not clients["backup"]
    assert all(c.is_closed for c in clients.values())


def test_account_ids_are_case_sensitive() -> None:
    with TestClient(create_app(make_config())) as client:
        response = client.get("/usage/main", headers=AUTH_HEADER)

    assert response.status_code == 404
    assert response.json() == {"success": False, "reason": "账号不存在", "data": ""}


def test_unknown_account_requires_auth_before_404() -> None:
    with TestClient(create_app(make_config())) as client:
        response = client.get("/usage/missing")

    assert response.status_code == 401
    assert response.json() == {"success": False, "reason": "未授权", "data": ""}


def test_non_ascii_authorization_returns_401_not_500() -> None:
    """请求头按 latin-1 解码可能含非 ASCII 字符，不应触发 TypeError 变成 500。"""
    with TestClient(create_app(make_config())) as client:
        # 以 bytes 形式直接构造含非 ASCII 字节的头，绕过客户端层的 ASCII 编码检查
        response = client.get(
            "/usage", headers={b"Authorization": "Bearer café".encode("latin-1")}
        )

    assert response.status_code == 401
    assert response.json() == {"success": False, "reason": "未授权", "data": ""}


def test_business_failure_keeps_http_200() -> None:
    def failed_builder(account, fetch_config, data_template, http_client):
        return {"success": False, "reason": "抓取失败：timeout", "data": ""}

    with TestClient(create_app(make_config(), failed_builder)) as client:
        response = client.get("/usage/backup", headers=AUTH_HEADER)

    assert response.status_code == 200
    assert response.json()["success"] is False


def test_health_is_public_and_does_not_fetch() -> None:
    def unexpected_builder(account, fetch_config, data_template, http_client):
        raise AssertionError("health must not fetch")

    with TestClient(create_app(make_config(), unexpected_builder)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
