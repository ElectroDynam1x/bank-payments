"""Миграции схемы БД.

Запускается перед стартом сервера (python -m app.migrate). В PostgreSQL миграции
выполняются под рекомендательной блокировкой, поэтому одновременный старт нескольких
реплик не приводит к гонке. Изменения схемы обратно совместимы: во время
последовательного обновления старая и новая версии работают с одной БД.
"""
import logging
import sys
import time

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from . import models  # noqa: F401  (регистрация моделей в метаданных)
from .config import settings
from .db import Base, engine

log = logging.getLogger("bank.migrate")
LOCK_KEY = 20261115


def _initial_schema(conn) -> None:
    Base.metadata.create_all(conn)


def _payments_status_index(conn) -> None:
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_payments_status_created ON payments (status, created_at)"
    ))


MIGRATIONS = [
    ("001_initial_schema", _initial_schema),
    ("002_payments_status_index", _payments_status_index),
]


def wait_for_db(target=engine) -> None:
    for attempt in range(1, settings.db_connect_retries + 1):
        try:
            with target.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError as exc:
            log.warning("БД недоступна (попытка %s/%s): %s", attempt,
                        settings.db_connect_retries, str(exc).splitlines()[0])
            time.sleep(2)
    raise SystemExit("Не удалось подключиться к базе данных")


def run(target=engine) -> list[str]:
    """Применяет недостающие миграции, возвращает список применённых версий."""
    applied_now: list[str] = []
    with target.begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": LOCK_KEY})
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version VARCHAR(100) PRIMARY KEY, "
            "applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL)"
        ))
        applied = {row[0] for row in conn.execute(text("SELECT version FROM schema_migrations"))}
        for version, migration in MIGRATIONS:
            if version in applied:
                continue
            migration(conn)
            conn.execute(text("INSERT INTO schema_migrations (version) VALUES (:v)"),
                         {"v": version})
            applied_now.append(version)
            log.info("Применена миграция %s", version)
        if settings.seed_demo_data:
            from .seed import seed

            with Session(bind=conn) as session:
                seed(session)
                session.flush()
    return applied_now


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(name)s %(message)s")
    wait_for_db()
    done = run()
    log.info("Схема БД актуальна, применено миграций: %s", len(done))
