# CLAUDE.md

## 项目概述

被访问时实时抓取 OpenCode Go 工作区页面、解析用量并返回 JSON 的 HTTPS API（FastAPI）。支持多个命名账号，所有逻辑集中在 `opencode_go_usage_api/` 包内，CLI 入口为 `opencode_go_usage_api/cli.py`。

## 常用命令

```bash
uv sync
uv run uvicorn opencode_go_usage_api:app --reload
uv run opencode-go-usage-api
uv run pytest
./run.sh
./gen-cert.sh <公网IP>
curl -k https://127.0.0.1:<PORT>/health
curl -k -H "Authorization: Bearer <TOKEN>" https://127.0.0.1:<PORT>/usage
curl -k -H "Authorization: Bearer <TOKEN>" https://127.0.0.1:<PORT>/usage/<ACCOUNT_ID>
```

## 配置

服务固定读取当前工作目录下的 `config.toml`，模板见 `config.example.toml`。配置包含 API Token、监听/TLS、全局抓取与响应设置，以及 `[accounts.<id>]` 多账号凭据。配置在启动时严格校验，修改后需重启。

## 部署

服务文件 `opencode-go-usage-api.service`，部署步骤见 `README.md`。

## 隐私保护

- 测试用例中不允许出现个人信息，账户标识、customerID、subscriptionID、邮箱等必须替换为虚构值。
- `config.toml` 含真实凭据，不得提交，其具体内容不允许以任何形式出现在 Agent 的上下文中。
