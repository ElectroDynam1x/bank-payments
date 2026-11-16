from app import migrate
from app.db import engine


def test_liveness_and_readiness(client):
    assert client.get("/api/health/live").json() == {"status": "ok"}
    assert client.get("/api/health/ready").json() == {"status": "ready"}


def test_version_endpoint_and_headers(client):
    response = client.get("/api/version")
    assert set(response.json()) == {"version", "commit", "env", "instance"}
    assert response.headers["X-App-Version"] == response.json()["version"]


def test_migrations_are_idempotent(client):
    assert migrate.run(engine) == []


def test_audit_log_is_closed_for_operator(client, operator, auditor):
    assert client.get("/api/audit", headers=operator).status_code == 403
    assert client.get("/api/audit", headers=auditor).status_code == 200
