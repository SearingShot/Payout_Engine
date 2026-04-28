"""
Tests for the payout engine.

Focuses on the three most critical properties:
1. Concurrency — two simultaneous payouts cannot overdraw
2. Idempotency — same key returns same response, no duplicate
3. State machine — illegal transitions are rejected
"""

import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal

from django.test import TestCase, TransactionTestCase
from django.test.client import Client
from django.db import connection

from core.models import Merchant, BankAccount, LedgerEntry, Payout, IdempotencyKey
from core.services.payout_service import (
    create_payout,
    get_merchant_balance,
    transition_payout_status,
    return_funds,
    InsufficientBalance,
    InvalidStateTransition,
    DuplicateIdempotencyKey,
)


class LedgerIntegrityTest(TestCase):
    """Verify that balance is always computed from the ledger, not cached."""

    def setUp(self):
        self.merchant = Merchant.objects.create(name="Test Merchant", email="test@test.com")
        self.bank_account = BankAccount.objects.create(
            merchant=self.merchant,
            account_number="1234567890",
            ifsc_code="TEST0001234",
            account_holder_name="Test Merchant",
        )

    def test_balance_equals_credits_minus_debits(self):
        """Balance must always equal SUM(credits) - SUM(debits)."""
        # Add credits
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type="credit",
            amount_paise=10000_00,  # ₹10,000
            reference_type="customer_payment",
            description="Payment 1",
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type="credit",
            amount_paise=5000_00,  # ₹5,000
            reference_type="customer_payment",
            description="Payment 2",
        )

        balance_info = get_merchant_balance(self.merchant.id)
        self.assertEqual(balance_info["available_balance"], 15000_00)
        self.assertEqual(balance_info["total_credits"], 15000_00)
        self.assertEqual(balance_info["total_debits"], 0)

        # Add a debit
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type="debit",
            amount_paise=3000_00,  # ₹3,000
            reference_type="payout_hold",
            description="Payout hold",
        )

        balance_info = get_merchant_balance(self.merchant.id)
        self.assertEqual(balance_info["available_balance"], 12000_00)
        self.assertEqual(balance_info["total_credits"], 15000_00)
        self.assertEqual(balance_info["total_debits"], 3000_00)

    def test_amounts_stored_as_integers(self):
        """All amounts must be integers (paise), never floats."""
        entry = LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type="credit",
            amount_paise=999_99,  # ₹999.99
            reference_type="customer_payment",
        )
        entry.refresh_from_db()
        self.assertIsInstance(entry.amount_paise, int)


class ConcurrencyTest(TransactionTestCase):
    """
    Test that concurrent payout requests cannot overdraw a merchant's balance.

    Uses TransactionTestCase because we need real database transactions
    (not the wrapped-in-transaction behavior of TestCase) for SELECT FOR UPDATE
    to actually work.
    """

    def setUp(self):
        self.merchant = Merchant.objects.create(name="Concurrency Test", email="concurrent@test.com")
        self.bank_account = BankAccount.objects.create(
            merchant=self.merchant,
            account_number="1234567890",
            ifsc_code="TEST0001234",
            account_holder_name="Test",
        )
        # Seed with ₹100 balance (10000 paise)
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type="credit",
            amount_paise=10000,
            reference_type="customer_payment",
            description="Seed balance",
        )

    def test_concurrent_payouts_no_overdraw(self):
        """
        Merchant has ₹100 (10000 paise).
        Two simultaneous ₹60 (6000 paise) payout requests.
        Exactly one should succeed. The other must be rejected.
        Final balance must be ₹40 (4000 paise), not negative.
        """
        results = {"success": 0, "failed": 0, "errors": []}

        def make_payout(key_suffix):
            """Each thread gets its own DB connection in TransactionTestCase."""
            try:
                create_payout(
                    merchant_id=self.merchant.id,
                    amount_paise=6000,
                    bank_account_id=self.bank_account.id,
                    idempotency_key=f"concurrent-test-{key_suffix}",
                )
                return "success"
            except InsufficientBalance:
                return "insufficient"
            except Exception as e:
                return f"error: {e}"

        # Submit two concurrent payout requests
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(make_payout, "a"),
                executor.submit(make_payout, "b"),
            ]
            for future in as_completed(futures):
                result = future.result()
                if result == "success":
                    results["success"] += 1
                elif result == "insufficient":
                    results["failed"] += 1
                else:
                    results["errors"].append(result)

        # Assertions
        self.assertEqual(results["success"], 1, f"Expected exactly 1 success, got {results}")
        self.assertEqual(results["failed"], 1, f"Expected exactly 1 failure, got {results}")
        self.assertEqual(results["errors"], [], f"Unexpected errors: {results['errors']}")

        # Verify balance integrity
        balance_info = get_merchant_balance(self.merchant.id)
        self.assertEqual(
            balance_info["available_balance"],
            4000,  # ₹100 - ₹60 = ₹40
            f"Balance should be 4000 paise, got {balance_info['available_balance']}"
        )

        # Verify only one payout was created
        payout_count = Payout.objects.filter(merchant=self.merchant).count()
        self.assertEqual(payout_count, 1, f"Expected 1 payout, got {payout_count}")


class IdempotencyTest(TransactionTestCase):
    """Test that duplicate idempotency keys return the same response."""

    def setUp(self):
        self.merchant = Merchant.objects.create(name="Idempotency Test", email="idempotent@test.com")
        self.bank_account = BankAccount.objects.create(
            merchant=self.merchant,
            account_number="1234567890",
            ifsc_code="TEST0001234",
            account_holder_name="Test",
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type="credit",
            amount_paise=50000_00,
            reference_type="customer_payment",
            description="Seed balance",
        )

    def test_same_key_returns_same_response(self):
        """Second call with the same idempotency key returns cached response."""
        idem_key = str(uuid.uuid4())

        # First call — should create the payout
        response1 = create_payout(
            merchant_id=self.merchant.id,
            amount_paise=5000_00,
            bank_account_id=self.bank_account.id,
            idempotency_key=idem_key,
        )

        # Second call — should return cached response
        try:
            create_payout(
                merchant_id=self.merchant.id,
                amount_paise=5000_00,
                bank_account_id=self.bank_account.id,
                idempotency_key=idem_key,
            )
            self.fail("Expected DuplicateIdempotencyKey exception")
        except DuplicateIdempotencyKey as e:
            response2 = e.cached_response

        # Same payout ID returned
        self.assertEqual(response1["id"], response2["id"])
        self.assertEqual(response1["amount_paise"], response2["amount_paise"])
        self.assertEqual(response1["status"], response2["status"])

        # Only ONE payout created in DB
        payout_count = Payout.objects.filter(merchant=self.merchant).count()
        self.assertEqual(payout_count, 1)

        # Balance debited only ONCE
        balance = get_merchant_balance(self.merchant.id)
        self.assertEqual(balance["available_balance"], 45000_00)

    def test_different_keys_create_different_payouts(self):
        """Different idempotency keys should create separate payouts."""
        key1 = str(uuid.uuid4())
        key2 = str(uuid.uuid4())

        create_payout(
            merchant_id=self.merchant.id,
            amount_paise=5000_00,
            bank_account_id=self.bank_account.id,
            idempotency_key=key1,
        )
        create_payout(
            merchant_id=self.merchant.id,
            amount_paise=5000_00,
            bank_account_id=self.bank_account.id,
            idempotency_key=key2,
        )

        payout_count = Payout.objects.filter(merchant=self.merchant).count()
        self.assertEqual(payout_count, 2)

    def test_idempotency_key_scoped_per_merchant(self):
        """Same key for different merchants should create separate payouts."""
        merchant2 = Merchant.objects.create(name="Other Merchant", email="other@test.com")
        ba2 = BankAccount.objects.create(
            merchant=merchant2,
            account_number="9999999999",
            ifsc_code="TEST0009999",
            account_holder_name="Other",
        )
        LedgerEntry.objects.create(
            merchant=merchant2,
            entry_type="credit",
            amount_paise=50000_00,
            reference_type="customer_payment",
        )

        shared_key = str(uuid.uuid4())

        create_payout(
            merchant_id=self.merchant.id,
            amount_paise=1000_00,
            bank_account_id=self.bank_account.id,
            idempotency_key=shared_key,
        )
        create_payout(
            merchant_id=merchant2.id,
            amount_paise=1000_00,
            bank_account_id=ba2.id,
            idempotency_key=shared_key,
        )

        # Each merchant should have 1 payout
        self.assertEqual(Payout.objects.filter(merchant=self.merchant).count(), 1)
        self.assertEqual(Payout.objects.filter(merchant=merchant2).count(), 1)


class IdempotencyAPITest(TransactionTestCase):
    """Test idempotency via the HTTP API layer."""

    def setUp(self):
        self.client = Client()
        self.merchant = Merchant.objects.create(name="API Test", email="api@test.com")
        self.bank_account = BankAccount.objects.create(
            merchant=self.merchant,
            account_number="1234567890",
            ifsc_code="TEST0001234",
            account_holder_name="Test",
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type="credit",
            amount_paise=100000_00,
            reference_type="customer_payment",
        )

    def test_post_payout_idempotent_via_api(self):
        """POST /api/v1/payouts/ with same Idempotency-Key returns same response."""
        idem_key = str(uuid.uuid4())
        payload = {
            "amount_paise": 10000_00,
            "bank_account_id": self.bank_account.id,
        }
        headers = {
            "HTTP_IDEMPOTENCY_KEY": idem_key,
            "HTTP_X_MERCHANT_ID": str(self.merchant.id),
        }

        resp1 = self.client.post(
            "/api/v1/payouts/",
            data=payload,
            content_type="application/json",
            **headers,
        )
        self.assertEqual(resp1.status_code, 201)

        resp2 = self.client.post(
            "/api/v1/payouts/",
            data=payload,
            content_type="application/json",
            **headers,
        )
        # Idempotent — returns cached 201
        self.assertEqual(resp2.status_code, 201)
        self.assertEqual(resp1.json()["id"], resp2.json()["id"])

        # Only one payout in DB
        self.assertEqual(Payout.objects.filter(merchant=self.merchant).count(), 1)


class StateMachineTest(TestCase):
    """Test that illegal state transitions are rejected."""

    def setUp(self):
        self.merchant = Merchant.objects.create(name="State Test", email="state@test.com")
        self.bank_account = BankAccount.objects.create(
            merchant=self.merchant,
            account_number="1234567890",
            ifsc_code="TEST0001234",
            account_holder_name="Test",
        )

    def _create_payout(self, status):
        return Payout.objects.create(
            merchant=self.merchant,
            amount_paise=1000_00,
            bank_account_id=self.bank_account.id,
            status=status,
            idempotency_key=str(uuid.uuid4()),
        )

    def test_pending_to_processing_allowed(self):
        payout = self._create_payout("pending")
        transition_payout_status(payout, "processing")
        payout.refresh_from_db()
        self.assertEqual(payout.status, "processing")

    def test_processing_to_completed_allowed(self):
        payout = self._create_payout("processing")
        transition_payout_status(payout, "completed")
        payout.refresh_from_db()
        self.assertEqual(payout.status, "completed")

    def test_processing_to_failed_allowed(self):
        payout = self._create_payout("processing")
        transition_payout_status(payout, "failed")
        payout.refresh_from_db()
        self.assertEqual(payout.status, "failed")

    def test_completed_to_pending_blocked(self):
        """Completed is a terminal state — no backward transitions."""
        payout = self._create_payout("completed")
        with self.assertRaises(InvalidStateTransition):
            transition_payout_status(payout, "pending")

    def test_completed_to_processing_blocked(self):
        payout = self._create_payout("completed")
        with self.assertRaises(InvalidStateTransition):
            transition_payout_status(payout, "processing")

    def test_failed_to_completed_blocked(self):
        """Failed is a terminal state — cannot magically complete."""
        payout = self._create_payout("failed")
        with self.assertRaises(InvalidStateTransition):
            transition_payout_status(payout, "completed")

    def test_failed_to_pending_blocked(self):
        payout = self._create_payout("failed")
        with self.assertRaises(InvalidStateTransition):
            transition_payout_status(payout, "pending")

    def test_pending_to_completed_blocked(self):
        """Cannot skip processing — must go through the full lifecycle."""
        payout = self._create_payout("pending")
        with self.assertRaises(InvalidStateTransition):
            transition_payout_status(payout, "completed")


class FundReturnTest(TransactionTestCase):
    """Test that failed payouts return funds atomically."""

    def setUp(self):
        self.merchant = Merchant.objects.create(name="Fund Test", email="fund@test.com")
        self.bank_account = BankAccount.objects.create(
            merchant=self.merchant,
            account_number="1234567890",
            ifsc_code="TEST0001234",
            account_holder_name="Test",
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type="credit",
            amount_paise=10000_00,
            reference_type="customer_payment",
        )

    def test_fund_return_on_failure(self):
        """When a payout fails, held funds are returned via a credit entry."""
        # Create and hold
        result = create_payout(
            merchant_id=self.merchant.id,
            amount_paise=5000_00,
            bank_account_id=self.bank_account.id,
            idempotency_key=str(uuid.uuid4()),
        )

        balance_after_hold = get_merchant_balance(self.merchant.id)
        self.assertEqual(balance_after_hold["available_balance"], 5000_00)

        # Simulate processing then failure
        payout = Payout.objects.get(id=result["id"])
        payout.status = "processing"
        payout.failure_reason = "Bank rejected"
        payout.save()

        return_funds(payout)

        # Balance should be fully restored
        balance_after_return = get_merchant_balance(self.merchant.id)
        self.assertEqual(balance_after_return["available_balance"], 10000_00)

        # Verify reversal ledger entry exists
        reversal = LedgerEntry.objects.filter(
            merchant=self.merchant,
            reference_type="payout_reversal",
            reference_id=payout.id,
        )
        self.assertEqual(reversal.count(), 1)
        self.assertEqual(reversal.first().amount_paise, 5000_00)
        self.assertEqual(reversal.first().entry_type, "credit")
