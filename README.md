# OpenCode Go 用量 API

被访问时实时抓取指定 OpenCode Go 工作区页面，解析用量数据并返回 JSON。支持在一个服务中配置多个 OpenCode Go 账号，供 [CC Switch](https://ccswitch.io/) 的用量查询功能使用。

当 CC Switch 官方支持 OpenCode Go 的用量查询或 OpenCode 提供了 JSON 格式的用量查询接口后，本项目将停止维护。

## API

### 查询用量

- `GET /usage`：查询 `config.toml` 中指定的默认账号。
- `GET /usage/{account_id}`：查询指定账号，例如 `/usage/backup`。

两个接口都需要请求头 `Authorization: Bearer <API_TOKEN>`，成功响应格式一致：

```json
{
  "success": true,
  "reason": "",
  "data": "滚动 0% (5h) | 周 7% (3d16h) | 月 3% (29d22h)"
}
```

- `success`：解析出至少一组用量时为 `true`。
- `reason`：抓取或解析失败时说明原因。
- `data`：用量与重置倒计时，可通过配置模板自定义。

已知账号的凭据失效、抓取失败和解析失败仍返回 HTTP 200，并通过 `success:false` 表示，便于 CC Switch 提取错误信息。未知账号返回 HTTP 404，鉴权失败返回 HTTP 401。

### 健康检查

`GET /health` 免鉴权，返回 `{"status":"ok"}`。该接口只检查服务存活，不抓取账号页面。

## 配置

服务固定读取当前工作目录下的 `config.toml`。复制示例并限制文件权限：

```bash
cp config.example.toml config.toml
chmod 600 config.toml
```

完整示例：

```toml
[server]
api_token = "使用 openssl rand -hex 32 生成的强随机值"
host = "0.0.0.0"
port = 18443
ssl_certfile = "certs/cert.pem"
ssl_keyfile = "certs/key.pem"

[fetch]
timeout = 10
retries = 1
locale = "zh"
user_agent = "Mozilla/5.0 ..."

[response]
data_template = "滚动 {rolling_percent}% ({rolling_reset}) | 周 {weekly_percent}% ({weekly_reset}) | 月 {monthly_percent}% ({monthly_reset})"

[account]
default = "main"

[accounts.main]
auth_cookie = "主账号的 auth cookie 值"
workspace_id = "wrk_main"

[accounts.backup]
auth_cookie = "备用账号的 auth cookie 值"
workspace_id = "wrk_backup"
```

账号 ID 支持 1–64 位大小写字母、数字、`_`、`-`，首位必须是字母或数字。账号 ID 大小写敏感，因此 `Main` 和 `main` 是不同账号。即使只有一个账号，也必须设置 `[account].default`。

配置会在启动时严格校验。未知字段、空凭据、无效默认账号、不完整的 TLS 配置等都会阻止服务启动。修改配置后需要重启服务。

### 配置项

| 配置                                  | 默认值        | 说明                            |
| ------------------------------------- | ------------- | ------------------------------- |
| `server.api_token`                    | 无            | API 访问密钥，必填              |
| `server.host`                         | `0.0.0.0`     | 监听地址                        |
| `server.port`                         | `18443`       | 监听端口                        |
| `server.ssl_certfile` / `ssl_keyfile` | 空            | 必须同时填写；均为空时使用 HTTP |
| `fetch.timeout`                       | `10`          | 单次抓取超时秒数                |
| `fetch.retries`                       | `1`           | 网络异常后的重试次数            |
| `fetch.locale`                        | `zh`          | OpenCode 的 `oc_locale` cookie  |
| `fetch.user_agent`                    | 内置浏览器 UA | 上游请求的 User-Agent           |
| `response.data_template`              | 内置模板      | 响应 `data` 字段模板            |
| `account.default`                     | 无            | 默认账号 ID，必填               |
| `accounts.<id>.auth_cookie`           | 无            | 该账号的原始 `auth` cookie 值   |
| `accounts.<id>.workspace_id`          | 无            | 该账号对应的工作区 ID           |

- 工作区 ID：`https://opencode.ai/workspace/<这里>/go`
- Cookie 获取：在浏览器中打开 `https://opencode.ai/workspace/wrk_XXX/go`，通过开发者工具（`F12`）查看

### 自定义 data 格式

模板占位符由分组和字段组成，例如 `{rolling_percent}`：

| 分组      | 含义     | 字段      | 含义         |
| --------- | -------- | --------- | ------------ |
| `rolling` | 滚动用量 | `percent` | 已用百分比   |
| `weekly`  | 每周用量 | `reset`   | 距重置倒计时 |
| `monthly` | 每月用量 | `status`  | 状态文本     |

三种分组都支持 `percent`、`reset` 和 `status`。缺失值显示为 `—`，未知的简单占位符会原样保留；模板语法错误会导致配置校验失败。

```toml
[response]
data_template = "R {rolling_percent}% / W {weekly_percent}% / M {monthly_percent}%"
```

## 部署

以下示例假设 Ubuntu 24.04、项目目录 `/opt/opencode-go-usage-api`。

```bash
cd /opt
git clone https://github.com/andywang425/opencode-go-usage-api.git
cd opencode-go-usage-api
uv sync
cp config.example.toml config.toml
# 按需编辑 config.toml
chmod 600 config.toml
```

如需自签证书：

```bash
chmod +x gen-cert.sh
./gen-cert.sh <公网IP>
```

然后将生成的路径写入 `config.toml`：

```toml
[server]
ssl_certfile = "certs/cert.pem"
ssl_keyfile = "certs/key.pem"
```

安装 systemd 服务：

```bash
chmod +x run.sh
cp opencode-go-usage-api.service /etc/systemd/system/
# 按需编辑 /etc/systemd/system/opencode-go-usage-api.service
systemctl daemon-reload
systemctl enable --now opencode-go-usage-api
systemctl status opencode-go-usage-api
```

修改配置后执行：

```bash
systemctl restart opencode-go-usage-api
```

记得在云厂商安全组 / 防火墙放行 `server.port`（默认 `18443`）。

验证服务，使用自签证书时保留 `-k`：

```bash
curl -k https://127.0.0.1:18443/health
curl -k -H "Authorization: Bearer <API_TOKEN>" https://127.0.0.1:18443/usage
curl -k -H "Authorization: Bearer <API_TOKEN>" https://127.0.0.1:18443/usage/backup
# 看日志
journalctl -u opencode-go-usage-api -f
```

## CC Switch 接入

点击配置用量查询图标，预设模板选择自定义，填入以下提取器代码：

```js
({
  request: {
    url: "https://<公网IP>:<PORT>/usage/<ACCOUNT_ID>",
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

默认账号也可以继续使用 `/usage`。如果使用自签证书，需要将证书导入运行 CC Switch 的操作系统的信任证书库。

## Cookie 失效

当接口返回以下结果时，重新登录对应 OpenCode 账号并更新其 `auth_cookie`，然后重启服务：

```json
{
  "success": false,
  "reason": "登录凭证已失效，请重新获取 auth cookie",
  "data": ""
}
```

`抓取失败：…` 表示网络或上游异常，`当前账号无 OpenCode Go 订阅` 表示该工作区没有 Go 套餐，`未能从页面解析出用量数据…` 通常表示页面结构发生变化。

## 本地开发

需要 [uv](https://docs.astral.sh/uv/)。

```bash
uv sync
cp config.example.toml config.toml
# 编辑 config.toml 后启动
uv run uvicorn opencode_go_usage_api:app --reload
```

运行测试：

```bash
uv run pytest
```

## 许可证

[MIT](LICENSE)
