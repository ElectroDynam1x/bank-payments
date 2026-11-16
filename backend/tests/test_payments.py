from decimal import Decimal

PAYMENT = {
    "account_id": 4,
    "beneficiary_name": "ООО «Получатель»",
    "beneficiary_account": "40702810900000000777",
    "beneficiary_bik": "044525777",
    "amount": "1500.25",
    "purpose": "Оплата по счёту 1 от 01.11.2026",
}


def create(client, headers, **overrides):
    response = client.post("/api/payments", json={**PAYMENT, **overrides}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_payment_crud_cycle(client, operator):
    payment = create(client, operator)
    assert payment["status"] == "draft"
    assert payment["created_by"] == "operator"

    updated = client.put(f"/api/payments/{payment['id']}", json={"amount": "999.99"}, headers=operator)
    assert updated.json()["amount"] == "999.99"

    assert client.delete(f"/api/payments/{payment['id']}", headers=operator).status_code == 204
    assert client.get(f"/api/payments/{payment['id']}", headers=operator).status_code == 404


def test_payments_can_be_filtered_by_status(client, auditor):
    drafts = client.get("/api/payments?status=draft", headers=auditor).json()
    assert drafts and all(p["status"] == "draft" for p in drafts)


def test_execute_debits_account(client, operator, admin):
    before = Decimal(client.get("/api/accounts/4", headers=admin).json()["balance"])
    payment = create(client, operator)
    executed = client.post(f"/api/payments/{payment['id']}/execute", headers=admin)
    assert executed.status_code == 200
    assert executed.json()["status"] == "executed"
    after = Decimal(client.get("/api/accounts/4", headers=admin).json()["balance"])
    assert before - after == Decimal("1500.25")


def test_execute_requires_enough_funds(client, operator, admin):
    payment = create(client, operator, amount="99999999.00")
    response = client.post(f"/api/payments/{payment['id']}/execute", headers=admin)
    assert response.status_code == 409
    assert "Недостаточно средств" in response.json()["detail"]


def test_operator_cannot_execute_payment(client, operator):
    payment = create(client, operator)
    assert client.post(f"/api/payments/{payment['id']}/execute", headers=operator).status_code == 403


def test_creator_cannot_execute_own_payment(client, admin):
    payment = create(client, admin)
    response = client.post(f"/api/payments/{payment['id']}/execute", headers=admin)
    assert response.status_code == 409


def test_executed_payment_is_immutable(client, operator, admin):
    payment = create(client, operator)
    client.post(f"/api/payments/{payment['id']}/execute", headers=admin)
    assert client.put(f"/api/payments/{payment['id']}", json={"amount": "1.00"}, headers=operator).status_code == 409
    assert client.delete(f"/api/payments/{payment['id']}", headers=operator).status_code == 409


def test_payment_to_closed_account_is_rejected(client, operator, admin):
    client.put("/api/accounts/4", json={"status": "closed"}, headers=admin)
    response = client.post("/api/payments", json=PAYMENT, headers=operator)
    assert response.status_code == 409


def test_reject_changes_status(client, operator, admin):
    payment = create(client, operator)
    response = client.post(f"/api/payments/{payment['id']}/reject", headers=admin)
    assert response.json()["status"] == "rejected"
