from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from shop.metal_rate_services import (
    MetalRateAPIError,
    PURITY_FACTORS,
    fetch_pure_metal_rates,
)
from shop.models import MetalRate


class Command(BaseCommand):
    help = "Fetch current Gold, Silver, and Platinum rates."

    def handle(self, *args, **options):
        try:
            pure_rates = fetch_pure_metal_rates()
        except MetalRateAPIError as exc:
            raise CommandError(str(exc)) from exc

        rows = []
        for (metal, purity), fineness in PURITY_FACTORS.items():
            rate = (pure_rates[metal] * fineness).quantize(Decimal("0.01"))
            rows.append(
                MetalRate(
                    metal=metal,
                    purity=purity,
                    rate_per_gram=rate,
                    source="metalpriceapi",
                )
            )

        with transaction.atomic():
            MetalRate.objects.bulk_create(rows)

        for row in rows:
            self.stdout.write(
                f"{row.metal} {row.purity}: INR {row.rate_per_gram}/g"
            )
        self.stdout.write(
            self.style.SUCCESS(f"Created {len(rows)} metal-rate rows.")
        )
