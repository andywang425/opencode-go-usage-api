# OpenCode Go 用量 API

被访问时实时抓取一次 OpenCode Go 工作区页面，解析用量数据，返回 JSON。

我个人用于接入[CC Switch](https://ccswitch.io/)，方便随时查看剩余用量和重置时间。当 CC Switch 官方支持 OpenCode GO 的用量查询时，本项目将停止维护。

## 响应格式

`GET /usage`（需鉴权）返回：

```json
{
  "success": true,
  "reason": "",
  "data": "滚动 0% (5h) | 周 7% (3d16h) | 月 3% (29d22h)"
}
```

- **success**：解析出至少一组用量则 `true`；抓取失败或一项都没解析出则 `false`。
- **reason**：`success` 为 `false` 时说明原因（如“抓取失败：登录凭证可能已失效”）。
- **data**：滚动/每周/每月用量的已用百分比 + 距下次重置的倒计时。**格式可通过 `.env` 的 `DATA_TEMPLATE` 自定义**，详见下方可选配置。

另有 `GET /health`（免鉴权）返回 `{"status":"ok"}`，用于存活检查。

## 技术方案

- **Python + uv**，FastAPI + uvicorn。
- 用 **httpx** 带 `auth`、`oc_locale` 两个 Cookie 发一次 GET，解析首屏 HTML 里内联的用量 JSON（精确到秒），DOM 文本兜底。
- **HTTPS**：uvicorn 直接加载 TLS 证书，监听端口由 `.env` 的 `PORT` 控制。
- **鉴权**：请求头 `Authorization: Bearer <API_TOKEN>`。

---

## 部署步骤

假设系统是 Ubuntu 24.04，用户 root，有公网IP，项目放在 `/opt/opencode-go-usage-api`。

### 1. 克隆项目

```bash
cd /opt
git clone https://github.com/andywang425/opencode-go-usage-api.git
cd /opt/opencode-go-usage-api
```

### 2. 安装依赖

```bash
uv sync           # 创建 .venv 并按 pyproject.toml 安装依赖
```

### 3. （可选）生成自签证书

```bash
chmod +x gen-cert.sh
./gen-cert.sh <你的公网IP>          # 例：./gen-cert.sh 203.0.113.45
```

输出目录默认是脚本同目录下的 `./certs` 目录。生成的 `certs/cert.pem`、`certs/key.pem` 有效期 10 年。

### 4. 填写配置

```bash
cp .env.example .env
chmod 600 .env                      # 内含等同账户登录态的 cookie，必须锁权限
nano .env
```

必填项：

- `AUTH_COOKIE`：你的 OpenCode `auth` cookie（浏览器登录后，开发者工具 → 应用 → Cookie 里复制 `auth` 的值）。
- `API_TOKEN`：第三方访问用的密钥，生成一个强随机值：`openssl rand -hex 32`。
- `WORKSPACE_ID`：你的工作区 ID。

可选项：

- `SSL_CERTFILE` / `SSL_KEYFILE`：证书和私钥文件路径。如果不填则无法启用 HTTPS，降级为 HTTP（后续 url 中的 https 改为 http）。
- `OC_LOCALE`：网页语言，默认 `zh`。
- `PORT` / `HOST`：监听端口和地址，默认 `18443` / `0.0.0.0`。改端口后，下方涉及端口号的防火墙、验证、接入命令需同步替换为你配置的端口。
- `DATA_TEMPLATE`：自定义 `data` 字段格式，留空用默认格式。

#### 自定义 data 格式

`data` 字段默认格式为 `滚动 0% (5h) | 周 7% (3d16h) | 月 3% (29d22h)`，可在 `.env` 里用 `DATA_TEMPLATE` 改成任意模板字符串。占位符形如 `{分组_字段}`：

| 分组      | 含义     | 字段      | 含义                       |
| --------- | -------- | --------- | -------------------------- |
| `rolling` | 滚动用量 | `percent` | 已用百分比数字（不含 `%`） |
| `weekly`  | 每周用量 | `reset`   | 距重置倒计时（如 `3d16h`） |
| `monthly` | 每月用量 | `status`  | 状态文本（如 `ok`）        |

组合示例（分组\_字段）：`{rolling_percent}`、`{weekly_reset}`、`{monthly_status}`。标签文字（“滚动”等）直接写进模板即可。

```
# 只看百分比、用斜杠分隔
DATA_TEMPLATE=R {rolling_percent}% / W {weekly_percent}% / M {monthly_percent}%
```

- 某组用量未解析出、或某字段缺失时，以 `—` 兜底。
- 未知占位符（拼错的名字）会原样保留成 `{xxx}`，便于发现问题。
- 模板语法非法（花括号不配对等）时自动回退默认格式，并在启动日志打印一条警告，接口不会因此报错。
- 留空或不配置该项即使用默认格式。

### 5. 放行防火墙 / 安全组

把下文的 `<PORT>` 换成你在 `.env` 里配置的 `PORT`（默认 18443）。

```bash
# 本机 ufw（若启用）
ufw allow <PORT>/tcp
```

**另外别忘了在云服务商控制台的安全组放行对应 TCP 端口**，否则外网连不上。

### 6. 安装 systemd 服务

```bash
chmod +x run.sh
cp opencode-go-usage-api.service /etc/systemd/system/
# 编辑服务文件，把路径/用户改成你的
# vim /etc/systemd/system/opencode-go-usage-api.service
systemctl daemon-reload
systemctl enable --now opencode-go-usage-api
systemctl status opencode-go-usage-api          # 确认 active (running)
```

看日志：

```bash
journalctl -u opencode-go-usage-api -f
```

### 7. 验证

下文 `<PORT>` 即你在 `.env` 配置的 `PORT`（默认 18443）。

在服务器本机（`-k` 跳过自签证书校验，如果没配置证书或配置了可信证书不用加）：

```bash
# 存活检查
curl -k https://127.0.0.1:<PORT>/health

# 用量（带 token）
curl -k -H "Authorization: Bearer <你的API_TOKEN>" https://127.0.0.1:<PORT>/usage
```

从外部（用公网 IP）：

```bash
curl -k -H "Authorization: Bearer <你的API_TOKEN>" https://<你的公网IP>:<PORT>/usage
```

预期返回形如 `{"success":true,...,"data":"滚动 …% (…) | 周 …% (…) | 月 …% (…)"}` 的 JSON。

## CC Switch 接入

配置用量查询 → 自定义预设模板，填入以下内容：

```js
({
  request: {
    url: "https://<你的公网IP>:<PORT>/usage",
    method: "GET",
    headers: {
      Authorization: "Authorization: Bearer <你的API_TOKEN>",
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

如果配置了自签证书，需要把证书导入到操作系统的信任证书库。

### Windows 安装证书的方法

先把刚刚生成的 `certs/cert.pem` 下载到本地：

```bash
scp root@<服务器公网IP>:/opt/opencode-go-usage-api/certs/cert.pem C:\Users\<你的用户名>\Desktop\cert.crt
```

双击桌面上的 `cert.crt` 安装证书，安装位置选 “受信任的根证书颁发机构”。

---

## 运维

| 操作         | 命令                                                    |
| ------------ | ------------------------------------------------------- |
| 重启         | `systemctl restart opencode-go-usage-api`               |
| 停止         | `systemctl stop opencode-go-usage-api`                  |
| 看状态       | `systemctl status opencode-go-usage-api`                |
| 看日志       | `journalctl -u opencode-go-usage-api -f`                |
| 改配置后生效 | 编辑 `.env` → `systemctl restart opencode-go-usage-api` |

### cookie 失效怎么办

`auth` cookie 会过期。当 `/usage` 返回 `success:false` 且 `reason` 为 **「登录凭证已失效，请重新获取 auth cookie」** 时，说明 cookie 已失效——重新登录 OpenCode，复制新的 `auth` 值填进 `.env`，`systemctl restart`。

> 其它 `success:false` 文案含义不同：`抓取失败：…` 为网络/上游异常，`当前账号无 OpenCode Go 订阅` 为该账号无 Go 套餐，`未能从页面解析出用量数据…` 多为页面结构变更。仅「凭证已失效」需要换 cookie。

## 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。
