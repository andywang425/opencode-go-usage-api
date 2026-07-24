from __future__ import annotations

from types import MappingProxyType

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

    def fake_builder(account, fetch_config, data_template):
        calls.append((account.account_id, account.auth_cookie, account.workspace_id))
        return {"success": True, "reason": "", "data": account.account_id}

    client = TestClient(create_app(make_config(), fake_builder))

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


def test_account_ids_are_case_sensitive() -> None:
    client = TestClient(create_app(make_config()))

    response = client.get("/usage/main", headers=AUTH_HEADER)

    assert response.status_code == 404
    assert response.json() == {"success": False, "reason": "账号不存在", "data": ""}


def test_unknown_account_requires_auth_before_404() -> None:
    client = TestClient(create_app(make_config()))

    response = client.get("/usage/missing")

    assert response.status_code == 401
    assert response.json() == {"success": False, "reason": "未授权", "data": ""}


def test_non_ascii_authorization_returns_401_not_500() -> None:
    """请求头按 latin-1 解码可能含非 ASCII 字符，不应触发 TypeError 变成 500。"""
    client = TestClient(create_app(make_config()))

    # 以 bytes 形式直接构造含非 ASCII 字节的头，绕过客户端层的 ASCII 编码检查
    response = client.get(
        "/usage", headers={b"Authorization": "Bearer café".encode("latin-1")}
    )

    assert response.status_code == 401
    assert response.json() == {"success": False, "reason": "未授权", "data": ""}


def test_business_failure_keeps_http_200() -> None:
    def failed_builder(account, fetch_config, data_template):
        return {"success": False, "reason": "抓取失败：timeout", "data": ""}

    client = TestClient(create_app(make_config(), failed_builder))

    response = client.get("/usage/backup", headers=AUTH_HEADER)

    assert response.status_code == 200
    assert response.json()["success"] is False


def test_health_is_public_and_does_not_fetch() -> None:
    def unexpected_builder(account, fetch_config, data_template):
        raise AssertionError("health must not fetch")

    client = TestClient(create_app(make_config(), unexpected_builder))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
