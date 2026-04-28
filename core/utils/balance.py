from django.db.models import Sum
from core.models import LedgerEntry

def get_balance(merchant_id):
    return (
        LedgerEntry.objects
        .filter(merchant_id=merchant_id)
        .aggregate(total=Sum("amount_paise"))["total"] or 0
    )