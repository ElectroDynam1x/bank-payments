#!/usr/bin/env bash
# Создание секретов контура в кластере Swarm.
#   create-secrets.sh <стек> <каталог с сертификатом шлюза> [файл для пароля тестового пользователя]
# Выполняется администратором один раз перед первым развёртыванием. Пароль БД и ключ
# подписи токенов генерируются случайно и хранятся только в зашифрованном хранилище
# кластера. Пароль тестового пользователя дополнительно сохраняется в указанный файл,
# чтобы передать его в секреты системы CI/CD для проверки после развёртывания.
set -euo pipefail
STACK=${1:?укажите имя стека, например bank-prod}
PKI=${2:?укажите каталог с gateway.crt и gateway.key}
OUT=${3:-}

exists() { docker secret inspect "${STACK}_$1" >/dev/null 2>&1; }
create() {  # create <имя>: значение читается со стандартного ввода
  docker secret create --label stack="$STACK" "${STACK}_$1" - >/dev/null
  echo "создан секрет ${STACK}_$1"
}

exists db_password || openssl rand -hex 24 | create db_password
exists jwt_secret  || openssl rand -hex 48 | create jwt_secret
if ! exists demo_password; then
  password=$(openssl rand -hex 9)
  printf '%s' "$password" | create demo_password
  [ -n "$OUT" ] && { umask 077; printf '%s' "$password" > "$OUT"; }
fi
exists tls_cert || create tls_cert < "$PKI/gateway.crt"
exists tls_key  || create tls_key  < "$PKI/gateway.key"
docker secret ls --filter "label=stack=$STACK" --format 'table {{.Name}}\t{{.CreatedAt}}'
