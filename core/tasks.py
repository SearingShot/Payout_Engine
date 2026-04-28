"""
Celery tasks for the payout processor.

Task 1: process_pending_payouts — picks up pending payouts, simulates bank settlement
Task 2: retry_stuck_payouts — retries payouts stuck in processing > 30 seconds
"""

import random
import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from core.models import Payout, LedgerEntry
from core.services.payout_service import (
    transition_payout_status,
    return_funds,
    InvalidStateTransition,
)

logger = logging.getLogger(__name__)


@shared_task(name="core.tasks.process_pending_payouts")
def process_pending_payouts():
    """
    Pick up all pending payouts and move them through the settlement lifecycle.

    For each pending payout:
    1. Transition to 'processing'
    2. Simulate bank settlement:
       - 70% chance: succeed → transition to 'completed'
       - 20% chance: fail → transition to 'failed', return funds
       - 10% chance: hang → leave in 'processing' (retry task will catch it)
    """
    pending_payouts = Payout.objects.filter(status="pending")
    count = pending_payouts.count()

    if count == 0:
        return "No pending payouts"

    logger.info(f"Processing {count} pending payout(s)")

    results = {"processed": 0, "completed": 0, "failed": 0, "hung": 0}

    for payout in pending_payouts:
        try:
            with transaction.atomic():
                # Lock the payout row to prevent concurrent processing
                payout = Payout.objects.select_for_update().get(id=payout.id)

                # Double-check status (could have changed between filter and lock)
                if payout.status != "pending":
                    continue

                # Transition to processing
                payout.status = "processing"
                payout.processing_started_at = timezone.now()
                payout.attempts = F("attempts") + 1
                payout.save(update_fields=["status", "processing_started_at", "attempts", "updated_at"])

            # Refresh to get actual attempts value after F() expression
            payout.refresh_from_db()
            results["processed"] += 1

            # Simulate bank settlement outcome
            outcome = random.random()

            if outcome < 0.70:
                # SUCCESS — 70% chance
                _settle_payout_success(payout)
                results["completed"] += 1

            elif outcome < 0.90:
                # FAIL — 20% chance
                _settle_payout_failure(payout, "Bank rejected the transaction")
                results["failed"] += 1

            else:
                # HANG — 10% chance — leave in processing
                logger.info(f"Payout {payout.id} simulating bank hang (attempt {payout.attempts})")
                results["hung"] += 1

        except Exception as e:
            logger.error(f"Error processing payout {payout.id}: {e}")

    logger.info(f"Payout processing results: {results}")
    return results


@shared_task(name="core.tasks.retry_stuck_payouts")
def retry_stuck_payouts():
    """
    Find payouts stuck in 'processing' for more than 30 seconds and retry them.

    Retry logic:
    - Exponential backoff: wait 30s * 2^(attempts-1) before retrying
    - Max 3 attempts total
    - After 3 failed attempts, move to 'failed' and return funds
    """
    cutoff = timezone.now() - timedelta(seconds=30)

    stuck_payouts = Payout.objects.filter(
        status="processing",
        processing_started_at__lt=cutoff,
    )

    count = stuck_payouts.count()
    if count == 0:
        return "No stuck payouts"

    logger.info(f"Found {count} stuck payout(s)")

    results = {"retried": 0, "completed": 0, "failed": 0, "max_retries_exceeded": 0}

    for payout in stuck_payouts:
        try:
            with transaction.atomic():
                payout = Payout.objects.select_for_update().get(id=payout.id)

                # Double-check it's still stuck
                if payout.status != "processing":
                    continue

                if payout.attempts >= 3:
                    # Max retries exceeded — fail and return funds
                    payout.failure_reason = f"Max retries exceeded ({payout.attempts} attempts)"
                    payout.save(update_fields=["failure_reason", "updated_at"])

                    # return_funds handles its own transaction
                    # but we need to release the lock first
                    _fail_and_return = True
                else:
                    _fail_and_return = False

                    # Check exponential backoff: 30s * 2^(attempts-1)
                    backoff_seconds = 30 * (2 ** (payout.attempts - 1))
                    retry_after = payout.processing_started_at + timedelta(seconds=backoff_seconds)

                    if timezone.now() < retry_after:
                        # Not time to retry yet
                        continue

                    # Reset for retry
                    payout.processing_started_at = timezone.now()
                    payout.attempts = F("attempts") + 1
                    payout.save(update_fields=["processing_started_at", "attempts", "updated_at"])

            if _fail_and_return:
                return_funds(payout)
                results["max_retries_exceeded"] += 1
                logger.info(f"Payout {payout.id} failed after max retries")
                continue

            # Refresh to get actual attempts value
            payout.refresh_from_db()
            results["retried"] += 1

            # Re-simulate bank settlement
            outcome = random.random()

            if outcome < 0.70:
                _settle_payout_success(payout)
                results["completed"] += 1
            elif outcome < 0.90:
                _settle_payout_failure(payout, f"Bank rejected on retry (attempt {payout.attempts})")
                results["failed"] += 1
            else:
                logger.info(f"Payout {payout.id} still hanging (attempt {payout.attempts})")

        except Exception as e:
            logger.error(f"Error retrying payout {payout.id}: {e}")

    logger.info(f"Retry results: {results}")
    return results


# ---------------------------------------------------------------------------
# Internal settlement helpers
# ---------------------------------------------------------------------------

def _settle_payout_success(payout):
    """Mark payout as completed. The debit ledger entry already exists."""
    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout.id)
        if payout.status != "processing":
            return
        payout.status = "completed"
        payout.save(update_fields=["status", "updated_at"])
    logger.info(f"Payout {payout.id} completed successfully")


def _settle_payout_failure(payout, reason):
    """Mark payout as failed and return funds atomically."""
    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout.id)
        if payout.status != "processing":
            return
        payout.status = "failed"
        payout.failure_reason = reason
        payout.save(update_fields=["status", "failure_reason", "updated_at"])

        # Return the held funds
        LedgerEntry.objects.create(
            merchant=payout.merchant,
            entry_type="credit",
            amount_paise=payout.amount_paise,
            reference_type="payout_reversal",
            reference_id=payout.id,
            description=f"Funds returned: {reason}",
        )

    logger.info(f"Payout {payout.id} failed: {reason}. Funds returned.")
