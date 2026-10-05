import json
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from app.core.config import settings
from app.models.account import Account, AccountType, AccountStatus
from app.models.outbox import OutboxEvent, OutboxStatus
from app.models.transaction import Transaction, EntryDirection, TransactionStatus
from app.services.account_service import AccountService
from app.services.ledger_service import LedgerService
from app.services.outbox_relay import OutboxRelay
from app.services.audit_service import AuditService
from app.services.reversal_service import ReversalService


class TestTransactionalOutbox:
    """Tests for the Transactional Outbox pattern and Redis Stream dispatching."""

    @pytest.mark.asyncio
    async def test_atomic_outbox_event_creation(self, db_session, sample_accounts):
        """
        Test 1: Verify that creating a transaction atomically creates an OutboxEvent
        with status PENDING and complete canonical payload within the same DB session.
        """
        acc_cash, acc_ap = sample_accounts
        acc_cash.allow_overdraft = True
        acc_ap.allow_overdraft = True
        idempotency_key = f"outbox-test-{uuid.uuid4()}"

        tx = await LedgerService.record_transaction(
            session=db_session,
            idempotency_key=idempotency_key,
            description="Payment to Vendor via Outbox",
            entries_data=[
                {"account_id": acc_cash.id, "direction": EntryDirection.CREDIT, "amount": 2500},
                {"account_id": acc_ap.id, "direction": EntryDirection.DEBIT, "amount": 2500},
            ],
        )


        assert tx.id is not None
        assert tx.status == TransactionStatus.POSTED

        # Query OutboxEvent within the same session
        stmt = select(OutboxEvent).where(OutboxEvent.aggregate_id == tx.id)
        outbox_event = (await db_session.execute(stmt)).scalar_one_or_none()

        assert outbox_event is not None
        assert outbox_event.event_type == "TRANSACTION_POSTED"
        assert outbox_event.aggregate_type == "TRANSACTION"
        assert outbox_event.status == OutboxStatus.PENDING
        assert outbox_event.published_at is None
        assert outbox_event.retry_count == 0

        payload = outbox_event.payload
        assert payload["transaction_id"] == str(tx.id)
        assert payload["idempotency_key"] == idempotency_key
        assert payload["description"] == "Payment to Vendor via Outbox"
        assert payload["prev_hash"] == tx.prev_hash
        assert payload["current_hash"] == tx.current_hash
        assert len(payload["entries"]) == 2

    @pytest.mark.asyncio
    async def test_outbox_relay_publishes_to_redis_stream(self, session_factory, redis_client):
        """
        Test 2: Execute the OutboxRelay worker (process_batch), verify event transitions
        to PUBLISHED, published_at is set, and the message is in the Redis Stream.
        """
        # 1. Setup accounts and transaction committed to DB
        async with session_factory() as session:
            acc_a = Account(
                name="Relay Test Cash",
                currency="EUR",
                type=AccountType.ASSET,
                status=AccountStatus.ACTIVE,
                allow_overdraft=True,
            )
            acc_b = Account(
                name="Relay Test AP",
                currency="EUR",
                type=AccountType.LIABILITY,
                status=AccountStatus.ACTIVE,
                allow_overdraft=True,
            )
            session.add_all([acc_a, acc_b])
            await session.commit()
            acc_a_id, acc_b_id = acc_a.id, acc_b.id

        tx_id = None
        async with session_factory() as session:
            tx = await LedgerService.record_transaction(
                session=session,
                idempotency_key=f"relay-test-{uuid.uuid4()}",
                description="Relay Stream Posting",
                entries_data=[
                    {"account_id": acc_a_id, "direction": EntryDirection.CREDIT, "amount": 4000},
                    {"account_id": acc_b_id, "direction": EntryDirection.DEBIT, "amount": 4000},
                ],
            )
            await session.commit()
            tx_id = tx.id

        # 2. Run Relay batch processing (drain all pending events)
        relay = OutboxRelay(session_factory=session_factory, redis_client=redis_client)
        total_published = 0
        while True:
            batch_count = await relay.process_batch()
            total_published += batch_count
            if batch_count == 0:
                break
        assert total_published >= 1


        # 3. Verify OutboxEvent status in DB
        async with session_factory() as session:
            stmt = select(OutboxEvent).where(OutboxEvent.aggregate_id == tx_id)
            outbox_event = (await session.execute(stmt)).scalar_one()
            assert outbox_event.status == OutboxStatus.PUBLISHED
            assert outbox_event.published_at is not None

        # 4. Verify message in Redis Stream
        stream_messages = await redis_client.xrange(relay.stream_key)
        assert len(stream_messages) >= 1

        # Find the message corresponding to this transaction
        found_in_stream = False
        for msg_id, fields in stream_messages:
            if fields.get("aggregate_id") == str(tx_id):
                found_in_stream = True
                assert fields.get("event_type") == "TRANSACTION_POSTED"
                assert fields.get("aggregate_type") == "TRANSACTION"
                payload = json.loads(fields.get("payload"))
                assert payload["transaction_id"] == str(tx_id)
                break
        assert found_in_stream, f"Transaction {tx_id} was not found in Redis Stream"


class TestImmutableReversalsAndAudit:
    """Tests for Storno reversals and cryptographic audit trail verification."""

    @pytest.mark.asyncio
    async def test_immutable_reversal_restores_balances(self, session_factory):
        """
        Test 3: Transaction reversal (storno): verify that reversing a transaction
        exactly restores previous balances without mutating the original transaction,
        and produces a 'TRANSACTION_REVERSED' OutboxEvent.
        """
        # 1. Create accounts: Vault (Asset) and Vendor (Expense)
        async with session_factory() as session:
            vault = Account(
                name="Vault Reserve",
                currency="EUR",
                type=AccountType.ASSET,
                status=AccountStatus.ACTIVE,
                allow_overdraft=False,
            )
            vendor = Account(
                name="Vendor Expense",
                currency="EUR",
                type=AccountType.EXPENSE,
                status=AccountStatus.ACTIVE,
                allow_overdraft=True,
            )
            session.add_all([vault, vendor])
            await session.commit()
            vault_id, vendor_id = vault.id, vendor.id

        # 2. Fund the Vault with 100 EUR (10,000 cents)
        async with session_factory() as session:
            await LedgerService.record_transaction(
                session=session,
                idempotency_key=f"fund-vault-{uuid.uuid4()}",
                description="Capital funding",
                entries_data=[
                    {"account_id": vault_id, "direction": EntryDirection.DEBIT, "amount": 10000},
                    {"account_id": vendor_id, "direction": EntryDirection.CREDIT, "amount": 10000},
                ],
            )
            await session.commit()

        # 3. Execute original transfer: 30 EUR (3,000 cents) from Vault to Vendor
        tx_original_id = None
        async with session_factory() as session:
            tx_original = await LedgerService.record_transaction(
                session=session,
                idempotency_key=f"pay-vendor-{uuid.uuid4()}",
                description="Payment to vendor #101",
                entries_data=[
                    {"account_id": vault_id, "direction": EntryDirection.CREDIT, "amount": 3000},
                    {"account_id": vendor_id, "direction": EntryDirection.DEBIT, "amount": 3000},
                ],
            )
            await session.commit()
            tx_original_id = tx_original.id
            original_hash = tx_original.current_hash

        # Verify intermediate balances: Vault should have 7000 cents
        async with session_factory() as session:
            bal_vault = await AccountService.get_account_balance(session, vault_id)
            assert bal_vault.balance == 7000

        # 4. Reverse the transaction (compensating entry / storno)
        reversal_id = None
        async with session_factory() as session:
            reversal_tx = await ReversalService.reverse_transaction(
                session=session,
                transaction_id=tx_original_id,
                idempotency_key=f"rev-pay-{uuid.uuid4()}",
                reason="Accidental double billing",
            )
            await session.commit()
            reversal_id = reversal_tx.id

        # 5. Assert balances are restored exactly
        async with session_factory() as session:
            bal_vault_restored = await AccountService.get_account_balance(session, vault_id)
            assert bal_vault_restored.balance == 10000

        # 6. Assert original transaction is unmodified (immutable)
        async with session_factory() as session:
            stmt = select(Transaction).where(Transaction.id == tx_original_id)
            orig_check = (await session.execute(stmt)).scalar_one()
            assert orig_check.status == TransactionStatus.POSTED
            assert orig_check.current_hash == original_hash

            # Verify reversal transaction details
            stmt_rev = (
                select(Transaction)
                .where(Transaction.id == reversal_id)
                .options(selectinload(Transaction.entries))
            )
            rev_check = (await session.execute(stmt_rev)).scalar_one()
            assert rev_check.prev_hash == original_hash
            assert rev_check.description.startswith(f"Reversal of [{tx_original_id}]")

            # Check reversal outbox event
            stmt_outbox = select(OutboxEvent).where(OutboxEvent.aggregate_id == reversal_id)
            rev_outbox = (await session.execute(stmt_outbox)).scalar_one()
            assert rev_outbox.event_type == "TRANSACTION_REVERSED"

    @pytest.mark.asyncio
    async def test_cryptographic_audit_clean_and_tampered(self, session_factory):
        """
        Test 4: Cryptographic integrity audit:
        - Consecutive ledger transactions pass audit with is_valid=True.
        - Tampering with an intermediate transaction's hash or payload is immediately
          detected with is_valid=False and broken_link_at accurately identifying the row.
        """
        # Ensure at least two sequential transactions exist in the ledger
        async with session_factory() as session:
            a1 = Account(
                name="Audit Account A",
                currency="EUR",
                type=AccountType.ASSET,
                status=AccountStatus.ACTIVE,
                allow_overdraft=True,
            )
            a2 = Account(
                name="Audit Account B",
                currency="EUR",
                type=AccountType.LIABILITY,
                status=AccountStatus.ACTIVE,
                allow_overdraft=True,
            )
            session.add_all([a1, a2])
            await session.commit()
            a1_id, a2_id = a1.id, a2.id

        async with session_factory() as session:
            await LedgerService.record_transaction(
                session=session,
                idempotency_key=f"audit-tx-1-{uuid.uuid4()}",
                description="Audit Transaction Leg 1",
                entries_data=[
                    {"account_id": a1_id, "direction": EntryDirection.DEBIT, "amount": 5000},
                    {"account_id": a2_id, "direction": EntryDirection.CREDIT, "amount": 5000},
                ],
            )
            await LedgerService.record_transaction(
                session=session,
                idempotency_key=f"audit-tx-2-{uuid.uuid4()}",
                description="Audit Transaction Leg 2",
                entries_data=[
                    {"account_id": a1_id, "direction": EntryDirection.CREDIT, "amount": 2000},
                    {"account_id": a2_id, "direction": EntryDirection.DEBIT, "amount": 2000},
                ],
            )
            await session.commit()

        # 1. Clean audit verification
        async with session_factory() as session:
            clean_report = await AuditService.verify_ledger_integrity(session)
            assert clean_report["is_valid"] is True
            assert clean_report["broken_link_at"] is None
            assert clean_report["total_transactions_verified"] >= 2

        # 2. Pick the latest transaction to simulate malicious tampering
        async with session_factory() as session:
            stmt = (
                select(Transaction)
                .order_by(Transaction.created_at.desc(), Transaction.id.desc())
                .limit(1)
            )
            target_tx = (await session.execute(stmt)).scalar_one()
            tamper_tx_id = target_tx.id
            real_hash = target_tx.current_hash

            # Alter the hash fraudulently directly in DB
            tampered_fake_hash = "deadbeef" * 8
            await session.execute(
                update(Transaction)
                .where(Transaction.id == tamper_tx_id)
                .values(current_hash=tampered_fake_hash)
            )
            await session.commit()

        # 3. Run audit on tampered ledger -> MUST fail
        try:
            async with session_factory() as session:
                tampered_report = await AuditService.verify_ledger_integrity(session)
                assert tampered_report["is_valid"] is False
                assert tampered_report["broken_link_at"] == tamper_tx_id
                assert "Tampered transaction payload detected" in tampered_report["details"]
        finally:
            # 4. Repair the cryptographic hash to maintain clean state
            async with session_factory() as session:
                await session.execute(
                    update(Transaction)
                    .where(Transaction.id == tamper_tx_id)
                    .values(current_hash=real_hash)
                )
                await session.commit()

        # 5. Confirm ledger integrity is restored
        async with session_factory() as session:
            restored_report = await AuditService.verify_ledger_integrity(session)
            assert restored_report["is_valid"] is True
            assert restored_report["broken_link_at"] is None

    @pytest.mark.asyncio
    async def test_reversal_and_audit_api_endpoints(self, async_client: AsyncClient, redis_client):
        """
        Integration test verifying:
        - GET /api/v1/ledger/audit returns 200 with integrity report.
        - POST /api/v1/transactions/{id}/reversal creates reversal and is idempotent.
        """
        # 1. Create two accounts via API
        r_acc1 = await async_client.post("/api/v1/accounts", json={
            "name": "API Source Vault",
            "currency": "EUR",
            "type": "ASSET",
            "allow_overdraft": True,
        })
        assert r_acc1.status_code == 201
        acc1_id = r_acc1.json()["id"]

        r_acc2 = await async_client.post("/api/v1/accounts", json={
            "name": "API Target AP",
            "currency": "EUR",
            "type": "LIABILITY",
            "allow_overdraft": True,
        })
        assert r_acc2.status_code == 201
        acc2_id = r_acc2.json()["id"]

        # 2. Post a transaction via API
        idempotency_key = f"api-tx-{uuid.uuid4()}"
        r_tx = await async_client.post(
            "/api/v1/transactions",
            headers={"Idempotency-Key": idempotency_key},
            json={
                "description": "API Transfer to be reversed",
                "entries": [
                    {"account_id": acc1_id, "direction": "CREDIT", "amount": 1500},
                    {"account_id": acc2_id, "direction": "DEBIT", "amount": 1500},
                ],
            },
        )
        assert r_tx.status_code == 201
        tx_data = r_tx.json()
        tx_id = tx_data["id"]

        # 3. Call Reversal API
        rev_idempotency_key = f"api-rev-{uuid.uuid4()}"
        r_rev = await async_client.post(
            f"/api/v1/transactions/{tx_id}/reversal",
            headers={"Idempotency-Key": rev_idempotency_key},
            json={"reason": "Customer cancellation request"},
        )
        assert r_rev.status_code == 201
        rev_data = r_rev.json()
        assert rev_data["idempotency_key"] == rev_idempotency_key
        assert f"Reversal of [{tx_id}]" in rev_data["description"]

        # 4. Verify Reversal Idempotency
        r_rev_dup = await async_client.post(
            f"/api/v1/transactions/{tx_id}/reversal",
            headers={"Idempotency-Key": rev_idempotency_key},
            json={"reason": "Customer cancellation request"},
        )
        assert r_rev_dup.status_code == 200
        assert r_rev_dup.json()["id"] == rev_data["id"]

        # 5. Call Audit API
        r_audit = await async_client.get("/api/v1/ledger/audit")
        assert r_audit.status_code == 200
        audit_data = r_audit.json()
        assert audit_data["is_valid"] is True
        assert audit_data["broken_link_at"] is None
        assert audit_data["total_transactions_verified"] >= 2
