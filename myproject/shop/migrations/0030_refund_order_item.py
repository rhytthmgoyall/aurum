from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0029_chatmessage_is_ai_message"),
    ]

    operations = [
        migrations.AddField(
            model_name="refund",
            name="order_item",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="refunds",
                to="shop.orderitem",
            ),
        ),
    ]
