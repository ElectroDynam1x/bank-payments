#!/usr/bin/env bash
# Секреты и самоподписанный сертификат для локального запуска (docker compose).
set -euo pipefail
dir="$(cd "$(dirname "$0")/.." && pwd)/.local"
mkdir -p "$dir"
[ -f "$dir/db_password" ]   || openssl rand -hex 16 > "$dir/db_password"
[ -f "$dir/jwt_secret" ]    || openssl rand -hex 32 > "$dir/jwt_secret"
[ -f "$dir/demo_password" ] || echo "demo12345" > "$dir/demo_password"
[ -f "$dir/tls.crt" ] || openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout "$dir/tls.key" -out "$dir/tls.crt" -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" 2>/dev/null
chmod 644 "$dir"/*
echo "Секреты для локального запуска созданы в $dir"
