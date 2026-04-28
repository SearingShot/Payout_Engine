"""
Payout service — handles payout creation with concurrency control,
idempotency, and state machine enforcement.

This is the core business logic of the payout engine.
"""

import logging
from django.db import transaction
from django.db.models import Sum, Case, When, Value, BigIntegerField, F as models_F
from django.utils import timezone

from core.models import Merchant, LedgerEntry, Payout, IdempotencyKey, BankAccount

logger = logging.getLogger(__name__)


class InsufficientBalance(Exception):
    """Raised when merchant doesn't have enough available balance."""
    pass


class InvalidStateTransition(Exception):
    """Raised when an illegal payout state transition is attempted."""
    pass


class DuplicateIdempotencyKey(Exception):
    """Raised when a duplicate idempotency key is detected (returns cached response)."""

    def __init__(self, cached_response, cached_status):
        self.cached_response = cached_response
        self.cached_status = cached_status
        super().__init__("Duplicate idempotency key")


# ---------------------------------------------------------------------------
# State machine — legal transitions
# ---------------------------------------------------------------------------

VALID_TRANSITIONS = {
    "pending": ["processing"],
    "processing": ["completed", "failed"],
    "completed": [],  # terminal state — no transitions allowed
    "failed": [],  # terminal state — no transitions allowed
}


def transition_payout_status(payout, new_status):
    """
    Enforce the payout state machine.

    Legal:   pending → processing → completed
             pending → processing → failed
    Illegal: completed → anything, failed → anything, any backward move

    Raises InvalidStateTransition if the transition is not allowed.
    """
    allowed = VALID_TRANSITIONS.get(payout.status, [])
    if new_status not in allowed:
        raise InvalidStateTransition(
            f"Cannot transition payout {payout.id} from '{payout.status}' to '{new_status}'. "
            f"Allowed transitions from '{payout.status}': {allowed or 'none (terminal state)'}"
        )
    payout.status = new_status
    payout.save(update_fields=["status", "updated_at"])
    logger.info(f"Payout {payout.id} transitioned to '{new_status}'")


# ---------------------------------------------------------------------------
# Balance computation — always at database level
# ---------------------------------------------------------------------------

def get_merchant_balance(merchant_id):
    """
    Compute available balance entirely in the database.

    Returns a dict with:
        - available_balance: total credits minus total debits (in paise)
        - total_credits: sum of all credit entries
        - total_debits: sum of all debit entries

    This uses Django's ORM aggregate which translates to a single SQL query:
        SELECT SUM(CASE WHEN entry_type='credit' THEN amount_paise
                        ELSE -amount_paise END) FROM core_ledgerentry
        WHERE merchant_id = %s
    """
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

    return {
        "available_balance": result["available_balance"] or 0,
        "total_credits": result["total_credits"] or 0,
        "total_debits": result["total_debits"] or 0,
    }


def get_held_balance(merchant_id):
    """
    Held balance = sum of debits for payouts that are still pending or processing.

    These funds are earmarked but not yet settled.
    """
    held = (
        Payout.objects.filter(
            merchant_id=merchant_id, status__in=["pending", "processing"]
        ).aggregate(held=Sum("amount_paise"))["held"]
        or 0
    )
    return held


# ---------------------------------------------------------------------------
# Payout creation — the critical path
# ---------------------------------------------------------------------------

def create_payout(merchant_id, amount_paise, bank_account_id, idempotency_key):
    """
    Create a payout request with full concurrency and idempotency protection.

    Flow:
    1. Check idempotency key — return cached response if duplicate
    2. Inside a DB transaction with SELECT FOR UPDATE:
       a. Lock the merchant's ledger rows to prevent concurrent balance reads
       b. Compute available balance at DB level
       c. Reject if insufficient funds
       d. Create payout record (status='pending')
       e. Create debit ledger entry (holds the funds)
       f. Cache the response in IdempotencyKey table
    3. Return the payout data

    The SELECT FOR UPDATE ensures that if two concurrent requests hit this
    function, the second one will BLOCK at step 2a until the first commits.
    After the first commits its debit, the second correctly sees reduced balance.
    """
    # Validate inputs
    if amount_paise <= 0:
        raise ValueError("amount_paise must be positive")

    # Validate merchant exists
    try:
        merchant = Merchant.objects.get(id=merchant_id)
    except Merchant.DoesNotExist:
        raise ValueError(f"Merchant {merchant_id} not found")

    # Validate bank account exists and belongs to merchant
    if not BankAccount.objects.filter(id=bank_account_id, merchant=merchant).exists():
        raise ValueError(f"Bank account {bank_account_id} not found for merchant {merchant_id}")

    # ---- Step 1: Check idempotency key ----
    # Clean up expired keys first
    IdempotencyKey.objects.filter(
        merchant=merchant, expires_at__lt=timezone.now()
    ).delete()

    existing_key = IdempotencyKey.objects.filter(
        key=idempotency_key, merchant=merchant
    ).first()

    if existing_key:
        if existing_key.is_expired:
            existing_key.delete()
        else:
            # Return the cached response — no new payout created
            logger.info(
                f"Idempotency key {idempotency_key[:8]}... already used for merchant {merchant_id}. "
                f"Returning cached response."
            )
            raise DuplicateIdempotencyKey(
                cached_response=existing_key.response_data,
                cached_status=existing_key.response_status,
            )

    # ---- Step 2: Atomic transaction with row-level locking ----
    with transaction.atomic():
        # Serialize payout creation per merchant. This protects both balance
        # checks and duplicate idempotency keys that arrive while the first
        # request is still in flight.
        merchant = Merchant.objects.select_for_update().get(id=merchant.id)

        IdempotencyKey.objects.filter(
            merchant=merchant, expires_at__lt=timezone.now()
        ).delete()

        existing_key = IdempotencyKey.objects.filter(
            key=idempotency_key, merchant=merchant
        ).first()

        if existing_key:
            logger.info(
                f"Idempotency key {idempotency_key[:8]}... already used for merchant {merchant_id}. "
                f"Returning cached response."
            )
            raise DuplicateIdempotencyKey(
                cached_response=existing_key.response_data,
                cached_status=existing_key.response_status,
            )

        # 2b. Compute available balance at database level while holding the
        # merchant row lock. PostgreSQL does not allow SELECT FOR UPDATE with
        # aggregate queries, so the merchant row is the lock target.
        locked_entries = LedgerEntry.objects.filter(merchant=merchant)

        balance_result = locked_entries.aggregate(
            available=Sum(
                Case(
                    When(entry_type="credit", then="amount_paise"),
                    When(entry_type="debit", then=Value(0) - models_F("amount_paise")),
                    output_field=BigIntegerField(),
                )
            )
        )
        available_balance = balance_result["available"] or 0

        # 2c. Reject if insufficient funds
        if available_balance < amount_paise:
            raise InsufficientBalance(
                f"Insufficient balance. Available: {available_balance} paise, "
                f"Requested: {amount_paise} paise"
            )

        # 2d. Create payout record
        payout = Payout.objects.create(
            merchant=merchant,
            amount_paise=amount_paise,
            bank_account_id=bank_account_id,
            status="pending",
            idempotency_key=idempotency_key,
        )

        # 2e. Create debit ledger entry — this atomically reduces the balance
        LedgerEntry.objects.create(
            merchant=merchant,
            entry_type="debit",
            amount_paise=amount_paise,
            reference_type="payout_hold",
            reference_id=payout.id,
            description=f"Funds held for payout {payout.id}",
        )

        # 2f. Build and cache the response
        response_data = {
            "id": str(payout.id),
            "merchant_id": merchant.id,
            "amount_paise": payout.amount_paise,
            "bank_account_id": payout.bank_account_id,
            "status": payout.status,
            "created_at": payout.created_at.isoformat(),
        }

        IdempotencyKey.objects.create(
            key=idempotency_key,
            merchant=merchant,
            response_data=response_data,
            response_status=201,
        )

        logger.info(
            f"Payout {payout.id} created for merchant {merchant_id}: "
            f"{amount_paise} paise (balance after hold: {available_balance - amount_paise})"
        )

        return response_data


# ---------------------------------------------------------------------------
# Fund return — atomic reversal on payout failure
# ---------------------------------------------------------------------------

def return_funds(payout):
    """
    Atomically transition a payout to 'failed' and return funds to the merchant.

    Both operations happen in a single transaction — if either fails,
    neither is committed.
    """
    with transaction.atomic():
        # Re-fetch with lock to prevent race conditions
        payout = Payout.objects.select_for_update().get(id=payout.id)

        if payout.status not in ("processing",):
            raise InvalidStateTransition(
                f"Cannot return funds for payout {payout.id} in status '{payout.status}'"
            )

        payout.status = "failed"
        payout.save(update_fields=["status", "updated_at"])

        # Create credit entry to return the held funds
        LedgerEntry.objects.create(
            merchant=payout.merchant,
            entry_type="credit",
            amount_paise=payout.amount_paise,
            reference_type="payout_reversal",
            reference_id=payout.id,
            description=f"Funds returned: payout {payout.id} failed — {payout.failure_reason}",
        )

        logger.info(
            f"Funds returned for payout {payout.id}: {payout.amount_paise} paise "
            f"back to merchant {payout.merchant_id}"
        )
