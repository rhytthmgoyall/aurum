from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

from .models import EmailSequenceState, Order
from .models import Product, Payment


CAMPAIGN_SUBJECTS = [
    "The Aurum Edit: Welcome to Your Private Preview",
    "The Aurum Edit: Curated Pieces Just for You",
    "The Aurum Edit: Your Next Favourite Piece Awaits",
    "The Aurum Edit: Last Chance to Discover These Picks",
]


@shared_task
def check_low_stock_products():
    low_stock_count = Product.objects.filter(stock__lte=5).count()
    print(f"[{timezone.now()}] Low stock products: {low_stock_count}")
    return low_stock_count


@shared_task
def cleanup_old_created_payments():
    old_payments = Payment.objects.filter(
        status="created",
        order__isnull=True,
    )
    count = old_payments.count()
    old_payments.delete()
    return count


def _send_campaign_emails(now=None, dry_run=False):
    now = now or timezone.now()
    sent_count = 0
    skipped_count = 0

    users = (
        User.objects.filter(is_active=True)
        .exclude(email__isnull=True)
        .exclude(email__exact="")
    )

    for user in users:
        state, _ = EmailSequenceState.objects.get_or_create(
            user=user,
            defaults={"next_send_at": now},
        )

        if not state.is_active or state.emails_sent >= 4 or state.next_send_at > now:
            skipped_count += 1
            continue

        step = state.emails_sent + 1
        subject = CAMPAIGN_SUBJECTS[step - 1]
        next_send_at = now + timezone.timedelta(minutes=30)

        context = {
            "user": user,
            "step": step,
            "total_steps": 4,
            "next_send_at": next_send_at,
            "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
        }

        text_body = render_to_string("shop/emails/campaign_email.txt", context)
        html_body = render_to_string("shop/emails/campaign_email.html", context)

        if dry_run:
            sent_count += 1
            continue

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=False)

        state.emails_sent = step
        state.last_sent_at = now
        state.is_active = state.emails_sent < 4
        state.next_send_at = next_send_at if state.is_active else now
        state.save(update_fields=["emails_sent", "last_sent_at", "is_active", "next_send_at", "updated_at"])

        sent_count += 1

    return sent_count, skipped_count


@shared_task
def send_campaign_emails():
    sent_count, skipped_count = _send_campaign_emails()
    return {
        "sent": sent_count,
        "skipped": skipped_count,
    }


@shared_task
def refresh_metal_rates_and_product_prices():
    call_command("fetch_metal_rates")
    call_command("recalculate_product_prices")
    return {
        "status": "completed",
        "message": "Metal rates fetched and product prices recalculated.",
    }

@shared_task
def send_order_confirmation_email(order_id):
    order = (
        Order.objects
        .select_related("user")
        .prefetch_related("items")
        .get(id=order_id)
    )

    if not order.user.email:
        return "User has no email"

    order_path = reverse("order_confirmation", args=[order.id])
    site_url = getattr(settings, "SITE_URL", "http://localhost:8000")
    order_url = f"{site_url}{order_path}"

    subject = f"AURUM Order Confirmation #{order.id}"

    html_body = render_to_string(
        "shop/emails/order_confirmation_email.html",
        {
            "order": order,
            "order_url": order_url,
        }
    )

    text_body = (
        f"Thank you for your order #{order.id}.\n"
        f"Status: {order.status}\n"
        f"Total: ₹{order.total}\n"
        f"View order: {order_url}"
    )

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.user.email],
    )
    email.attach_alternative(html_body, "text/html")
    email.send()

    return f"Order confirmation email sent for order {order.id}"
