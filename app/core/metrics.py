from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# Counter: ledger_transactions_total (labels: status, type)
LEDGER_TRANSACTIONS_TOTAL = Counter(
    "ledger_transactions_total",
    "Total count of financial ledger transactions processed.",
    labelnames=["status", "type"],
)

# Pre-initialize labeled metrics for initial scrape visibility
for s in ("POSTED", "FAILED"):
    for t in ("REGULAR", "REVERSAL"):
        LEDGER_TRANSACTIONS_TOTAL.labels(status=s, type=t)


# Histogram: ledger_transaction_duration_seconds with fine-grained buckets
# (5ms, 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s)
TRANSACTION_DURATION_BUCKETS = (
    0.005,
    0.010,
    0.025,
    0.050,
    0.100,
    0.250,
    0.500,
    1.000,
    2.500,
    5.000,
)

LEDGER_TRANSACTION_DURATION_SECONDS = Histogram(
    "ledger_transaction_duration_seconds",
    "Duration of double-entry ledger transaction processing in seconds.",
    buckets=TRANSACTION_DURATION_BUCKETS,
)

# Counter: ledger_serialization_retries_total
LEDGER_SERIALIZATION_RETRIES_TOTAL = Counter(
    "ledger_serialization_retries_total",
    "Total number of serializable isolation collision retries executed.",
)

# Counter: ledger_idempotency_hits_total
LEDGER_IDEMPOTENCY_HITS_TOTAL = Counter(
    "ledger_idempotency_hits_total",
    "Total number of transaction requests deduplicated via Redis idempotency cache.",
)

# Gauge: ledger_outbox_queue_depth
LEDGER_OUTBOX_QUEUE_DEPTH = Gauge(
    "ledger_outbox_queue_depth",
    "Current depth of pending domain events in the transactional outbox queue.",
)
