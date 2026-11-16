"""Общие фикстуры: приложение работает с SQLite в памяти, без внешних сервисов."""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SEED_DEMO_DATA"] = "1"
os.environ["DEMO_PASSWORD"] = "test-password"
os.environ["PBKDF2_ITERATIONS"] = "1000"  # ускорение тестов
os.environ["JWT_SECRET"] = "unit-test-secret-key-0123456789abcdef"

import pytest
from fastapi.testclient import TestClient

from app import migrate
from app.db import Base, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS schema_migrations")
    migrate.run(engine)
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, username: str, password: str = "test-password") -> dict:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def admin(client):
    return login(client, "admin")


@pytest.fixture()
def operator(client):
    return login(client, "operator")


@pytest.fixture()
def auditor(client):
    return login(client, "auditor")
