from django.contrib import admin
from core.models import Merchant, BankAccount, LedgerEntry, Payout, IdempotencyKey


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "email", "created_at")
    search_fields = ("name", "email")


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ("id", "merchant", "account_holder_name", "account_number", "ifsc_code")
    list_filter = ("merchant",)


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "merchant", "entry_type", "amount_paise", "reference_type", "created_at")
    list_filter = ("entry_type", "reference_type", "merchant")
    ordering = ("-created_at",)


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ("id", "merchant", "amount_paise", "status", "attempts", "created_at")
    list_filter = ("status", "merchant")
    ordering = ("-created_at",)


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ("key", "merchant", "response_status", "created_at", "expires_at")
    list_filter = ("merchant",)
