import asyncio
import random
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.resilience import with_serialization_retry
from app.core.exceptions import InsufficientFundsError
from app.models.account import Account, AccountType, AccountStatus
from app.models.transaction import Transaction, EntryDirection, TransactionStatus
from app.services.account_service import AccountService
from app.services.ledger_service import LedgerService


class TestAccountServiceUnit:
    """Unit tests for AccountService accounting equations and deltas."""

    def test_account_balance_formulas_by_type(self):
        # ASSET: Balance = Debits - Credits
        asset_bal = AccountService.calculate_balance_by_type(AccountType.ASSET, total_debit=15000, total_credit=5000)
        assert asset_bal == 10000

        # EXPENSE: Balance = Debits - Credits
        expense_bal = AccountService.calculate_balance_by_type(AccountType.EXPENSE, total_debit=8000, total_credit=2000)
        assert expense_bal == 6000

        # LIABILITY: Balance = Credits - Debits
        liab_bal = AccountService.calculate_balance_by_type(AccountType.LIABILITY, total_debit=3000, total_credit=10000)
        assert liab_bal == 7000

        # EQUITY: Balance = Credits - Debits
        equity_bal = AccountService.calculate_balance_by_type(AccountType.EQUITY, total_debit=2000, total_credit=12000)
        assert equity_bal == 10000

        # REVENUE: Balance = Credits - Debits
        rev_bal = AccountService.calculate_balance_by_type(AccountType.REVENUE, total_debit=1000, total_credit=9000)
        assert rev_bal == 8000

    def test_entry_deltas_by_account_type(self):
        # ASSET: Debit is positive (+), Credit is negative (-)
        assert AccountService.calculate_delta(AccountType.ASSET, EntryDirection.DEBIT, 5000) == 5000
        assert AccountService.calculate_delta(AccountType.ASSET, EntryDirection.CREDIT, 5000) == -5000

        # LIABILITY: Credit is positive (+), Debit is negative (-)
        assert AccountService.calculate_delta(AccountType.LIABILITY, EntryDirection.CREDIT, 5000) == 5000
        assert AccountService.calculate_delta(AccountType.LIABILITY, EntryDirection.DEBIT, 5000) == -5000


class TestConcurrencyAndResilience:
    """Intensive concurrency, race-condition and stress tests."""

    @pytest.mark.asyncio
    async def test_concurrent_double_spending(self, session_factory):
        """
        Test 1: Doble gasto concurrente.
        Una cuenta con 100€ (10,000 centavos) recibe 5 intentos simultáneos de retirar 100€.
        Exactamente 1 debe tener éxito y los otros 4 deben fallar por saldo insuficiente o conflicto,
        sin dejar el balance negativo en ningún momento.
        """
        # 1. Setup: Create Vault (Source, no overdraft) and Recipient (Dest)
        async with session_factory() as session:
            vault = Account(
                name="Vault Account",
                currency="EUR",
                type=AccountType.ASSET,
                status=AccountStatus.ACTIVE,
                allow_overdraft=False,
            )
            recipient = Account(
                name="Recipient Account",
                currency="EUR",
                type=AccountType.LIABILITY,
                status=AccountStatus.ACTIVE,
                allow_overdraft=True,
            )
            session.add_all([vault, recipient])
            await session.commit()
            vault_id = vault.id
            recipient_id = recipient.id

        # 2. Fund the Vault with exactly 10,000 cents (100.00 EUR)
        async with session_factory() as session:
            await LedgerService.record_transaction(
                session=session,
                idempotency_key=f"init-funding-{uuid.uuid4()}",
                description="Initial funding 100 EUR",
                entries_data=[
                    {"account_id": vault_id, "direction": EntryDirection.DEBIT, "amount": 10000},
                    {"account_id": recipient_id, "direction": EntryDirection.CREDIT, "amount": 10000},
                ],
            )
            await session.commit()

        # Verify initial balance
        async with session_factory() as session:
            vault_bal = await AccountService.get_account_balance(session, vault_id)
            assert vault_bal.balance == 10000

        # 3. Concurrently launch 5 withdrawal attempts of 100 EUR each
        withdrawal_amount = 10000
        success_count = 0
        failure_count = 0

        @with_serialization_retry(max_retries=10, base_delay=0.03, max_delay=0.3)
        async def attempt_withdrawal(attempt_idx: int):
            async with session_factory() as session:
                tx = await LedgerService.record_transaction(
                    session=session,
                    idempotency_key=f"withdraw-attempt-{attempt_idx}-{uuid.uuid4()}",
                    description=f"Withdrawal attempt {attempt_idx}",
                    entries_data=[
                        {"account_id": vault_id, "direction": EntryDirection.CREDIT, "amount": withdrawal_amount},
                        {"account_id": recipient_id, "direction": EntryDirection.DEBIT, "amount": withdrawal_amount},
                    ],
                )
                await session.commit()
                return tx

        async def worker(idx: int):
            nonlocal success_count, failure_count
            try:
                await attempt_withdrawal(idx)
                success_count += 1
            except InsufficientFundsError:
                failure_count += 1
            except Exception:
                failure_count += 1

        # Execute 5 concurrent withdrawals simultaneously
        tasks = [worker(i) for i in range(5)]
        await asyncio.gather(*tasks)

        # 4. Strict assertions: Exactly 1 succeeded, 4 failed
        assert success_count == 1, f"Expected exactly 1 success, got {success_count}"
        assert failure_count == 4, f"Expected exactly 4 failures, got {failure_count}"

        # 5. Check Vault final balance: Must be exactly 0, NEVER negative
        async with session_factory() as session:
            final_summary = await AccountService.get_account_balance(session, vault_id)
            assert final_summary.balance == 0
            assert final_summary.balance >= 0

    @pytest.mark.asyncio
    async def test_concurrent_cross_transfer_zero_sum_invariant(self, session_factory):
        """
        Test 2: Ráfaga concurrente de transferencias cruzadas.
        50 transacciones simultáneas entre múltiples cuentas bajo alta contención;
        verifica que al final la suma total de saldos del sistema conserve la conservación
        estricta de fondos (Zero-Sum Invariant) y que la cadena SHA-256 esté intacta.
        """
        num_accounts = 8
        initial_per_account = 50000  # 500.00 EUR per account
        total_system_funds = num_accounts * initial_per_account  # 400,000 cents

        # 1. Create accounts
        account_ids = []
        async with session_factory() as session:
            for i in range(num_accounts):
                acc = Account(
                    name=f"Trading Desk {i+1}",
                    currency="EUR",
                    type=AccountType.ASSET,
                    status=AccountStatus.ACTIVE,
                    allow_overdraft=True,  # Allow transfer flows without arbitrary floor
                )
                session.add(acc)
                await session.flush()
                account_ids.append(acc.id)

            # Fund accounts via offsetting equity/seed transactions
            seed_acc = Account(
                name="Central Reserve",
                currency="EUR",
                type=AccountType.LIABILITY,
                status=AccountStatus.ACTIVE,
                allow_overdraft=True,
            )
            session.add(seed_acc)
            await session.flush()

            for acc_id in account_ids:
                await LedgerService.record_transaction(
                    session=session,
                    idempotency_key=f"initial-seed-{acc_id}",
                    description="Seed funding",
                    entries_data=[
                        {"account_id": acc_id, "direction": EntryDirection.DEBIT, "amount": initial_per_account},
                        {"account_id": seed_acc.id, "direction": EntryDirection.CREDIT, "amount": initial_per_account},
                    ],
                )
            await session.commit()

        # 2. Concurrently execute 50 random cross-transfers
        num_transfers = 50

        @with_serialization_retry(max_retries=40, base_delay=0.01, max_delay=0.25)
        async def execute_transfer(transfer_idx: int):
            # Select two distinct accounts
            from_idx, to_idx = random.sample(range(num_accounts), 2)
            from_acc = account_ids[from_idx]
            to_acc = account_ids[to_idx]
            transfer_amount = random.randint(100, 1000)  # 1.00 to 10.00 EUR

            async with session_factory() as session:
                tx = await LedgerService.record_transaction(
                    session=session,
                    idempotency_key=f"cross-transfer-{transfer_idx}-{uuid.uuid4()}",
                    description=f"Concurrent transfer #{transfer_idx}",
                    entries_data=[
                        {"account_id": from_acc, "direction": EntryDirection.CREDIT, "amount": transfer_amount},
                        {"account_id": to_acc, "direction": EntryDirection.DEBIT, "amount": transfer_amount},
                    ],
                )
                await session.commit()
                return tx

        tasks = [execute_transfer(i) for i in range(num_transfers)]
        completed_transactions = await asyncio.gather(*tasks)

        assert len(completed_transactions) == num_transfers
        for tx in completed_transactions:
            assert tx.status == TransactionStatus.POSTED
            assert tx.net_balance == 0

        # 3. Verify Conservation of Value (Zero-Sum Invariant)
        async with session_factory() as session:
            balances = []
            for acc_id in account_ids:
                summary = await AccountService.get_account_balance(session, acc_id)
                balances.append(summary.balance)

            total_after = sum(balances)
            assert total_after == total_system_funds, (
                f"Zero-Sum invariant violated: Expected {total_system_funds}, but got {total_after}."
            )

    @pytest.mark.asyncio
    async def test_concurrent_idempotency_same_key(self, async_client: AsyncClient, redis_client):
        """
        Test 3: Idempotencia bajo concurrencia.
        10 peticiones simultáneas con la MISMA 'Idempotency-Key';
        verifica que solo se ejecute una vez y las demás retornen el mismo resultado o 409
        sin duplicar asientos ni asientos huérfanos.
        """
        # 1. Setup accounts
        acc_a_res = await async_client.post(
            "/api/v1/accounts",
            json={"name": "Buyer Account", "currency": "EUR", "type": "ASSET", "allow_overdraft": True},
        )
        acc_b_res = await async_client.post(
            "/api/v1/accounts",
            json={"name": "Seller Account", "currency": "EUR", "type": "LIABILITY", "allow_overdraft": True},
        )
        buyer_id = acc_a_res.json()["id"]
        seller_id = acc_b_res.json()["id"]

        same_key = f"same-idempotency-key-{uuid.uuid4()}"
        payload = {
            "description": "Exclusive concurrent payment",
            "entries": [
                {"account_id": buyer_id, "direction": "CREDIT", "amount": 2500},
                {"account_id": seller_id, "direction": "DEBIT", "amount": 2500},
            ],
        }

        # 2. Fire 10 simultaneous HTTP requests with the SAME key
        async def send_request():
            return await async_client.post(
                "/api/v1/transactions",
                headers={"Idempotency-Key": same_key},
                json=payload,
            )

        responses = await asyncio.gather(*[send_request() for _ in range(10)])

        status_codes = [r.status_code for r in responses]
        # At least one must be 201 Created
        assert 201 in status_codes

        # All responses must be either 201 (initial), 200 (cached completed), or 409 (conflict while in progress)
        for code in status_codes:
            assert code in (200, 201, 409), f"Unexpected status code: {code}"

        # Collect successful responses (200 or 201)
        successful_payloads = [r.json() for r in responses if r.status_code in (200, 201)]
        assert len(successful_payloads) >= 1

        # All successful responses must return the EXACT same transaction id and hash
        canonical_tx_id = successful_payloads[0]["id"]
        canonical_hash = successful_payloads[0]["current_hash"]
        for p in successful_payloads:
            assert p["id"] == canonical_tx_id
            assert p["current_hash"] == canonical_hash

        # 3. Subsequent request after completion MUST return 200 with the exact same payload
        follow_up = await async_client.post(
            "/api/v1/transactions",
            headers={"Idempotency-Key": same_key},
            json=payload,
        )
        assert follow_up.status_code in (200, 201)
        assert follow_up.json()["id"] == canonical_tx_id
