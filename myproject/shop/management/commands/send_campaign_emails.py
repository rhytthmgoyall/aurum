from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone

from shop.models import EmailSequenceState


CAMPAIGN_SUBJECTS = [
    "The Aurum Edit: Welcome to Your Private Preview",
    "The Aurum Edit: Curated Pieces Just for You",
    "The Aurum Edit: Your Next Favourite Piece Awaits",
    "The Aurum Edit: Last Chance to Discover These Picks",
]


class Command(BaseCommand):
    help = "Send the next email in a 4-step campaign to every eligible user."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show which emails would be sent without sending them.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        dry_run = options["dry_run"]
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
            next_send_at = now + timedelta(minutes=30)

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
                self.stdout.write(
                    f"[DRY RUN] Would send step {step}/4 to {user.email} with subject: {subject}"
                )
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
            self.stdout.write(
                f"Sent step {step}/4 to {user.email} with subject: {subject}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Sent or simulated {sent_count} email(s); skipped {skipped_count} user(s)."
            )
        )
