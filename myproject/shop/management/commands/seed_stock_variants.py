from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from shop.models import Product, ProductStockVariant


SIZE_OPTIONS = {
    "ring": [("7", 0), ("8", 0), ("9", 0), ("10", 0), ("11", 0)],
    "bracelet": [("6.5 inch", -3), ("7 inch", 0), ("7.5 inch", 5), ("8 inch", 10)],
    "chain": [("16 inch", -5), ("18 inch", 0), ("20 inch", 8), ("24 inch", 18)],
    "necklace": [("14 inch", -5), ("16 inch", 0), ("18 inch", 7), ("20 inch", 13)],
}


def product_size_type(product):
    name = product.primary_subcategory.name.lower()
    if name in {"rings", "signet rings"}:
        return "ring"
    if "bracelet" in name:
        return "bracelet"
    if "chain" in name:
        return "chain"
    if "necklace" in name:
        return "necklace"
    return None


def purity_options(product):
    if product.purity not in {"18K", "22K"}:
        return []
    if "silver" in product.material.lower() or "oxid" in product.finish.lower():
        return []

    values = ["18K", "22K"]
    size_type = product_size_type(product)
    if size_type == "chain" and not product.stone_type:
        values.append("24K")
    return values


def price_delta(product, percentage):
    return (Decimal(product.price) * Decimal(percentage) / Decimal("100")).quantize(
        Decimal("0.01")
    )


class Command(BaseCommand):
    help = "Populate size/purity stock combinations for a realistic product subset."

    def add_arguments(self, parser):
        parser.add_argument("--both", type=int, default=6)
        parser.add_argument("--size-only", type=int, default=6)
        parser.add_argument("--purity-only", type=int, default=6)
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        already_configured_count = Product.objects.filter(
            stock_variants__isnull=False
        ).distinct().count()

        gold_sized = list(
            Product.objects.select_related("primary_subcategory")
            .filter(purity__in=["18K", "22K"], stock_variants__isnull=True)
            .exclude(material__icontains="silver")
            .exclude(finish__icontains="oxid")
            .order_by("id")
        )
        gold_sized = [p for p in gold_sized if product_size_type(p)][:options["both"]]

        used_ids = {product.id for product in gold_sized}
        silver_sized = list(
            Product.objects.select_related("primary_subcategory")
            .filter(material__icontains="silver", stock_variants__isnull=True)
            .exclude(id__in=used_ids)
            .order_by("id")
        )
        silver_sized = [p for p in silver_sized if product_size_type(p)][:options["size_only"]]
        used_ids.update(product.id for product in silver_sized)

        gold_purity_only = list(
            Product.objects.select_related("primary_subcategory")
            .filter(purity__in=["18K", "22K"], stock_variants__isnull=True)
            .exclude(id__in=used_ids)
            .exclude(material__icontains="silver")
            .exclude(finish__icontains="oxid")
            .order_by("id")
        )
        gold_purity_only = [
            product for product in gold_purity_only if not product_size_type(product)
        ][:options["purity_only"]]

        created_rows = 0
        products_with_size = set()
        products_with_purity = set()

        def create_rows(product, sizes, purities):
            nonlocal created_rows
            size_values = sizes or [(None, 0)]
            purity_values = purities or [None]

            for size, delta_percentage in size_values:
                for purity in purity_values:
                    sku_parts = ["PSV", str(product.id), slugify(size or "no-size"), purity or "no-purity"]
                    sku = "-".join(sku_parts).upper()
                    defaults = {
                        "stock_quantity": 4 + ((product.id + len(sku)) % 23),
                        "price_delta": price_delta(product, delta_percentage),
                    }
                    if options["dry_run"]:
                        self.stdout.write(
                            f"Would create {sku}: size={size}, purity={purity}, delta={defaults['price_delta']}"
                        )
                        created_rows += 1
                        continue

                    _, created = ProductStockVariant.objects.update_or_create(
                        product=product,
                        size=size,
                        purity=purity,
                        defaults={"sku": sku, **defaults},
                    )
                    created_rows += int(created)

            if sizes:
                products_with_size.add(product.id)
            if purities:
                products_with_purity.add(product.id)

        for product in gold_sized:
            create_rows(product, SIZE_OPTIONS[product_size_type(product)], purity_options(product))
        for product in silver_sized:
            create_rows(product, SIZE_OPTIONS[product_size_type(product)], [])
        for product in gold_purity_only:
            create_rows(product, [], purity_options(product))

        if options["dry_run"]:
            transaction.set_rollback(True)

        both_count = len(products_with_size & products_with_purity)
        self.stdout.write(self.style.SUCCESS("\nStock-variant population summary"))
        self.stdout.write(f"Rows created: {created_rows}")
        self.stdout.write(f"Products with size options: {len(products_with_size)}")
        self.stdout.write(f"Products with purity options: {len(products_with_purity)}")
        self.stdout.write(f"Products with both: {both_count}")
        self.stdout.write(f"Previously configured products skipped: {already_configured_count}")
