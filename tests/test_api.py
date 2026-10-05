import pytest
import uuid
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Aegis Ledger"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "healthy"
    assert data["redis"] == "healthy"


@pytest.mark.asyncio
async def test_account_creation_and_balance_query(async_client: AsyncClient):
    # 1. Create Asset account
    payload = {
        "name": "Treasury Vault EUR",
        "currency": "EUR",
        "type": "ASSET",
        "allow_overdraft": False,
    }
    create_res = await async_client.post("/api/v1/accounts", json=payload)
    assert create_res.status_code == 201
    account_data = create_res.json()
    account_id = account_data["id"]
    assert account_data["name"] == "Treasury Vault EUR"
    assert account_data["allow_overdraft"] is False

    # 2. Query initial balance
    balance_res = await async_client.get(f"/api/v1/accounts/{account_id}/balance")
    assert balance_res.status_code == 200
    balance_data = balance_res.json()
    assert balance_data["total_debit"] == 0
    assert balance_data["total_credit"] == 0
    assert balance_data["balance"] == 0


@pytest.mark.asyncio
async def test_transaction_api_idempotency_and_overdraft_protection(async_client: AsyncClient):
    # 1. Create two accounts: Cash (Asset, no overdraft) and Equity (Capital, allow overdraft)
    cash_res = await async_client.post(
        "/api/v1/accounts",
        json={"name": "Retail Cash", "currency": "EUR", "type": "ASSET", "allow_overdraft": False},
    )
    equity_res = await async_client.post(
        "/api/v1/accounts",
        json={"name": "Founder Capital", "currency": "EUR", "type": "EQUITY", "allow_overdraft": True},
    )
    cash_id = cash_res.json()["id"]
    equity_id = equity_res.json()["id"]

    # 2. Fund the Cash account: Debit Cash 100 EUR (10000 cents), Credit Equity 100 EUR
    funding_key = f"funding-tx-{uuid.uuid4()}"
    funding_payload = {
        "description": "Initial funding capital",
        "entries": [
            {"account_id": cash_id, "direction": "DEBIT", "amount": 10000},
            {"account_id": equity_id, "direction": "CREDIT", "amount": 10000},
        ],
    }

    tx_res = await async_client.post(
        "/api/v1/transactions",
        headers={"Idempotency-Key": funding_key},
        json=funding_payload,
    )
    assert tx_res.status_code == 201
    tx_data = tx_res.json()
    assert tx_data["status"] == "POSTED"
    assert len(tx_data["current_hash"]) == 64

    # 3. Repeat request with SAME Idempotency-Key (must return cached result without error)
    cached_res = await async_client.post(
        "/api/v1/transactions",
        headers={"Idempotency-Key": funding_key},
        json=funding_payload,
    )
    assert cached_res.status_code in (200, 201)
    cached_data = cached_res.json()
    assert cached_data["id"] == tx_data["id"]
    assert cached_data["current_hash"] == tx_data["current_hash"]

    # 4. Check Cash balance: should be exactly 10000 cents (100 EUR)
    bal_res = await async_client.get(f"/api/v1/accounts/{cash_id}/balance")
    assert bal_res.json()["balance"] == 10000

    # 5. Overdraft test: Attempt to withdraw 150 EUR (15000 cents) from Cash (which only has 100 EUR)
    overdraft_key = f"overdraft-attempt-{uuid.uuid4()}"
    overdraft_payload = {
        "description": "Attempted excess withdrawal",
        "entries": [
            {"account_id": cash_id, "direction": "CREDIT", "amount": 15000},
            {"account_id": equity_id, "direction": "DEBIT", "amount": 15000},
        ],
    }

    od_res = await async_client.post(
        "/api/v1/transactions",
        headers={"Idempotency-Key": overdraft_key},
        json=overdraft_payload,
    )
    assert od_res.status_code == 422
    assert "InsufficientFundsError" in od_res.text

    # 6. Verify Cash balance was NOT mutated
    bal_res2 = await async_client.get(f"/api/v1/accounts/{cash_id}/balance")
    assert bal_res2.json()["balance"] == 10000
