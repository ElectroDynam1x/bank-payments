NEW_ACCOUNT = {"number": "40702810100000000999", "owner_name": "ООО «Тест»", "balance": "1000.00"}


def test_seed_accounts_are_listed(client, auditor):
    accounts = client.get("/api/accounts", headers=auditor).json()
    assert len(accounts) == 8
    assert accounts[0]["number"].startswith("40702810")


def test_account_crud_cycle(client, admin):
    created = client.post("/api/accounts", json=NEW_ACCOUNT, headers=admin)
    assert created.status_code == 201
    account_id = created.json()["id"]

    updated = client.put(f"/api/accounts/{account_id}", json={"status": "closed"}, headers=admin)
    assert updated.json()["status"] == "closed"

    assert client.delete(f"/api/accounts/{account_id}", headers=admin).status_code == 204
    assert client.get(f"/api/accounts/{account_id}", headers=admin).status_code == 404


def test_duplicate_account_number_is_rejected(client, operator):
    assert client.post("/api/accounts", json=NEW_ACCOUNT, headers=operator).status_code == 201
    assert client.post("/api/accounts", json=NEW_ACCOUNT, headers=operator).status_code == 409


def test_account_number_must_have_20_digits(client, operator):
    bad = {**NEW_ACCOUNT, "number": "12345"}
    assert client.post("/api/accounts", json=bad, headers=operator).status_code == 422


def test_auditor_cannot_change_accounts(client, auditor):
    assert client.post("/api/accounts", json=NEW_ACCOUNT, headers=auditor).status_code == 403


def test_operator_cannot_delete_account(client, operator):
    assert client.delete("/api/accounts/1", headers=operator).status_code == 403


def test_account_with_payments_cannot_be_deleted(client, admin):
    assert client.delete("/api/accounts/1", headers=admin).status_code == 409
