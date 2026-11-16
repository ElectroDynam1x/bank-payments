def test_login_returns_token_and_role(client):
    response = client.post("/api/auth/login", json={"username": "operator", "password": "test-password"})
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "operator"
    assert body["access_token"].count(".") == 2


def test_login_with_wrong_password_is_rejected(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401


def test_api_requires_token(client):
    assert client.get("/api/accounts").status_code == 401
    assert client.get("/api/payments", headers={"Authorization": "Bearer bad.token.value"}).status_code == 401


def test_me_returns_current_user(client, auditor):
    response = client.get("/api/auth/me", headers=auditor)
    assert response.json()["username"] == "auditor"


def test_failed_login_is_written_to_audit_log(client, admin):
    client.post("/api/auth/login", json={"username": "operator", "password": "nope"})
    events = client.get("/api/audit", headers=admin).json()
    assert any(e["action"] == "login_failed" and e["username"] == "operator" for e in events)
