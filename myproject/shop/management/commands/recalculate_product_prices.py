from decimal import Decimal, ROUND_HALF_UP

from django.core.management.base import BaseCommand

from shop.models import Product


class Command(BaseCommand):
    help = "Recalculate precious-metal product prices."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print changes without updating products.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        updated = 0
        unchanged = 0
        skipped = 0

        for product in Product.objects.all().iterator():
            if product.weight_grams is None:
                skipped += 1
                self.stdout.write(f"Skipped {product.pk}: missing weight.")
                continue

            metal, purity = product.get_pricing_attributes()
            if not metal:
                skipped += 1
                self.stdout.write(
                    f"Skipped {product.pk}: static-price material "
                    f"'{product.material}'."
                )
                continue

            rate = product.get_applicable_metal_rate()
            if rate is None:
                skipped += 1
                self.stdout.write(
                    f"Skipped {product.pk}: missing rate for "
                    f"{metal} {purity or ''}."
                )
                continue

            computed_price = product.get_computed_price()
            new_price = int(
                computed_price.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )

            if product.price == new_price:
                unchanged += 1
                continue

            old_price = product.price
            if not dry_run:
                product.price = new_price
                product.save(update_fields=("price",))

            updated += 1
            prefix = "[DRY RUN] " if dry_run else ""
            self.stdout.write(
                f"{prefix}Product {product.pk}: INR {old_price} -> INR {new_price}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated: {updated}; unchanged: {unchanged}; skipped: {skipped}."
            )
        )
