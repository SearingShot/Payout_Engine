"""
API views for the payout engine.

All endpoints are unauthenticated for simplicity — merchants are identified by ID.
"""

import logging
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Merchant, LedgerEntry, Payout, BankAccount
from core.serializers import (
    MerchantSerializer,
    BankAccountSerializer,
    LedgerEntrySerializer,
    PayoutSerializer,
    PayoutRequestSerializer,
    MerchantDashboardSerializer,
)
from core.services.payout_service import (
    create_payout,
    get_merchant_balance,
    get_held_balance,
    InsufficientBalance,
    DuplicateIdempotencyKey,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Merchant endpoints
# ---------------------------------------------------------------------------


class MerchantListView(APIView):
    """GET /api/v1/merchants/ — List all merchants."""

    def get(self, request):
        merchants = Merchant.objects.all()
        serializer = MerchantSerializer(merchants, many=True)
        return Response(serializer.data)


class MerchantDetailView(APIView):
    """GET /api/v1/merchants/{id}/ — Single merchant detail."""

    def get(self, request, merchant_id):
        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response(
                {"error": "Merchant not found"}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = MerchantSerializer(merchant)
        return Response(serializer.data)


class MerchantDashboardView(APIView):
    """
    GET /api/v1/merchants/{id}/dashboard/

    Returns aggregated dashboard data:
    - Available balance (credits - debits, computed at DB level)
    - Held balance (pending + processing payouts)
    - Recent ledger entries
    - Recent payouts
    - Bank accounts
    """

    def get(self, request, merchant_id):
        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response(
                {"error": "Merchant not found"}, status=status.HTTP_404_NOT_FOUND
            )

        balance_info = get_merchant_balance(merchant_id)
        held = get_held_balance(merchant_id)

        recent_entries = LedgerEntry.objects.filter(merchant=merchant).order_by(
            "-created_at"
        )[:20]
        recent_payouts = Payout.objects.filter(merchant=merchant).order_by(
            "-created_at"
        )[:20]
        bank_accounts = BankAccount.objects.filter(merchant=merchant)

        data = {
            "merchant": MerchantSerializer(merchant).data,
            "available_balance": balance_info["available_balance"],
            "held_balance": held,
            "total_credits": balance_info["total_credits"],
            "total_debits": balance_info["total_debits"],
            "recent_entries": LedgerEntrySerializer(recent_entries, many=True).data,
            "recent_payouts": PayoutSerializer(recent_payouts, many=True).data,
            "bank_accounts": BankAccountSerializer(bank_accounts, many=True).data,
        }

        return Response(data)


class MerchantLedgerView(APIView):
    """GET /api/v1/merchants/{id}/ledger/ — Full ledger for a merchant."""

    def get(self, request, merchant_id):
        try:
            Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response(
                {"error": "Merchant not found"}, status=status.HTTP_404_NOT_FOUND
            )

        entries = LedgerEntry.objects.filter(merchant_id=merchant_id).order_by(
            "-created_at"
        )
        serializer = LedgerEntrySerializer(entries, many=True)
        return Response(serializer.data)


class MerchantPayoutsView(APIView):
    """GET /api/v1/merchants/{id}/payouts/ — Payout history for a merchant."""

    def get(self, request, merchant_id):
        try:
            Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response(
                {"error": "Merchant not found"}, status=status.HTTP_404_NOT_FOUND
            )

        payouts = Payout.objects.filter(merchant_id=merchant_id).order_by("-created_at")
        serializer = PayoutSerializer(payouts, many=True)
        return Response(serializer.data)


class MerchantBankAccountsView(APIView):
    """GET /api/v1/merchants/{id}/bank-accounts/ — Bank accounts for a merchant."""

    def get(self, request, merchant_id):
        try:
            Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response(
                {"error": "Merchant not found"}, status=status.HTTP_404_NOT_FOUND
            )

        accounts = BankAccount.objects.filter(merchant_id=merchant_id)
        serializer = BankAccountSerializer(accounts, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Payout endpoints
# ---------------------------------------------------------------------------


class PayoutCreateView(APIView):
    """
    POST /api/v1/payouts/

    Headers:
        Idempotency-Key: <merchant-supplied UUID>
        X-Merchant-Id: <merchant ID>  (simulates auth — in production this comes from JWT)

    Body:
        {
            "amount_paise": 500000,
            "bank_account_id": 1
        }

    Creates a payout in 'pending' state and holds the funds.
    Returns the same response if called twice with the same idempotency key.
    """

    def post(self, request):
        # Extract idempotency key from header
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return Response(
                {"error": "Idempotency-Key header is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Extract merchant ID from header (simulates authentication)
        merchant_id = request.headers.get("X-Merchant-Id")
        if not merchant_id:
            return Response(
                {"error": "X-Merchant-Id header is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            merchant_id = int(merchant_id)
        except (ValueError, TypeError):
            return Response(
                {"error": "X-Merchant-Id must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate request body
        serializer = PayoutRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = create_payout(
                merchant_id=merchant_id,
                amount_paise=serializer.validated_data["amount_paise"],
                bank_account_id=serializer.validated_data["bank_account_id"],
                idempotency_key=idempotency_key,
            )
            return Response(result, status=status.HTTP_201_CREATED)

        except DuplicateIdempotencyKey as e:
            # Return the cached response with the original status code
            return Response(e.cached_response, status=e.cached_status)

        except InsufficientBalance as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )

        except ValueError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            logger.error(f"Unexpected error creating payout: {e}", exc_info=True)
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PayoutDetailView(APIView):
    """GET /api/v1/payouts/{id}/ — Single payout detail."""

    def get(self, request, payout_id):
        try:
            payout = Payout.objects.get(id=payout_id)
        except Payout.DoesNotExist:
            return Response(
                {"error": "Payout not found"}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = PayoutSerializer(payout)
        return Response(serializer.data)
