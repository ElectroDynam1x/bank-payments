#!/usr/bin/env bash
# Проверка работоспособности после развёртывания: smoke.sh <адрес> <ожидаемая версия>
#
# Проверяет шлюз, готовность серверной части, версию сборки, вход в систему
# и полный цикл операций со счётом (создание, чтение, изменение, удаление).
# Пароль тестового пользователя берётся из переменной DEMO_PASSWORD,
# корневой сертификат стенда – из CA_CERT.
set -euo pipefail

BASE_URL=${1:?укажите адрес контура}
EXPECTED=${2:-}
: "${DEMO_PASSWORD:?не задан пароль тестового пользователя (DEMO_PASSWORD)}"
CURL=(curl --silent --show-error --max-time 10 --noproxy '*')
[ -n "${CA_CERT:-}" ] && CURL+=(--cacert "$CA_CERT")

fail() { echo "  ОШИБКА: $*"; exit 1; }
ok()   { echo "  ок: $*"; }
field() { python3 -c "import json,sys; print(json.load(sys.stdin)$1)"; }

echo "Проверка $BASE_URL"

# шлюз и серверная часть могут подниматься несколько секунд
for attempt in $(seq 1 20); do
  code=$("${CURL[@]}" -o /dev/null -w '%{http_code}' "$BASE_URL/api/health/ready" || true)
  [ "$code" = "200" ] && break
  sleep 3
done
[ "$code" = "200" ] || fail "серверная часть не готова, код ответа $code"
ok "серверная часть готова (GET /api/health/ready -> 200)"

code=$("${CURL[@]}" -o /dev/null -w '%{http_code}' "$BASE_URL/")
[ "$code" = "200" ] || fail "клиентская часть недоступна, код ответа $code"
ok "клиентская часть отвечает (GET / -> 200)"

if [ -n "$EXPECTED" ]; then
  # при нескольких репликах опрашиваем сервис несколько раз: все должны быть новой версии
  for attempt in $(seq 1 6); do
    actual=$("${CURL[@]}" "$BASE_URL/api/version" | field "['version']")
    [ "$actual" = "$EXPECTED" ] || fail "версия $actual, ожидалась $EXPECTED"
  done
  ok "версия сборки $EXPECTED"
fi

token=$("${CURL[@]}" -H 'Content-Type: application/json' \
  -d "{\"username\":\"admin\",\"password\":\"$DEMO_PASSWORD\"}" \
  "$BASE_URL/api/auth/login" | field "['access_token']") || fail "вход не выполнен"
AUTH=(-H "Authorization: Bearer $token" -H 'Content-Type: application/json')
ok "вход пользователя admin, токен получен"

code=$("${CURL[@]}" -o /dev/null -w '%{http_code}' "$BASE_URL/api/accounts")
[ "$code" = "401" ] || fail "запрос без токена вернул $code вместо 401"
ok "запрос без токена отклонён (401)"

number="4070281090000$(date +%H%M%S)$((RANDOM % 10))"
id=$("${CURL[@]}" "${AUTH[@]}" -d "{\"number\":\"$number\",\"owner_name\":\"Проверка развёртывания\",\"balance\":\"10.00\"}" \
  "$BASE_URL/api/accounts" | field "['id']") || fail "счёт не создан"
"${CURL[@]}" "${AUTH[@]}" "$BASE_URL/api/accounts/$id" | field "['number']" | grep -q "$number" || fail "счёт не читается"
"${CURL[@]}" "${AUTH[@]}" -X PUT -d '{"status":"closed"}' "$BASE_URL/api/accounts/$id" | field "['status']" | grep -q closed \
  || fail "счёт не изменён"
code=$("${CURL[@]}" "${AUTH[@]}" -o /dev/null -w '%{http_code}' -X DELETE "$BASE_URL/api/accounts/$id")
[ "$code" = "204" ] || fail "счёт не удалён, код ответа $code"
ok "создание, чтение, изменение и удаление счёта (запись в БД работает)"

echo "Проверка пройдена"
