from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.core.mail import send_mail
from django.utils import timezone
from .models import Category, MembershipPlan, Product, ProductEmbedding, ProductInteraction, ProductStockVariant, Review, Subcategory, UserMembership, UserProfile, Order, OrderItem
from .models import MetalRate
from .models import ShippingAddress
from .models import Payment, Refund, RefundImage, RefundItem, RefundRequest
from .models import ChatConversation, ChatMessage
from .refund_services import process_refund
from .models import Wallet, WalletTransaction


class RefundItemInline(admin.TabularInline):
    model = RefundItem
    extra = 0
    readonly_fields = ("order_item", "quantity_returned", "item_condition_notes")
    can_delete = False


class RefundImageInline(admin.TabularInline):
    model = RefundImage
    extra = 0


class SubcategoryInline(admin.TabularInline):
    model = Subcategory
    extra = 0
    fields = ("name", "slug", "display_order", "is_new", "description")
    prepopulated_fields = {"slug": ("name",)}


class ProductStockVariantInline(admin.TabularInline):
    model = ProductStockVariant
    extra = 0
    fields = ("size", "purity", "stock_quantity", "sku", "price_delta")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)
    inlines = (SubcategoryInline,)


@admin.register(Subcategory)
class SubcategoryAdmin(admin.ModelAdmin):
    list_display = ("category", "name", "display_order", "is_new")
    list_filter = ("category", "is_new")
    list_editable = ("display_order", "is_new")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "category__name")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "primary_category", "primary_subcategory", "price", "stock", "is_new")
    list_filter = ("primary_category", "primary_subcategory", "is_new", "collection", "material")
    search_fields = ("name", "slug", "primary_category__name", "primary_subcategory__name")
    filter_horizontal = ("categories", "subcategories", "tags")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ProductStockVariantInline,)


@admin.register(ProductStockVariant)
class ProductStockVariantAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "product",
        "size",
        "purity",
        "stock_quantity",
        "price_delta",
        "calculated_price",
    )
    list_filter = ("purity", "size", "product__primary_category")
    search_fields = ("sku", "product__name")
    list_editable = ("stock_quantity", "price_delta")
    autocomplete_fields = ("product",)
    ordering = ("product__name", "size", "purity")

    @admin.display(description="Calculated price")
    def calculated_price(self, obj):
        return obj.final_price


@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "billing_cycle",
        "price",
        "discount_percent",
        "free_shipping",
        "wallet_bonus_percent",
        "razorpay_plan_id",
    )
    list_filter = ("billing_cycle", "free_shipping")


@admin.register(UserMembership)
class UserMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "status",
        "start_date",
        "next_billing_date",
        "razorpay_subscription_id",
    )
    list_filter = ("status", "plan__billing_cycle")
    search_fields = ("user__username", "user__email", "razorpay_subscription_id")


class RefundRequestAdminForm(forms.ModelForm):
    class Meta:
        model = RefundRequest
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        rejection_reason = (cleaned_data.get("rejection_reason") or "").strip()

        if status in [RefundRequest.REJECTED, RefundRequest.QC_FAILED] and not rejection_reason:
            self.add_error(
                "rejection_reason",
                "Rejection reason is required when rejecting a refund request.",
            )

        if self.instance.pk:
            original = RefundRequest.objects.get(pk=self.instance.pk)
            if (
                original.reviewed_at
                and original.status in [RefundRequest.APPROVED, RefundRequest.REJECTED]
                and status in [RefundRequest.APPROVED, RefundRequest.REJECTED]
                and status != original.status
            ):
                raise forms.ValidationError(
                    "This request has already been reviewed and cannot be re-approved or re-rejected."
                )

        return cleaned_data


def _send_refund_review_email(refund_request):
    if not refund_request.user.email:
        return

    if refund_request.status == RefundRequest.APPROVED:
        subject = f"AURUM refund request #{refund_request.id} approved"
        message = (
            "Your refund request has been approved. "
            "Pickup and quality check updates will appear on your refund status page."
        )
    elif refund_request.status == RefundRequest.REJECTED:
        subject = f"AURUM refund request #{refund_request.id} rejected"
        message = refund_request.rejection_reason or "Your refund request was rejected."
    else:
        return

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [refund_request.user.email],
        fail_silently=True,
    )


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    form = RefundRequestAdminForm
    list_display = (
        "id",
        "status",
        "order",
        "user",
        "created_at",
        "reviewed_by",
        "reviewed_at",
        "razorpay_refund_id",
        "razorpay_refund_status",
    )
    list_filter = ("status", "reason", "refund_mode", "shipping_refunded", "created_at")
    search_fields = ("id", "order__id", "user__username", "user__email")
    list_editable = ("status",)
    readonly_fields = (
        "order",
        "user",
        "refund_amount",
        "shipping_refunded",
        "created_at",
        "updated_at",
        "reviewed_by",
        "reviewed_at",
        "razorpay_refund_id",
        "razorpay_refund_status",
        "refund_initiated_at",
        "refund_completed_at",
        "wallet_transaction",
    )
    inlines = (RefundItemInline, RefundImageInline)
    actions = ("approve_selected", "reject_selected", "mark_qc_passed", "retry_failed_refund")

    def save_model(self, request, obj, form, change):
        original_status = None

        if change:
            original = RefundRequest.objects.get(pk=obj.pk)
            original_status = original.status
            if (
                original.status == RefundRequest.PENDING_REVIEW
                and obj.status in [RefundRequest.APPROVED, RefundRequest.REJECTED]
                and not obj.reviewed_at
            ):
                obj.reviewed_by = request.user
                obj.reviewed_at = timezone.now()

        super().save_model(request, obj, form, change)

        if obj.status == RefundRequest.QC_PASSED:
            process_refund(obj)

        if original_status == RefundRequest.PENDING_REVIEW and obj.status in [
            RefundRequest.APPROVED,
            RefundRequest.REJECTED,
        ]:
            _send_refund_review_email(obj)

    @admin.action(description="Approve Selected")
    def approve_selected(self, request, queryset):
        eligible = queryset.filter(
            status=RefundRequest.PENDING_REVIEW,
            reviewed_at__isnull=True,
        )
        eligible_requests = list(eligible.select_related("user"))
        now = timezone.now()
        count = eligible.update(
            status=RefundRequest.APPROVED,
            reviewed_by=request.user,
            reviewed_at=now,
        )

        for refund_request in eligible_requests:
            refund_request.status = RefundRequest.APPROVED
            refund_request.reviewed_by = request.user
            refund_request.reviewed_at = now
            _send_refund_review_email(refund_request)

        skipped = queryset.count() - count
        if skipped:
            self.message_user(
                request,
                f"{skipped} request(s) were skipped because they were already reviewed.",
                messages.WARNING,
            )
        self.message_user(request, f"{count} refund request(s) approved.", messages.SUCCESS)

    @admin.action(description="Reject Selected")
    def reject_selected(self, request, queryset):
        eligible = queryset.filter(
            status=RefundRequest.PENDING_REVIEW,
            reviewed_at__isnull=True,
        ).exclude(rejection_reason="")
        eligible_requests = list(eligible.select_related("user"))
        now = timezone.now()
        count = eligible.update(
            status=RefundRequest.REJECTED,
            reviewed_by=request.user,
            reviewed_at=now,
        )

        for refund_request in eligible_requests:
            refund_request.status = RefundRequest.REJECTED
            refund_request.reviewed_by = request.user
            refund_request.reviewed_at = now
            _send_refund_review_email(refund_request)

        skipped = queryset.count() - count
        if skipped:
            self.message_user(
                request,
                "Some requests were skipped because they were already reviewed or missing a rejection reason.",
                messages.ERROR,
            )
        self.message_user(request, f"{count} refund request(s) rejected.", messages.SUCCESS)

    @admin.action(description="Mark QC Passed")
    def mark_qc_passed(self, request, queryset):
        for refund_request in queryset.filter(status=RefundRequest.PICKED_UP):
            refund_request.status = RefundRequest.QC_PASSED
            refund_request.save(update_fields=["status", "updated_at"])
            process_refund(refund_request)

    @admin.action(description="Retry Failed Refund")
    def retry_failed_refund(self, request, queryset):
        for refund_request in queryset.filter(status=RefundRequest.REFUND_FAILED):
            process_refund(refund_request)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "created_at", "updated_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("balance", "created_at", "updated_at")


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "wallet",
        "amount",
        "transaction_type",
        "status",
        "balance_after",
        "related_refund_request",
        "related_order",
        "created_at",
    )
    list_filter = ("transaction_type", "status", "created_at")
    search_fields = (
        "wallet__user__username",
        "wallet__user__email",
        "razorpay_payment_id",
        "related_refund_request__id",
        "related_order__id",
    )
    readonly_fields = (
        "wallet",
        "amount",
        "transaction_type",
        "related_refund_request",
        "related_order",
        "razorpay_payment_id",
        "balance_after",
        "notes",
        "status",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(MetalRate)
class MetalRateAdmin(admin.ModelAdmin):
    list_display = (
        "metal",
        "purity",
        "rate_per_gram",
        "source",
        "fetched_at",
    )
    list_filter = (
        "metal",
        "purity",
        "source",
    )
    ordering = ("-fetched_at",)
    readonly_fields = ("fetched_at",)

admin.site.register(ProductEmbedding)
admin.site.register(ProductInteraction)
admin.site.register(Review)
admin.site.register(UserProfile)
admin.site.register(ShippingAddress)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(Payment)
admin.site.register(Refund)
admin.site.register(RefundItem)
admin.site.register(RefundImage)
admin.site.register(ChatConversation)
admin.site.register(ChatMessage)
