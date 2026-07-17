# CLAUDE.md

## 项目概述

被访问时实时抓取一次 OpenCode Go 工作区页面、解析用量并返回 JSON 的 HTTPS API（FastAPI）。用于接入 CC Switch 软件查看剩余用量。所有逻辑集中在 `opencode_go_usage_api/` 包内，CLI 入口为 `opencode_go_usage_api/cli.py`。

## 常用命令

```bash
uv sync                                      # 按 pyproject.toml 创建 .venv 并装依赖（uv.lock 锁定版本，应提交）
uv run uvicorn opencode_go_usage_api:app --reload   # 本地开发（HTTP，免证书）
uv run opencode-go-usage-api                        # CLI 入口：读取 .env 启动 HTTPS（生产用）
./run.sh                                     # 生产启动：source .env 后调用 CLI 入口（systemd 调用）
./gen-cert.sh <公网IP>                        # 生成自签证书到 certs/（10 年）
curl -k https://127.0.0.1:<PORT>/health      # 存活检查（免鉴权）
curl -k -H "Authorization: Bearer <TOKEN>" https://127.0.0.1:<PORT>/usage   # 用量（需鉴权）
```

无测试套件、无 linter 配置。

## 配置

全部配置走 `.env`（由 `opencode_go_usage_api/config.py` 中 `load_dotenv()` 读入），模板见 [.env.example](.env.example)。

## 部署

服务文件 [opencode-go-usage-api.service](opencode-go-usage-api.service)，部署步骤见 [README.md](README.md#部署步骤)。
