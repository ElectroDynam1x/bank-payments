#!/usr/bin/env bash
# Учебный стенд на одной машине: реестр образов, три узла Docker Swarm и балансировщик.
#
# Узлы кластера работают в привилегированных контейнерах docker:dind, у каждого узла
# свой демон Docker и свой адрес в сети стенда. В промышленной среде на их месте
# отдельные серверы, остальные настройки от этого не зависят.
#
# Требуется Docker 24 или новее, openssl, права администратора на машине стенда.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DATA=${STAND_DATA:-$ROOT/.stand}        # ключи и пароли стенда, в репозиторий не попадают
REGISTRY=registry.bank.local:5000
NODES=(prod-swarm-01 prod-swarm-02 prod-swarm-03)
mkdir -p "$DATA/pki" "$DATA/secrets" "$DATA/registry-auth"

# 1. Удостоверяющий центр стенда, сертификаты реестра и шлюза
if [ ! -f "$DATA/pki/ca.crt" ]; then
  (
    cd "$DATA/pki"
    openssl req -x509 -newkey rsa:4096 -nodes -days 825 -keyout ca.key -out ca.crt \
      -subj "/C=RU/O=Bank Stand/CN=Bank Stand Root CA" \
      -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign"
    issue() {  # issue <файл> <имя> <альтернативные имена>
      openssl req -newkey rsa:2048 -nodes -keyout "$1.key" -out "$1.csr" -subj "/C=RU/O=Bank Stand/CN=$2"
      printf 'subjectAltName=%s\nextendedKeyUsage=serverAuth\nkeyUsage=digitalSignature,keyEncipherment\n' "$3" > "$1.ext"
      openssl x509 -req -in "$1.csr" -CA ca.crt -CAkey ca.key -CAcreateserial -days 397 \
        -extfile "$1.ext" -out "$1.crt"
    }
    issue registry registry.bank.local "DNS:registry.bank.local,IP:10.10.0.5"
    issue gateway payments.bank.local \
      "DNS:payments.bank.local,DNS:payments-stage.bank.local,DNS:localhost,IP:127.0.0.1"
  )
fi

# 2. Сеть стенда
docker network inspect stand >/dev/null 2>&1 || docker network create --subnet 10.10.0.0/24 stand

# 3. Реестр образов: TLS и вход по паролю
if [ ! -f "$DATA/secrets/registry_ci_password" ]; then
  openssl rand -hex 12 > "$DATA/secrets/registry_ci_password"
  docker run --rm --entrypoint htpasswd httpd:2.4-alpine -Bbn ci \
    "$(cat "$DATA/secrets/registry_ci_password")" > "$DATA/registry-auth/htpasswd"
fi
docker inspect registry >/dev/null 2>&1 || docker run -d --name registry --restart unless-stopped \
  --network stand --ip 10.10.0.5 --network-alias registry.bank.local \
  -v registry-data:/var/lib/registry \
  -v "$DATA/pki/registry.crt:/certs/registry.crt:ro" -v "$DATA/pki/registry.key:/certs/registry.key:ro" \
  -v "$DATA/registry-auth/htpasswd:/auth/htpasswd:ro" \
  -e REGISTRY_HTTP_ADDR=0.0.0.0:5000 \
  -e REGISTRY_HTTP_TLS_CERTIFICATE=/certs/registry.crt -e REGISTRY_HTTP_TLS_KEY=/certs/registry.key \
  -e REGISTRY_AUTH=htpasswd -e REGISTRY_AUTH_HTPASSWD_REALM="Bank Registry" \
  -e REGISTRY_AUTH_HTPASSWD_PATH=/auth/htpasswd \
  registry:3

# Машина стенда должна доверять сертификату реестра и знать имена стенда
sudo mkdir -p "/etc/docker/certs.d/$REGISTRY"
sudo cp "$DATA/pki/ca.crt" "/etc/docker/certs.d/$REGISTRY/ca.crt"
grep -q registry.bank.local /etc/hosts || sudo tee -a /etc/hosts >/dev/null <<'HOSTS'
10.10.0.5 registry.bank.local
10.10.0.10 payments.bank.local payments-stage.bank.local
10.10.0.11 prod-swarm-01
10.10.0.12 prod-swarm-02
10.10.0.13 prod-swarm-03
HOSTS
docker login "$REGISTRY" --username ci --password-stdin < "$DATA/secrets/registry_ci_password"

# 4. Зеркало базовых образов: узлы кластера берут образы только из внутреннего реестра
for image in python:3.13-slim nginx:1.30.6-alpine postgres:17-alpine; do
  docker pull "$image"
  docker tag "$image" "$REGISTRY/mirror/$image"
  docker push "$REGISTRY/mirror/$image"
done

# 5. Узлы кластера. API Docker каждого узла доступен только по TLS с клиентским сертификатом
for i in 1 2 3; do
  name=${NODES[$((i - 1))]}
  docker inspect "$name" >/dev/null 2>&1 || docker run -d --name "$name" --hostname "$name" --privileged \
    --restart unless-stopped --network stand --ip "10.10.0.1$i" \
    -e DOCKER_TLS_CERTDIR=/certs \
    -v "node$i-certs:/certs" -v "node$i-docker:/var/lib/docker" \
    -v "$DATA/pki/ca.crt:/etc/docker/certs.d/$REGISTRY/ca.crt:ro" \
    docker:dind
done
for name in "${NODES[@]}"; do
  until docker exec "$name" docker info >/dev/null 2>&1; do sleep 2; done
done

# 6. Кластер Swarm: три управляющих узла, допустим отказ одного из них
if ! docker exec prod-swarm-01 docker node ls >/dev/null 2>&1; then
  docker exec prod-swarm-01 docker swarm init --advertise-addr 10.10.0.11
  token=$(docker exec prod-swarm-01 docker swarm join-token -q manager)
  docker exec prod-swarm-02 docker swarm join --token "$token" --advertise-addr 10.10.0.12 10.10.0.11:2377
  docker exec prod-swarm-03 docker swarm join --token "$token" --advertise-addr 10.10.0.13 10.10.0.11:2377
fi

# Метки узлов: на первых двух работают шлюзы, на третьем лежит том СУБД
docker exec prod-swarm-01 docker node update --label-add edge=true --label-add app=true prod-swarm-01
docker exec prod-swarm-01 docker node update --label-add edge=true --label-add app=true prod-swarm-02
docker exec prod-swarm-01 docker node update --label-add app=true --label-add db=true prod-swarm-03

# 7. Ключи администратора для удалённого управления кластером
mkdir -p "$DATA/swarm-client"
docker cp prod-swarm-01:/certs/client/. "$DATA/swarm-client/"

# 8. Балансировщик перед шлюзами кластера
docker inspect lb >/dev/null 2>&1 || docker run -d --name lb --restart unless-stopped \
  --network stand --ip 10.10.0.10 \
  -v "$ROOT/stand/lb.conf:/etc/nginx/nginx.conf:ro" nginx:1.30.6-alpine

cat <<INFO

Стенд готов. Подключение к управляющему узлу:
  export DOCKER_HOST=tcp://prod-swarm-01:2376 DOCKER_TLS_VERIFY=1 DOCKER_CERT_PATH=$DATA/swarm-client
Дальше: stand/create-secrets.sh bank-stage $DATA/pki $DATA/secrets/bank-stage_demo_password
INFO
docker exec prod-swarm-01 docker node ls
