from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from opencode_go_usage_api.config import ConfigError, load_config


VALID_CONFIG = """
[server]
api_token = "api-secret"

[account]
default = "Main"

[accounts.Main]
auth_cookie = "main-cookie"
workspace_id = "wrk_main"

[accounts.backup-2]
auth_cookie = "backup-cookie"
workspace_id = "wrk_backup"
"""


def write_config(tmp_path: Path, content: str = VALID_CONFIG) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(content, encoding="utf-8")
    return path


def test_loads_multiple_accounts_and_defaults(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path))

    assert config.default_account == "Main"
    assert list(config.accounts) == ["Main", "backup-2"]
    assert config.accounts["Main"].auth_cookie == "main-cookie"
    assert config.accounts["backup-2"].workspace_url.endswith("/wrk_backup/go")
    assert config.fetch.timeout == 10
    assert config.server.port == 18443


def test_rejects_unknown_fields(tmp_path: Path) -> None:
    content = VALID_CONFIG.replace(
        'api_token = "api-secret"',
        'api_token = "api-secret"\napi_tokne = "typo"',
    )

    with pytest.raises(ConfigError, match="server 包含未知字段：api_tokne"):
        load_config(write_config(tmp_path, content))


def test_rejects_missing_default_account(tmp_path: Path) -> None:
    content = VALID_CONFIG.replace('default = "Main"', 'default = "missing"')

    with pytest.raises(ConfigError, match="默认账号 'missing' 不存在"):
        load_config(write_config(tmp_path, content))


@pytest.mark.parametrize("account_id", ["has space", "slash/name", "中文", "_leading"])
def test_rejects_non_url_safe_account_ids(
    tmp_path: Path, account_id: str
) -> None:
    content = VALID_CONFIG.replace("[accounts.Main]", f'[accounts."{account_id}"]')

    with pytest.raises(ConfigError, match="账号 ID .* 非法"):
        load_config(write_config(tmp_path, content))


def test_requires_both_tls_paths(tmp_path: Path) -> None:
    content = VALID_CONFIG.replace(
        'api_token = "api-secret"',
        'api_token = "api-secret"\nssl_certfile = "certs/cert.pem"',
    )

    with pytest.raises(ConfigError, match="必须同时配置或同时留空"):
        load_config(write_config(tmp_path, content))


def test_rejects_invalid_data_template(tmp_path: Path) -> None:
    content = VALID_CONFIG + '\n[response]\ndata_template = "broken {"\n'

    with pytest.raises(ConfigError, match="response.data_template 模板非法"):
        load_config(write_config(tmp_path, content))


def test_documented_uvicorn_app_target_loads_config_from_cwd(tmp_path: Path) -> None:
    write_config(tmp_path)
    code = (
        "import os, sys; "
        "os.chdir(sys.argv[1]); "
        "import opencode_go_usage_api; "
        "print(type(opencode_go_usage_api.app).__name__)"
    )

    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "FastAPI"
