"""
Seed data management command.

Creates 3 merchants with bank accounts and credit history.
Run: python manage.py seed_data
"""

import uuid
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Merchant, BankAccount, LedgerEntry, Payout


class Command(BaseCommand):
    help = "Seed the database with test merchants, bank accounts, and credit history"

    def handle(self, *args, **options):
        self.stdout.write("🌱 Seeding database...")

        # Clear existing data
        LedgerEntry.objects.all().delete()
        Payout.objects.all().delete()
        BankAccount.objects.all().delete()
        Merchant.objects.all().delete()

        # ----- Merchant 1: Acme Design Studio -----
        m1 = Merchant.objects.create(
            name="Acme Design Studio",
            email="billing@acmedesign.in",
        )
        ba1 = BankAccount.objects.create(
            merchant=m1,
            account_number="1234567890123456",
            ifsc_code="HDFC0001234",
            account_holder_name="Acme Design Studio Pvt Ltd",
        )
        # Seed credits — simulating 6 customer payments over the past month
        credits_m1 = [
            (5000_00, "Invoice #INV-001 — Webflow redesign for ClientCo", 25),
            (12000_00, "Invoice #INV-002 — Brand identity for StartupX", 20),
            (3500_00, "Invoice #INV-003 — UI audit for FinTechY", 15),
            (8000_00, "Invoice #INV-004 — Landing page for SaaSZ", 10),
            (15000_00, "Invoice #INV-005 — Full website for AgencyABC", 5),
            (6000_00, "Invoice #INV-006 — Logo design for CryptoDAO", 2),
        ]
        for amount, desc, days_ago in credits_m1:
            LedgerEntry.objects.create(
                merchant=m1,
                entry_type="credit",
                amount_paise=amount,
                reference_type="customer_payment",
                reference_id=uuid.uuid4(),
                description=desc,
                created_at=timezone.now() - timedelta(days=days_ago),
            )

        # One completed payout to show history
        p1 = Payout.objects.create(
            merchant=m1,
            amount_paise=10000_00,
            bank_account_id=ba1.id,
            status="completed",
            idempotency_key=str(uuid.uuid4()),
            attempts=1,
            created_at=timezone.now() - timedelta(days=8),
        )
        LedgerEntry.objects.create(
            merchant=m1,
            entry_type="debit",
            amount_paise=10000_00,
            reference_type="payout_hold",
            reference_id=p1.id,
            description=f"Payout to HDFC ****3456",
            created_at=timezone.now() - timedelta(days=8),
        )

        self.stdout.write(
            f"  ✅ {m1.name} — Balance: ₹{(49500_00 - 10000_00) / 100:,.2f}"
        )

        # ----- Merchant 2: ByteForge Labs -----
        m2 = Merchant.objects.create(
            name="ByteForge Labs",
            email="finance@byteforge.dev",
        )
        ba2 = BankAccount.objects.create(
            merchant=m2,
            account_number="9876543210987654",
            ifsc_code="ICIC0005678",
            account_holder_name="ByteForge Labs LLP",
        )
        credits_m2 = [
            (25000_00, "Contract #BF-100 — API development for MegaCorp", 30),
            (18000_00, "Contract #BF-101 — Mobile app MVP for HealthStart", 22),
            (7500_00, "Contract #BF-102 — DevOps setup for EduTech", 14),
            (32000_00, "Contract #BF-103 — Full-stack project for RetailPro", 7),
            (4500_00, "Contract #BF-104 — Bug fixes for LogiTrack", 3),
        ]
        for amount, desc, days_ago in credits_m2:
            LedgerEntry.objects.create(
                merchant=m2,
                entry_type="credit",
                amount_paise=amount,
                reference_type="customer_payment",
                reference_id=uuid.uuid4(),
                description=desc,
                created_at=timezone.now() - timedelta(days=days_ago),
            )

        self.stdout.write(
            f"  ✅ {m2.name} — Balance: ₹{87000_00 / 100:,.2f}"
        )

        # ----- Merchant 3: Priya Sharma (Freelancer) -----
        m3 = Merchant.objects.create(
            name="Priya Sharma",
            email="priya@priyasharma.design",
        )
        ba3_a = BankAccount.objects.create(
            merchant=m3,
            account_number="5555666677778888",
            ifsc_code="SBIN0009012",
            account_holder_name="Priya Sharma",
        )
        ba3_b = BankAccount.objects.create(
            merchant=m3,
            account_number="1111222233334444",
            ifsc_code="UTIB0003456",
            account_holder_name="Priya Sharma",
        )
        credits_m3 = [
            (8000_00, "Freelance — Illustration pack for GameStudio", 18),
            (3000_00, "Freelance — Social media graphics for Influencer", 12),
            (12000_00, "Freelance — App icon set for ProductHunt launch", 6),
            (5000_00, "Freelance — Pitch deck design for VCFund", 1),
        ]
        for amount, desc, days_ago in credits_m3:
            LedgerEntry.objects.create(
                merchant=m3,
                entry_type="credit",
                amount_paise=amount,
                reference_type="customer_payment",
                reference_id=uuid.uuid4(),
                description=desc,
                created_at=timezone.now() - timedelta(days=days_ago),
            )

        # One failed payout to show reversal
        p3 = Payout.objects.create(
            merchant=m3,
            amount_paise=5000_00,
            bank_account_id=ba3_a.id,
            status="failed",
            idempotency_key=str(uuid.uuid4()),
            attempts=3,
            failure_reason="Bank rejected: invalid account details",
            created_at=timezone.now() - timedelta(days=4),
        )
        LedgerEntry.objects.create(
            merchant=m3,
            entry_type="debit",
            amount_paise=5000_00,
            reference_type="payout_hold",
            reference_id=p3.id,
            description=f"Payout hold to SBI ****8888",
            created_at=timezone.now() - timedelta(days=4),
        )
        LedgerEntry.objects.create(
            merchant=m3,
            entry_type="credit",
            amount_paise=5000_00,
            reference_type="payout_reversal",
            reference_id=p3.id,
            description=f"Funds returned: payout failed — invalid account details",
            created_at=timezone.now() - timedelta(days=4, hours=-1),
        )

        self.stdout.write(
            f"  ✅ {m3.name} — Balance: ₹{28000_00 / 100:,.2f}"
        )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("✨ Seed data created successfully!"))
        self.stdout.write(f"   Merchants: {Merchant.objects.count()}")
        self.stdout.write(f"   Bank accounts: {BankAccount.objects.count()}")
        self.stdout.write(f"   Ledger entries: {LedgerEntry.objects.count()}")
        self.stdout.write(f"   Payouts: {Payout.objects.count()}")
