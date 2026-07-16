import logging
from decimal import Decimal
import razorpay
from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from .models import Payment, RefundRequest
from .wallet_services import credit_wallet

logger = logging.getLogger(__name__)


def process_refund(refund_request):
    if refund_request.status not in [RefundRequest.QC_PASSED, RefundRequest.REFUND_FAILED]:
        return refund_request

    if refund_request.razorpay_refund_id or refund_request.wallet_transaction_id:
        return refund_request

    if refund_request.refund_mode == RefundRequest.ORIGINAL_PAYMENT:
        return process_razorpay_refund(refund_request)

    tx = credit_wallet(
        refund_request.user,
        refund_request.refund_amount,
        refund_request=refund_request,
        transaction_type="refund_credit",
        notes=f"Refund request #{refund_request.id}",
    )

    refund_request.wallet_transaction = tx
    refund_request.status = RefundRequest.REFUNDED
    refund_request.refund_completed_at = timezone.now()
    refund_request.save(update_fields=["wallet_transaction", "status", "refund_completed_at", "updated_at"])
    return refund_request

def process_razorpay_refund(refund_request):
    payment = Payment.objects.filter(order=refund_request.order).first()

    if not payment or not payment.razorpay_payment_id:
        refund_request.status = RefundRequest.REFUND_FAILED
        refund_request.staff_notes = "Missing Razorpay payment id."
        refund_request.save(update_fields=["status", "staff_notes", "updated_at"])
        return refund_request

    amount_paise = int(Decimal(refund_request.refund_amount) * Decimal("100"))

    already_refunded = (
        RefundRequest.objects
        .filter(order=refund_request.order, razorpay_refund_id__isnull=False)
        .exclude(id=refund_request.id)
        .aggregate(total=Sum("refund_amount"))["total"]
        or Decimal("0")
    )

    if int((already_refunded + refund_request.refund_amount) * Decimal("100")) > payment.amount:
        refund_request.status = RefundRequest.REFUND_FAILED
        refund_request.staff_notes = "Refund would exceed captured payment amount."
        refund_request.save(update_fields=["status", "staff_notes", "updated_at"])
        return refund_request

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    try:
        response = client.payment.refund(payment.razorpay_payment_id, {
            "amount": amount_paise,
            "speed": "normal",
            "notes": {"refund_request_id": str(refund_request.id)},
        })
    except razorpay.errors.BadRequestError as exc:
        logger.exception("Razorpay refund failed")
        refund_request.status = RefundRequest.REFUND_FAILED
        refund_request.staff_notes = str(exc)
        refund_request.save(update_fields=["status", "staff_notes", "updated_at"])
        return refund_request
    except Exception as exc:
        logger.exception("Unexpected Razorpay refund error")
        refund_request.status = RefundRequest.REFUND_FAILED
        refund_request.staff_notes = str(exc)
        refund_request.save(update_fields=["status", "staff_notes", "updated_at"])
        return refund_request

    refund_request.razorpay_refund_id = response["id"]
    refund_request.razorpay_refund_status = response.get("status", "")
    refund_request.refund_initiated_at = timezone.now()
    refund_request.status = RefundRequest.REFUND_PROCESSING
    refund_request.save()
    return refund_request