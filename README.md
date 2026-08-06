# OpenCode Go Usage API

Live-scrapes the specified OpenCode Go workspace page on each request, parses the usage data, and returns it as JSON. Multiple OpenCode Go accounts can be configured in a single service, for use with the usage-query feature of [CC Switch](https://ccswitch.io/).

This project will stop being maintained once CC Switch officially supports OpenCode Go usage queries, or OpenCode provides a JSON usage-query API. Related issue and PR: [#2260](https://github.com/farion1231/cc-switch/issues/2260), [#3606](https://github.com/farion1231/cc-switch/pull/3606)

## API

### Query usage

- `GET /usage`: queries the default account specified in `config.toml`.
- `GET /usage/{account_id}`: queries a specific account, e.g. `/usage/backup`.

Both endpoints require the header `Authorization: Bearer <API_TOKEN>`. The response format is:

```json
{
  "success": true,
  "reason": "",
  "data": "Rolling 0% (5h) | Weekly 7% (3d16h) | Monthly 3% (29d22h)"
}
```

- `success`: `true` when at least one usage group was parsed.
- `reason`: explains the reason when fetching or parsing fails.
- `data`: usage and reset countdown, customizable via the config template.

Expired credentials, fetch failures, and parse failures for a known account still return HTTP 200, indicated by `success:false`. Unknown accounts return HTTP 404, and auth failures return HTTP 401.

### Health check

`GET /health` requires no auth and returns `{"status":"ok"}`. This endpoint only checks that the service is alive; it does not fetch any account page.

## Configuration

The service always reads `config.toml` from the current working directory. Copy the example and restrict file permissions:

```bash
cp config.example.toml config.toml
chmod 600 config.toml
```

Full example:

```toml
[server]
api_token = "generate a strong random value, e.g. with openssl rand -hex 32"
host = "0.0.0.0"
port = 18443
ssl_certfile = "certs/cert.pem"
ssl_keyfile = "certs/key.pem"

[fetch]
timeout = 10
retries = 1
locale = "en"
user_agent = "Mozilla/5.0 ..."

[response]
data_template = "Rolling {rolling_percent}% ({rolling_reset}) | Weekly {weekly_percent}% ({weekly_reset}) | Monthly {monthly_percent}% ({monthly_reset})"

[account]
default = "main"

[accounts.main]
auth_cookie = "the main account's auth cookie value"
workspace_id = "wrk_main"

[accounts.backup]
auth_cookie = "the backup account's auth cookie value"
workspace_id = "wrk_backup"
```

Account IDs support 1-64 letters (upper and lower case), digits, `_`, and `-`; the first character must be a letter or digit, and they are case-sensitive.

The config is validated at startup. After modifying the config file, restart the service for the changes to take effect.

### Configuration options

| Config                                  | Default        | Description                          |
| --------------------------------------- | -------------- | ------------------------------------ |
| `server.api_token`                      | none           | API access token, required           |
| `server.host`                           | `0.0.0.0`      | Listen address                       |
| `server.port`                           | `18443`        | Listen port                          |
| `server.ssl_certfile` / `ssl_keyfile`   | empty          | Must be set together; HTTP when both empty |
| `fetch.timeout`                         | `10`           | Single fetch timeout in seconds      |
| `fetch.retries`                         | `1`            | Retries after a network error        |
| `fetch.locale`                          | `en`           | The OpenCode `oc_locale` cookie      |
| `fetch.user_agent`                      | built-in browser UA | User-Agent for upstream requests |
| `response.data_template`                | built-in template | Template for the response `data` field |
| `account.default`                       | none           | Default account ID, required         |
| `accounts.<id>.auth_cookie`             | none           | The account's raw `auth` cookie value |
| `accounts.<id>.workspace_id`            | none           | The account's workspace ID           |

- Workspace ID: `https://opencode.ai/workspace/<this>/go`
- Getting the cookie: open `https://opencode.ai/workspace/wrk_XXX/go` in a browser and inspect it with the developer tools (`F12`)

### Custom data format

Template placeholders consist of a group and a field, formatted as `{<group>_<field>}`. There are three groups:

| Group     | Meaning         |
| --------- | --------------- |
| `rolling` | Rolling usage   |
| `weekly`  | Weekly usage    |
| `monthly` | Monthly usage   |

Each group supports three fields:

| Field     | Meaning             |
| --------- | ------------------- |
| `percent` | Percent used        |
| `reset`   | Countdown to reset  |
| `status`  | Status text         |

Compact-style example:

```toml
[response]
data_template = "R {rolling_percent}% ({rolling_reset}) | W {weekly_percent}% ({weekly_reset}) | M {monthly_percent}% ({monthly_reset})"
```

## Deployment

The examples below assume Ubuntu 24.04, project directory `/opt/opencode-go-usage-api`, and [uv](https://docs.astral.sh/uv/) installed.

```bash
cd /opt
git clone https://github.com/andywang425/opencode-go-usage-api.git
cd opencode-go-usage-api
uv sync
cp config.example.toml config.toml
# edit config.toml as needed
chmod 600 config.toml
```

For a self-signed certificate:

```bash
chmod +x gen-cert.sh
./gen-cert.sh <PUBLIC_IP>
```

Then write the paths of the generated certificates into `config.toml`:

```toml
[server]
ssl_certfile = "certs/cert.pem"
ssl_keyfile = "certs/key.pem"
```

Install the systemd service:

```bash
chmod +x run.sh
cp opencode-go-usage-api.service /etc/systemd/system/
# edit /etc/systemd/system/opencode-go-usage-api.service as needed
systemctl daemon-reload
systemctl enable --now opencode-go-usage-api
systemctl status opencode-go-usage-api
```

If you later modify the config, restart the service for the changes to take effect:

```bash
systemctl restart opencode-go-usage-api
```

Remember to allow `server.port` (default `18443`) in your cloud provider's security group / firewall.

Verify the service (add `-k` when using a self-signed certificate):

```bash
curl -k https://127.0.0.1:18443/health
curl -k -H "Authorization: Bearer ***" https://127.0.0.1:18443/usage
curl -k -H "Authorization: Bearer ***" https://127.0.0.1:18443/usage/backup
# watch the logs
journalctl -u opencode-go-usage-api -f
```

## CC Switch integration

Click the configure-usage-query icon, select Custom for the preset template, and paste in the following extractor code:

```js
({
  request: {
    url: "https://<PUBLIC_IP>:<PORT>/usage/<ACCOUNT_ID>",
    method: "GET",
    headers: {
      Authorization: "Bearer <API_TOKEN>",
    },
  },
  extractor: function (response) {
    return {
      isValid: response.success,
      invalidMessage: response.reason,
      extra: response.data,
    };
  },
});
```

If you omit `/<ACCOUNT_ID>`, the default account's usage is queried. If you use a self-signed certificate, you must import the certificate into the trust store of the OS running CC Switch.

To install a self-signed certificate on Windows 11: download `certs/cert.pem` locally in any way, rename it to `cert.crt`, double-click it, install certificate -> choose Current User for the store location -> place all certificates in the following store, browse -> Trusted Root Certification Authorities -> Next, Finish.

## Cookie expiry

When the API returns the following, log back into the corresponding OpenCode account, update its `auth_cookie`, and restart the service:

```json
{
  "success": false,
  "reason": "auth cookie has expired, please re-fetch it; if the cookie is valid, check that workspace_id is correct",
  "data": ""
}
```

`fetch failed: ...` indicates a network or upstream issue; `this account has no OpenCode Go subscription` means the workspace has no Go plan; `failed to parse usage data from the page (the page structure may have changed)` usually means the page structure changed.

## Local development

```bash
uv sync
cp config.example.toml config.toml
# start after editing config.toml
uv run uvicorn opencode_go_usage_api:app --reload
```

Run the tests:

```bash
uv run pytest
```

## License

[MIT](LICENSE)
