#!/usr/bin/env bash
# 生成自签 TLS 证书，SAN 绑定服务器公网 IP，有效期 10 年。
# 用法：./gen-cert.sh <公网IP> [输出目录]
# 例：  ./gen-cert.sh 203.0.113.45
set -euo pipefail

IP="${1:-}"
OUT_DIR="${2:-$(dirname "$0")/certs}"

if [[ -z "$IP" ]]; then
  echo "用法: $0 <公网IP> [输出目录]" >&2
  echo "例:   $0 203.0.113.45" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
CERT="$OUT_DIR/cert.pem"
KEY="$OUT_DIR/key.pem"

# -nodes: 私钥不加密（systemd 无人值守启动需要）
# subjectAltName=IP:<ip>: 关键，客户端按 IP 校验时需要它
openssl req -x509 -newkey rsa:2048 -sha256 \
  -days 3650 -nodes \
  -keyout "$KEY" -out "$CERT" \
  -subj "/CN=$IP" \
  -addext "subjectAltName=IP:$IP"

chmod 600 "$KEY"
chmod 644 "$CERT"

echo "已生成："
echo "  证书: $CERT"
echo "  私钥: $KEY  (权限 600)"
echo
echo "证书信息："
openssl x509 -in "$CERT" -noout -subject -ext subjectAltName -dates
