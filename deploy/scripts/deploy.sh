#!/usr/bin/env bash
# Развёртывание версии в контур: deploy.sh <stage|prod> <версия>
#
# 1. Выкладывает стек в кластер (docker stack deploy).
# 2. Ждёт, пока все сервисы перейдут на новую версию.
# 3. Если Swarm откатил обновление, завершает работу с ошибкой.
# 4. Запускает проверку работоспособности (smoke.sh); при неудаче откатывает сервисы.
#
# Подключение к управляющему узлу задаётся переменными DOCKER_HOST,
# DOCKER_TLS_VERIFY и DOCKER_CERT_PATH.
set -euo pipefail

ENV_NAME=${1:?укажите контур: stage или prod}
export VERSION=${2:?укажите версию образов}
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
set -a; source "$ROOT/deploy/env/$ENV_NAME.env"; set +a
: "${REGISTRY:?не задан адрес реестра образов (REGISTRY)}"
TIMEOUT=${DEPLOY_TIMEOUT:-300}
SERVICES="db backend frontend gateway"

log() { printf '%s  %s\n' "$(date +%H:%M:%S)" "$*"; }

# Откат сервисов, которые успели перейти на новую версию. Сервис, уже возвращённый
# кластером к прежней спецификации, повторно не откатывается.
rollback() {
  log "ОТКАТ: сервисы, перешедшие на версию $VERSION, возвращаются к предыдущей"
  for name in gateway frontend backend; do
    service="${STACK}_${name}"
    image=$(docker service inspect "$service" --format '{{.Spec.TaskTemplate.ContainerSpec.Image}}' 2>/dev/null || true)
    if [ "${image%%@*}" = "$REGISTRY/bank/$name:$VERSION" ]; then
      if docker service rollback --quiet "$service" >/dev/null 2>&1; then
        log "  откат: $service"
      fi
    fi
  done
}

log "Контур $ENV_NAME, стек $STACK, версия $VERSION"
docker stack deploy --with-registry-auth --prune --detach=true \
  --compose-file "$ROOT/deploy/stack.yml" "$STACK"

expected_image() {
  case "$1" in
    db) echo "$REGISTRY/mirror/postgres:17-alpine" ;;
    *)  echo "$REGISTRY/bank/$1:$VERSION" ;;
  esac
}

deadline=$((SECONDS + TIMEOUT))
for name in $SERVICES; do
  service="${STACK}_${name}"
  expected=$(expected_image "$name")
  while true; do
    state=$(docker service inspect "$service" --format '{{if .UpdateStatus}}{{.UpdateStatus.State}}{{else}}none{{end}}')
    spec_image=$(docker service inspect "$service" --format '{{.Spec.TaskTemplate.ContainerSpec.Image}}')
    if [ "${spec_image%%@*}" != "$expected" ]; then
      # Swarm вернул прежнюю спецификацию сервиса: обновление не прошло проверку
      log "ОШИБКА: $service откатился на ${spec_image%%@*} (состояние: $state)"
      docker service ps "$service" --no-trunc --format '  {{.Name}}  {{.CurrentState}}  {{.Error}}' | head -n 6
      rollback
      exit 1
    fi
    replicas=$(docker service ls --filter "name=$service" --format '{{.Replicas}}' | head -n1)
    desired=${replicas##*/}; desired=${desired%% *}
    ready=$(docker service ps "$service" --filter desired-state=running --format '{{.Image}} {{.CurrentState}}' \
      | awk -v image="$expected" '$1 == image && $2 == "Running"' | wc -l)
    if [ "$state" != "updating" ] && [ "${desired:-0}" -gt 0 ] && [ "$ready" -ge "$desired" ]; then
      log "готов: $service, реплик $ready из $desired, образ $expected"
      break
    fi
    if [ "$SECONDS" -ge "$deadline" ]; then
      log "ОШИБКА: $service не перешёл в рабочее состояние за $TIMEOUT с (готово $ready из ${desired:-?}, $state)"
      rollback
      exit 1
    fi
    sleep 3
  done
done

if ! "$ROOT/deploy/scripts/smoke.sh" "$BASE_URL" "$VERSION"; then
  rollback
  exit 1
fi
log "Развёртывание версии $VERSION в контуре $ENV_NAME завершено"
