"""Сервис платёжных поручений: точка входа FastAPI."""
import json
import logging
import socket
import sys
import time

from fastapi import FastAPI, Request

from .config import settings
from .routers import accounts, auth, payments, system

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(message)s")
log = logging.getLogger("bank.access")
HOSTNAME = socket.gethostname()

app = FastAPI(
    title="Сервис платёжных поручений",
    version=settings.app_version,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


@app.middleware("http")
async def access_log(request: Request, call_next):
    """Пишет журнал запросов в JSON и добавляет версию сборки в заголовки ответа."""
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-App-Version"] = settings.app_version
    response.headers["X-Instance"] = HOSTNAME
    if not request.url.path.startswith("/api/health"):
        log.info(json.dumps({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": round((time.perf_counter() - started) * 1000, 1),
            "version": settings.app_version,
            "instance": HOSTNAME,
            "request_id": request.headers.get("x-request-id", ""),
        }, ensure_ascii=False))
    return response


for module in (auth, accounts, payments, system):
    app.include_router(module.router, prefix="/api")
