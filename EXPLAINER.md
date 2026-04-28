# Playto Payout Engine - Explainer

## 1. The Ledger

Balance calculation query:

```python
result = LedgerEntry.objects.filter(merchant_id=merchant_id).aggregate(
    available_balance=Sum(
        Case(
            When(entry_type="credit", then="amount_paise"),
            When(entry_type="debit", then=Value(0) - models_F("amount_paise")),
            output_field=BigIntegerField(),
        )
    ),
    total_credits=Sum(
        Case(
            When(entry_type="credit", then="amount_paise"),
            default=Value(0),
            output_field=BigIntegerField(),
        )
    ),
    total_debits=Sum(
        Case(
            When(entry_type="debit", then="amount_paise"),
            default=Value(0),
            output_field=BigIntegerField(),
        )
    ),
)
```

Credits and debits are append-only `LedgerEntry` rows. Amounts are stored as positive `BigIntegerField` values in paise; the sign comes from `entry_type`. I modeled it this way because the displayed balance must be derivable from the audit trail. There is no cached mutable balance column that can drift from ledger history.

## 2. The Lock

The critical section is in `core/services/payout_service.py`:

```python
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant.id)

    existing_key = IdempotencyKey.objects.filter(
        key=idempotency_key, merchant=merchant
    ).first()
    if existing_key:
        raise DuplicateIdempotencyKey(
            cached_response=existing_key.response_data,
            cached_status=existing_key.response_status,
        )

    balance_result = LedgerEntry.objects.filter(merchant=merchant).aggregate(
        available=Sum(
            Case(
                When(entry_type="credit", then="amount_paise"),
                When(entry_type="debit", then=Value(0) - models_F("amount_paise")),
                output_field=BigIntegerField(),
            )
        )
    )
```

This relies on PostgreSQL row-level pessimistic locking through `SELECT ... FOR UPDATE`. The merchant row is the serialization point for payout creation. Two payout requests for the same merchant cannot both check the old balance; the second blocks until the first transaction commits, then recalculates the balance after the first debit exists. I lock the merchant row instead of the aggregate query because PostgreSQL does not allow `SELECT FOR UPDATE` directly on aggregate results.

## 3. The Idempotency

The system stores each merchant-supplied `Idempotency-Key` in `IdempotencyKey`, scoped by `(key, merchant)` and expiring after 24 hours. The response body and original status code are cached on that row.

If the first request is still in flight when the second arrives, the second request blocks on the same merchant row lock. After the first request commits its payout, ledger debit, and cached response, the second request wakes up, re-checks `IdempotencyKey`, and returns the cached response. No second payout is created.

The database also has uniqueness constraints on `(idempotency_key, merchant)` in `Payout` and `(key, merchant)` in `IdempotencyKey`, so the database enforces the same invariant if application code regresses.

## 4. The State Machine

Legal transitions are defined in `core/services/payout_service.py`:

```python
VALID_TRANSITIONS = {
    "pending": ["processing"],
    "processing": ["completed", "failed"],
    "completed": [],
    "failed": [],
}

def transition_payout_status(payout, new_status):
    allowed = VALID_TRANSITIONS.get(payout.status, [])
    if new_status not in allowed:
        raise InvalidStateTransition(...)
```

`failed -> completed` is blocked because `VALID_TRANSITIONS["failed"]` is empty. `completed` and `failed` are terminal states.

Failed payout fund return is handled in one transaction in `return_funds()`: it locks the payout row, verifies the current status is `processing`, marks it `failed`, and writes the reversal credit ledger entry atomically.

## 5. The AI Audit

The subtle wrong version AI suggested was:

```python
available_balance = get_merchant_balance(merchant.id)
if available_balance < amount_paise:
    raise InsufficientBalance()

payout = Payout.objects.create(...)
LedgerEntry.objects.create(entry_type="debit", ...)
```

That is a check-then-act race. If a merchant has 100 rupees and two 60 rupee requests arrive together, both can read 100 before either writes the debit.

I replaced it with a transaction and a `SELECT ... FOR UPDATE` lock on the merchant row before checking idempotency and balance:

```python
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant.id)
    # check idempotency, aggregate balance, create payout, write ledger debit
```

I also changed the initial idea of locking ledger rows with `select_for_update().aggregate(...)`. That is not the right primitive for PostgreSQL because aggregate rows are not lockable in the way ordinary table rows are. The merchant row gives a concrete row to lock and serializes all payout creation for that merchant.
