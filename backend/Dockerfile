# Образ серверной части (FastAPI). Многоэтапная сборка: зависимости ставятся
# в отдельном этапе, в итоговый образ попадают только виртуальное окружение и код.
# BASE_REGISTRY позволяет брать базовые образы из внутреннего зеркала реестра.
ARG BASE_REGISTRY=docker.io/library

FROM ${BASE_REGISTRY}/python:3.13-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r requirements.txt

# Этап test: модульные тесты выполняются при сборке (docker build --target test)
FROM builder AS test
COPY requirements-dev.txt pyproject.toml ./
RUN /opt/venv/bin/pip install -r requirements-dev.txt
COPY app ./app
COPY tests ./tests
RUN /opt/venv/bin/ruff check . && /opt/venv/bin/python -m pytest -q

FROM ${BASE_REGISTRY}/python:3.13-slim AS runtime
ARG APP_VERSION=0.0.0-dev
ARG GIT_COMMIT=unknown
ENV APP_VERSION=${APP_VERSION} \
    GIT_COMMIT=${GIT_COMMIT} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}"
LABEL org.opencontainers.image.title="bank-payments-backend" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}"
# Непривилегированный пользователь: процесс в контейнере не работает от root
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /srv
COPY --from=builder /opt/venv /opt/venv
COPY app ./app
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=2)"]
# Сначала миграции БД, затем сервер. exec передаёт сигнал SIGTERM процессу uvicorn,
# поэтому при остановке контейнера текущие запросы завершаются штатно.
CMD ["sh", "-c", "python -m app.migrate && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --no-server-header --timeout-graceful-shutdown 20"]
