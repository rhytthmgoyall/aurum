from decimal import Decimal, ROUND_HALF_UP

from .models import UserMembership


MONEY = Decimal("0.01")
FREE_SHIPPING_THRESHOLD = Decimal("250.00")
STANDARD_SHIPPING = Decimal("8.00")
TAX_RATE = Decimal("0.08")


def money(value):
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def get_active_membership(user):
    if not user or not user.is_authenticated:
        return None

    try:
        membership = user.membership
    except (AttributeError, UserMembership.DoesNotExist):
        return None

    return membership if membership.is_active else None


def calculate_order_totals(subtotal, user=None):
    subtotal = money(subtotal)
    membership = get_active_membership(user)
    discount_percent = (
        membership.plan.discount_percent if membership else Decimal("0")
    )
    membership_discount = money(subtotal * discount_percent / Decimal("100"))
    discounted_subtotal = money(subtotal - membership_discount)

    if discounted_subtotal <= 0:
        shipping = Decimal("0.00")
        tax = Decimal("0.00")
    else:
        has_free_shipping = bool(membership and membership.plan.free_shipping)
        shipping = (
            Decimal("0.00")
            if has_free_shipping or discounted_subtotal >= FREE_SHIPPING_THRESHOLD
            else STANDARD_SHIPPING
        )
        tax = money(discounted_subtotal * TAX_RATE)

    total = money(discounted_subtotal + shipping + tax)
    return {
        "subtotal": subtotal,
        "membership": membership,
        "discount_percent": money(discount_percent),
        "membership_discount": membership_discount,
        "discounted_subtotal": discounted_subtotal,
        "shipping": money(shipping),
        "tax": money(tax),
        "total": total,
    }
