"""配置：全部来自 .env（由 load_dotenv 读入）。"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

AUTH_COOKIE = os.getenv("AUTH_COOKIE", "")
OC_LOCALE = os.getenv("OC_LOCALE", "zh")
API_TOKEN = os.getenv("API_TOKEN", "")
WORKSPACE_ID = os.getenv("WORKSPACE_ID", "")
# 由 WORKSPACE_ID 拼出默认 go 页面地址（不再支持环境变量覆盖）
WORKSPACE_URL = f"https://opencode.ai/workspace/{WORKSPACE_ID}/go"
FETCH_TIMEOUT = float(os.getenv("FETCH_TIMEOUT", "10"))
FETCH_RETRIES = int(os.getenv("FETCH_RETRIES", "1"))

USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "18443"))
SSL_CERTFILE = os.getenv("SSL_CERTFILE")
SSL_KEYFILE = os.getenv("SSL_KEYFILE")

# data 字段模板：可用占位符 {rolling_percent}/{rolling_reset}/{rolling_status}
# （weekly_/monthly_ 同理），缺失项由 formatter 以 — 兜底
DEFAULT_DATA_TEMPLATE = (
    "滚动 {rolling_percent}% ({rolling_reset}) | "
    "周 {weekly_percent}% ({weekly_reset}) | "
    "月 {monthly_percent}% ({monthly_reset})"
)
# 空值（未配置或写成 DATA_TEMPLATE=）一律回退默认，避免 data 变成空串
DATA_TEMPLATE = os.getenv("DATA_TEMPLATE", "").strip() or DEFAULT_DATA_TEMPLATE

# 启动期校验：三个必填项缺失则直接退出，避免运行到首次请求才报错
_missing = [
    name
    for name, value in (
        ("AUTH_COOKIE", AUTH_COOKIE),
        ("API_TOKEN", API_TOKEN),
        ("WORKSPACE_ID", WORKSPACE_ID),
    )
    if not value
]
if _missing:
    print(
        f"缺少必填环境变量：{', '.join(_missing)}，请在 .env 中配置后重试",
        file=sys.stderr,
    )
    sys.exit(1)
