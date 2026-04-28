from django.urls import path
from core.views import (
    MerchantListView,
    MerchantDetailView,
    MerchantDashboardView,
    MerchantLedgerView,
    MerchantPayoutsView,
    MerchantBankAccountsView,
    PayoutCreateView,
    PayoutDetailView,
)

urlpatterns = [
    # Merchant endpoints
    path("merchants/", MerchantListView.as_view(), name="merchant-list"),
    path("merchants/<int:merchant_id>/", MerchantDetailView.as_view(), name="merchant-detail"),
    path("merchants/<int:merchant_id>/dashboard/", MerchantDashboardView.as_view(), name="merchant-dashboard"),
    path("merchants/<int:merchant_id>/ledger/", MerchantLedgerView.as_view(), name="merchant-ledger"),
    path("merchants/<int:merchant_id>/payouts/", MerchantPayoutsView.as_view(), name="merchant-payouts"),
    path("merchants/<int:merchant_id>/bank-accounts/", MerchantBankAccountsView.as_view(), name="merchant-bank-accounts"),

    # Payout endpoints
    path("payouts/", PayoutCreateView.as_view(), name="payout-create"),
    path("payouts/<uuid:payout_id>/", PayoutDetailView.as_view(), name="payout-detail"),
]
