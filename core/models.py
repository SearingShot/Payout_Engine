import uuid
from django.db import models
from django.utils import timezone
from datetime import timedelta


class Merchant(models.Model):
    """A merchant who collects payments and requests payouts."""

    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class BankAccount(models.Model):
    """Bank account details for payout settlement."""

    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="bank_accounts"
    )
    account_number = models.CharField(max_length=20)
    ifsc_code = models.CharField(max_length=11)
    account_holder_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.account_holder_name} - {self.account_number[-4:]}"


class LedgerEntry(models.Model):
    """
    Immutable record of every money movement.

    Credits are positive (customer payments received).
    Debits are negative (payout holds, completed payouts).

    The merchant's balance is ALWAYS derived from:
        SUM(CASE WHEN entry_type='credit' THEN amount_paise ELSE -amount_paise END)

    amount_paise is stored as a positive BigInteger.
    The sign is determined by entry_type.
    """

    ENTRY_TYPE_CHOICES = [
        ("credit", "Credit"),
        ("debit", "Debit"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="ledger_entries"
    )
    entry_type = models.CharField(max_length=6, choices=ENTRY_TYPE_CHOICES)
    amount_paise = models.BigIntegerField(
        help_text="Amount in paise. Always positive. Sign determined by entry_type."
    )
    reference_type = models.CharField(
        max_length=50,
        help_text="What caused this entry: customer_payment, payout_hold, payout_reversal, payout_completed",
    )
    reference_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of the related object (e.g., Payout ID)",
    )
    description = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["merchant", "-created_at"]),
            models.Index(fields=["merchant", "entry_type"]),
        ]

    def __str__(self):
        sign = "+" if self.entry_type == "credit" else "-"
        return f"{sign}₹{self.amount_paise / 100:.2f} [{self.reference_type}]"


class Payout(models.Model):
    """
    A payout request from a merchant to their bank account.

    Lifecycle: pending → processing → completed
                                    → failed (funds returned)

    No backward transitions allowed.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="payouts"
    )
    amount_paise = models.BigIntegerField()
    bank_account_id = models.IntegerField(
        help_text="FK to BankAccount, stored as int for simplicity"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    idempotency_key = models.CharField(max_length=255)
    attempts = models.IntegerField(default=0)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["merchant", "status"]),
            models.Index(fields=["status", "processing_started_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["idempotency_key", "merchant"],
                name="unique_idempotency_per_merchant",
            )
        ]

    def __str__(self):
        return f"Payout {self.id} - ₹{self.amount_paise / 100:.2f} [{self.status}]"


class IdempotencyKey(models.Model):
    """
    Stores idempotency keys scoped per merchant with 24-hour expiry.

    If a duplicate request arrives with the same key, we return the
    cached response without creating a new payout.
    """

    key = models.CharField(max_length=255)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="idempotency_keys"
    )
    response_data = models.JSONField(
        help_text="Cached JSON response from the original request"
    )
    response_status = models.IntegerField(
        default=201, help_text="HTTP status code of the original response"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        unique_together = ("key", "merchant")
        indexes = [
            models.Index(fields=["key", "merchant"]),
        ]

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Key {self.key[:8]}... for merchant {self.merchant_id}"