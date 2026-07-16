from decimal import Decimal

from django.db import migrations


def create_aurum_select_plans(apps, schema_editor):
    MembershipPlan = apps.get_model("shop", "MembershipPlan")
    plans = (
        {
            "name": "Select Monthly",
            "billing_cycle": "monthly",
            "price": Decimal("499.00"),
            "discount_percent": Decimal("5.00"),
            "free_shipping": True,
            "wallet_bonus_percent": Decimal("2.00"),
        },
        {
            "name": "Select Signature",
            "billing_cycle": "yearly",
            "price": Decimal("4999.00"),
            "discount_percent": Decimal("10.00"),
            "free_shipping": True,
            "wallet_bonus_percent": Decimal("5.00"),
        },
    )
    for values in plans:
        MembershipPlan.objects.get_or_create(
            name=values["name"],
            billing_cycle=values["billing_cycle"],
            defaults=values,
        )


def remove_aurum_select_plans(apps, schema_editor):
    MembershipPlan = apps.get_model("shop", "MembershipPlan")
    MembershipPlan.objects.filter(
        name__in=("Select Monthly", "Select Signature"),
        razorpay_plan_id="",
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("shop", "0041_membershipplan_order_membership_discount_and_more")]
    operations = [
        migrations.RunPython(create_aurum_select_plans, remove_aurum_select_plans),
    ]
