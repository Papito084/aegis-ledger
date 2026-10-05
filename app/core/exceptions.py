class LedgerDomainError(Exception):
    """Base exception for all domain invariant violations in Aegis Ledger."""
    pass


class UnbalancedTransactionError(LedgerDomainError):
    """Raised when sum(Debits) != sum(Credits)."""
    pass


class InvalidEntryAmountError(LedgerDomainError):
    """Raised when an entry amount is <= 0 or not an exact integer."""
    pass


class InsufficientEntriesError(LedgerDomainError):
    """Raised when a transaction does not contain at least two entries."""
    pass


class InsufficientFundsError(LedgerDomainError):
    """Raised when an entry would result in a negative balance and overdraft is not allowed."""
    pass


class AccountNotFoundError(LedgerDomainError):
    """Raised when a referenced account does not exist."""
    pass


class TransactionNotFoundError(LedgerDomainError):
    """Raised when a referenced transaction does not exist."""
    pass


class InactiveAccountError(LedgerDomainError):
    """Raised when trying to post an entry to a frozen or closed account."""
    pass


class CurrencyMismatchError(LedgerDomainError):
    """Raised when accounts in a single transaction have mismatched currencies."""
    pass


class ConcurrentTransactionConflictError(Exception):
    """Raised when a transaction with the same idempotency key is already in progress."""
    def __init__(self, key: str):
        super().__init__(f"Transaction with Idempotency-Key '{key}' is currently being processed.")
        self.key = key
