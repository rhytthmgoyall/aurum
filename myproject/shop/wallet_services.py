from decimal import Decimal
from django.db import transaction
from .models import Wallet, WalletTransaction


def credit_wallet(user, amount, refund_request=None, related_order=None, transaction_type=WalletTransaction.REFUND_CREDIT, razorpay_payment_id="", notes=""):
    amount = Decimal(amount)

    with transaction.atomic():
        wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)

        if refund_request:
            existing = WalletTransaction.objects.filter(
                related_refund_request=refund_request,
                transaction_type=WalletTransaction.REFUND_CREDIT,
            ).first()
            if existing:
                return existing

        if razorpay_payment_id:
            existing = WalletTransaction.objects.filter(razorpay_payment_id=razorpay_payment_id).first()
            if existing:
                return existing

        if related_order:
            existing = WalletTransaction.objects.filter(
                related_order=related_order,
                transaction_type=WalletTransaction.MEMBERSHIP_BONUS,
            ).first()
            if existing:
                return existing

        wallet.balance += amount
        wallet.save(update_fields=["balance", "updated_at"])

        return WalletTransaction.objects.create(
            wallet=wallet,
            amount=amount,
            transaction_type=transaction_type,
            related_refund_request=refund_request,
            related_order=related_order,
            razorpay_payment_id=razorpay_payment_id,
            balance_after=wallet.balance,
            notes=notes,
            status=WalletTransaction.SUCCESS,
        )
