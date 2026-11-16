"""Параметры приложения.

Секреты (пароль БД, ключ подписи JWT) читаются из файлов Docker secrets
(/run/secrets/<имя>), а в локальной разработке – из переменных окружения.
"""
import os
from pathlib import Path


def read_secret(name: str, default: str = "") -> str:
    """Возвращает секрет из файла <ИМЯ>_FILE или /run/secrets/<имя>, иначе из окружения."""
    path = Path(os.getenv(f"{name.upper()}_FILE", f"/run/secrets/{name}"))
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return os.getenv(name.upper(), default)


class Settings:
    app_env: str = os.getenv("APP_ENV", "dev")
    app_version: str = os.getenv("APP_VERSION", "0.0.0-dev")
    git_commit: str = os.getenv("GIT_COMMIT", "unknown")

    db_host: str = os.getenv("DB_HOST", "db")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "bank")
    db_user: str = os.getenv("DB_USER", "bank")
    db_password: str = read_secret("db_password", "bank")
    db_connect_retries: int = int(os.getenv("DB_CONNECT_RETRIES", "30"))

    jwt_secret: str = read_secret("jwt_secret", "dev-only-secret-key-change-me-0123456789")
    jwt_ttl_minutes: int = int(os.getenv("JWT_TTL_MINUTES", "30"))
    pbkdf2_iterations: int = int(os.getenv("PBKDF2_ITERATIONS", "310000"))

    seed_demo_data: bool = os.getenv("SEED_DEMO_DATA", "0") == "1"
    demo_password: str = read_secret("demo_password", "demo12345")

    @property
    def database_url(self) -> str:
        explicit = os.getenv("DATABASE_URL")
        if explicit:
            return explicit
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
