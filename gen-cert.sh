#!/usr/bin/env bash
# Generate a self-signed TLS certificate whose SAN is bound to the server's public IP, valid for 10 years.
# Usage: ./gen-cert.sh <PUBLIC_IP> [output directory]
# Example:  ./gen-cert.sh 203.0.113.45
set -euo pipefail

IP="${1:-}"
OUT_DIR="${2:-$(dirname "$0")/certs}"

if [[ -z "$IP" ]]; then
  echo "Usage: $0 <PUBLIC_IP> [output directory]" >&2
  echo "Example:   $0 203.0.113.45" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
CERT="$OUT_DIR/cert.pem"
KEY="$OUT_DIR/key.pem"

# -nodes: keep the private key unencrypted (required for unattended systemd startup)
# subjectAltName=IP:<ip>: critical, clients validate by IP and need it
openssl req -x509 -newkey rsa:2048 -sha256 \
  -days 3650 -nodes \
  -keyout "$KEY" -out "$CERT" \
  -subj "/CN=$IP" \
  -addext "subjectAltName=IP:$IP"

chmod 600 "$KEY"
chmod 644 "$CERT"

echo "Generated:"
echo "  Certificate: $CERT"
echo "  Private key: $KEY  (mode 600)"
echo
echo "Certificate details:"
openssl x509 -in "$CERT" -noout -subject -ext subjectAltName -dates
