from django.db import migrations, models
from django.db.models import Sum


def merge_duplicate_cart_items(apps, schema_editor):
    CartItem = apps.get_model("shop", "CartItem")
    duplicates = (
        CartItem.objects.values("cart_id", "product_id")
        .annotate(total_quantity=Sum("quantity"), row_count=models.Count("id"))
        .filter(row_count__gt=1)
    )

    for duplicate in duplicates:
        items = CartItem.objects.filter(
            cart_id=duplicate["cart_id"],
            product_id=duplicate["product_id"],
        ).order_by("id")
        keeper = items.first()
        keeper.quantity = duplicate["total_quantity"]
        keeper.save(update_fields=("quantity",))
        items.exclude(id=keeper.id).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0009_cart_cartitem"),
    ]

    operations = [
        migrations.RunPython(
            merge_duplicate_cart_items,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="cartitem",
            constraint=models.UniqueConstraint(
                fields=("cart", "product"),
                name="unique_cart_product",
            ),
        ),
    ]
