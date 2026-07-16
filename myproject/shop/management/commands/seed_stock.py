import random

from django.core.management.base import BaseCommand

from shop.models import Product


class Command(BaseCommand):
    help = "Assign random stock values to existing products."

    def add_arguments(self, parser):
        parser.add_argument(
            "--min",
            type=int,
            default=3,
            help="Minimum stock value to assign.",
        )
        parser.add_argument(
            "--max",
            type=int,
            default=25,
            help="Maximum stock value to assign.",
        )
        parser.add_argument(
            "--only-empty",
            action="store_true",
            help="Only update products with stock set to 0.",
        )

    def handle(self, *args, **options):
        min_stock = options["min"]
        max_stock = options["max"]

        if min_stock < 0:
            self.stderr.write(self.style.ERROR("Minimum stock cannot be negative."))
            return

        if max_stock < min_stock:
            self.stderr.write(self.style.ERROR("Maximum stock must be greater than or equal to minimum stock."))
            return

        products = Product.objects.all()

        if options["only_empty"]:
            products = products.filter(stock=0)

        updated_count = 0

        for product in products:
            product.stock = random.randint(min_stock, max_stock)
            product.save(update_fields=["stock"])
            updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Updated stock for {updated_count} products.")
        )
