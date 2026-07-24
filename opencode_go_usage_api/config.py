"""从工作目录下的 config.toml 加载并校验服务配置。"""

from __future__ import annotations

import math
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import quote

from .formatter import DEFAULT_DATA_TEMPLATE, validate_template

CONFIG_FILENAME = "config.toml"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)

_ACCOUNT_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_MISSING = object()


class ConfigError(ValueError):
    """配置文件缺失、格式错误或字段校验失败。"""


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int
    api_token: str
    ssl_certfile: str | None
    ssl_keyfile: str | None


@dataclass(frozen=True)
class FetchConfig:
    timeout: float
    retries: int
    locale: str
    user_agent: str


@dataclass(frozen=True)
class ResponseConfig:
    data_template: str


@dataclass(frozen=True)
class AccountConfig:
    account_id: str
    auth_cookie: str
    workspace_id: str

    @property
    def workspace_url(self) -> str:
        workspace_id = quote(self.workspace_id, safe="")
        return f"https://opencode.ai/workspace/{workspace_id}/go"


@dataclass(frozen=True)
class AppConfig:
    server: ServerConfig
    fetch: FetchConfig
    response: ResponseConfig
    default_account: str
    accounts: Mapping[str, AccountConfig]


def _reject_unknown(table: Mapping[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise ConfigError(f"{context} 包含未知字段：{', '.join(unknown)}")


def _get_table(
    table: Mapping[str, Any], key: str, context: str, *, required: bool = True
) -> dict[str, Any]:
    value = table.get(key, _MISSING)
    if value is _MISSING:
        if required:
            raise ConfigError(f"缺少必填配置表 {context}.{key}")
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"{context}.{key} 必须是配置表")
    return value


def _get_string(
    table: Mapping[str, Any],
    key: str,
    context: str,
    *,
    default: object = _MISSING,
    allow_empty: bool = False,
) -> str:
    value = table.get(key, default)
    if value is _MISSING:
        raise ConfigError(f"缺少必填配置 {context}.{key}")
    if not isinstance(value, str):
        raise ConfigError(f"{context}.{key} 必须是字符串")
    if not allow_empty and not value:
        raise ConfigError(f"{context}.{key} 不能为空")
    return value


def _get_int(
    table: Mapping[str, Any], key: str, context: str, *, default: int
) -> int:
    value = table.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{context}.{key} 必须是整数")
    return value


def _get_number(
    table: Mapping[str, Any], key: str, context: str, *, default: float
) -> float:
    value = table.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{context}.{key} 必须是数字")
    result = float(value)
    if not math.isfinite(result):
        raise ConfigError(f"{context}.{key} 必须是有限数字")
    return result


def _optional_path(table: Mapping[str, Any], key: str, context: str) -> str | None:
    value = _get_string(table, key, context, default="", allow_empty=True)
    return value or None


def load_config(path: Path | None = None) -> AppConfig:
    """读取并严格校验一个 TOML 配置文件。"""
    if path is None:
        path = Path.cwd() / CONFIG_FILENAME
    try:
        with path.open("rb") as file:
            raw = tomllib.load(file)
    except FileNotFoundError as exc:
        raise ConfigError(f"配置文件不存在：{path}") from exc
    except OSError as exc:
        raise ConfigError(f"无法读取配置文件 {path}：{exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"TOML 格式错误：{exc}") from exc

    _reject_unknown(raw, {"server", "fetch", "response", "account", "accounts"}, "根配置")

    server_raw = _get_table(raw, "server", "根配置")
    _reject_unknown(
        server_raw,
        {"host", "port", "api_token", "ssl_certfile", "ssl_keyfile"},
        "server",
    )
    port = _get_int(server_raw, "port", "server", default=18443)
    if not 1 <= port <= 65535:
        raise ConfigError("server.port 必须在 1 到 65535 之间")
    ssl_certfile = _optional_path(server_raw, "ssl_certfile", "server")
    ssl_keyfile = _optional_path(server_raw, "ssl_keyfile", "server")
    if bool(ssl_certfile) != bool(ssl_keyfile):
        raise ConfigError("server.ssl_certfile 与 server.ssl_keyfile 必须同时配置或同时留空")
    server = ServerConfig(
        host=_get_string(server_raw, "host", "server", default="0.0.0.0"),
        port=port,
        api_token=_get_string(server_raw, "api_token", "server"),
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
    )

    fetch_raw = _get_table(raw, "fetch", "根配置", required=False)
    _reject_unknown(fetch_raw, {"timeout", "retries", "locale", "user_agent"}, "fetch")
    timeout = _get_number(fetch_raw, "timeout", "fetch", default=10.0)
    if timeout <= 0:
        raise ConfigError("fetch.timeout 必须大于 0")
    retries = _get_int(fetch_raw, "retries", "fetch", default=1)
    if retries < 0:
        raise ConfigError("fetch.retries 不能为负数")
    fetch = FetchConfig(
        timeout=timeout,
        retries=retries,
        locale=_get_string(fetch_raw, "locale", "fetch", default="zh"),
        user_agent=_get_string(
            fetch_raw, "user_agent", "fetch", default=DEFAULT_USER_AGENT
        ),
    )

    response_raw = _get_table(raw, "response", "根配置", required=False)
    _reject_unknown(response_raw, {"data_template"}, "response")
    data_template = _get_string(
        response_raw,
        "data_template",
        "response",
        default=DEFAULT_DATA_TEMPLATE,
        allow_empty=True,
    )
    data_template = data_template or DEFAULT_DATA_TEMPLATE
    try:
        validate_template(data_template)
    except ValueError as exc:
        raise ConfigError(f"response.data_template 模板非法：{exc}") from exc
    response = ResponseConfig(data_template=data_template)

    account_raw = _get_table(raw, "account", "根配置")
    _reject_unknown(account_raw, {"default"}, "account")
    default_account = _get_string(account_raw, "default", "account")

    accounts_raw = _get_table(raw, "accounts", "根配置")
    if not accounts_raw:
        raise ConfigError("accounts 至少需要配置一个账号")
    accounts: dict[str, AccountConfig] = {}
    for account_id, value in accounts_raw.items():
        context = f"accounts.{account_id}"
        if not _ACCOUNT_ID_RE.fullmatch(account_id):
            raise ConfigError(
                f"账号 ID {account_id!r} 非法：仅允许 1-64 位字母、数字、_、-，且首位须为字母或数字"
            )
        if not isinstance(value, dict):
            raise ConfigError(f"{context} 必须是配置表")
        _reject_unknown(value, {"auth_cookie", "workspace_id"}, context)
        accounts[account_id] = AccountConfig(
            account_id=account_id,
            auth_cookie=_get_string(value, "auth_cookie", context),
            workspace_id=_get_string(value, "workspace_id", context),
        )

    if default_account not in accounts:
        raise ConfigError(f"默认账号 {default_account!r} 不存在于 accounts")

    return AppConfig(
        server=server,
        fetch=fetch,
        response=response,
        default_account=default_account,
        accounts=MappingProxyType(accounts),
    )
