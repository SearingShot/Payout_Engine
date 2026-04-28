from rest_framework import serializers
from core.models import Merchant, BankAccount, LedgerEntry, Payout


class MerchantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Merchant
        fields = ["id", "name", "email", "created_at"]


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = ["id", "account_number", "ifsc_code", "account_holder_name", "created_at"]


class LedgerEntrySerializer(serializers.ModelSerializer):
    amount_display = serializers.SerializerMethodField()

    class Meta:
        model = LedgerEntry
        fields = [
            "id",
            "entry_type",
            "amount_paise",
            "amount_display",
            "reference_type",
            "reference_id",
            "description",
            "created_at",
        ]

    def get_amount_display(self, obj):
        """Human-readable amount in INR."""
        sign = "+" if obj.entry_type == "credit" else "-"
        return f"{sign}₹{obj.amount_paise / 100:,.2f}"


class PayoutSerializer(serializers.ModelSerializer):
    amount_display = serializers.SerializerMethodField()

    class Meta:
        model = Payout
        fields = [
            "id",
            "merchant_id",
            "amount_paise",
            "amount_display",
            "bank_account_id",
            "status",
            "idempotency_key",
            "attempts",
            "failure_reason",
            "created_at",
            "updated_at",
        ]

    def get_amount_display(self, obj):
        return f"₹{obj.amount_paise / 100:,.2f}"


class PayoutRequestSerializer(serializers.Serializer):
    """Validates the payout request body."""

    amount_paise = serializers.IntegerField(min_value=100)  # min ₹1
    bank_account_id = serializers.IntegerField()

    def validate_amount_paise(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive")
        return value


class MerchantDashboardSerializer(serializers.Serializer):
    """Aggregated dashboard data for a merchant."""

    merchant = MerchantSerializer()
    available_balance = serializers.IntegerField()
    held_balance = serializers.IntegerField()
    total_credits = serializers.IntegerField()
    total_debits = serializers.IntegerField()
    recent_entries = LedgerEntrySerializer(many=True)
    recent_payouts = PayoutSerializer(many=True)
    bank_accounts = BankAccountSerializer(many=True)
