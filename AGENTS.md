# CLAUDE.md

## Project overview

An HTTPS API (FastAPI) that live-scrapes the OpenCode Go workspace page on each request, parses usage, and returns JSON. It supports multiple named accounts; all logic lives in the `opencode_go_usage_api/` package, and the CLI entrypoint is `opencode_go_usage_api/cli.py`.

## Common commands

```bash
uv sync
uv run uvicorn opencode_go_usage_api:app --reload
uv run opencode-go-usage-api
uv run pytest
./run.sh
./gen-cert.sh <PUBLIC_IP>
curl -k https://127.0.0.1:<PORT>/health
curl -k -H "Authorization: Bearer <TOKEN>" https://127.0.0.1:<PORT>/usage
curl -k -H "Authorization: Bearer <TOKEN>" https://127.0.0.1:<PORT>/usage/<ACCOUNT_ID>
```

## Configuration

The service always reads `config.toml` from the current working directory; see `config.example.toml` for a template. The config holds the API token, listen/TLS settings, global fetch and response settings, and the `[accounts.<id>]` multi-account credentials. It is validated strictly at startup, and a restart is required after edits.

## Deployment

The systemd unit is `opencode-go-usage-api.service`; deployment steps are in `README.md`.

## Privacy protection

- No personal information may appear in test cases; account identifiers, customerID, subscriptionID, emails, etc. must be replaced with fictitious values.
- `config.toml` contains real credentials and must never be committed; its actual contents must not appear in the agent's context in any form.
