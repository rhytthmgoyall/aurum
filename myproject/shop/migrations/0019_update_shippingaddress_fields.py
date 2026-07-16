from django.db import migrations, models


def copy_old_address_fields(apps, schema_editor):
    ShippingAddress = apps.get_model("shop", "ShippingAddress")

    for address in ShippingAddress.objects.all():
        full_name = f"{address.first_name} {address.last_name}".strip()
        address.full_name = full_name or address.email
        address.phone = ""
        address.address_line = address.address
        address.state = ""
        address.country = "India"
        address.save(update_fields=[
            "full_name",
            "phone",
            "address_line",
            "state",
            "country",
        ])


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0018_product_is_new"),
    ]

    operations = [
        migrations.AddField(
            model_name="shippingaddress",
            name="full_name",
            field=models.CharField(default="", max_length=120),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="shippingaddress",
            name="phone",
            field=models.CharField(default="", max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="shippingaddress",
            name="address_line",
            field=models.CharField(default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="shippingaddress",
            name="state",
            field=models.CharField(default="", max_length=80),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="shippingaddress",
            name="country",
            field=models.CharField(default="India", max_length=80),
            preserve_default=False,
        ),
        migrations.RunPython(copy_old_address_fields, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="shippingaddress",
            name="first_name",
        ),
        migrations.RemoveField(
            model_name="shippingaddress",
            name="last_name",
        ),
        migrations.RemoveField(
            model_name="shippingaddress",
            name="email",
        ),
        migrations.RemoveField(
            model_name="shippingaddress",
            name="address",
        ),
        migrations.RemoveField(
            model_name="shippingaddress",
            name="is_default",
        ),
    ]
