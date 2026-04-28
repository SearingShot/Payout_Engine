from django.core.management import call_command
from django.core.management.base import BaseCommand

from core.models import Merchant


class Command(BaseCommand):
    help = "Seed demo data only when the database is empty."

    def handle(self, *args, **options):
        if Merchant.objects.exists():
            self.stdout.write("Demo data already exists; skipping seed.")
            return

        call_command("seed_data")
