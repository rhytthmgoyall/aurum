from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import uuid
import logging

logger = logging.getLogger(__name__)

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)

    description = models.TextField(
        blank=True,
        default=""
    )

    image = models.ImageField(
        upload_to="categories/",
        blank=True,
        default="categories/default.jpg"
    )

    is_active = models.BooleanField(
        default=True
    )

    display_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class Subcategory(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="subcategories",
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField()
    description = models.TextField(blank=True, default="")
    display_order = models.PositiveIntegerField(default=0)
    is_new = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Subcategories"
        unique_together = ("category", "slug")
        ordering = ["display_order", "name"]

    def __str__(self):
        return f"{self.category.name} -> {self.name}"


class Tag(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name

class MetalRateManager(models.Manager):
    def get_latest(self, metal, purity=None):
        queryset = self.filter(metal__iexact=metal)

        if purity:
            queryset = queryset.filter(purity__iexact=purity)
        else:
            queryset = queryset.filter(purity__isnull=True)

        return queryset.order_by("-fetched_at", "-id").first()


class MetalRate(models.Model):
    GOLD = "Gold"
    SILVER = "Silver"
    PLATINUM = "Platinum"

    METAL_CHOICES = (
        (GOLD, "Gold"),
        (SILVER, "Silver"),
        (PLATINUM, "Platinum"),
    )

    metal = models.CharField(
        max_length=20,
        choices=METAL_CHOICES,
        db_index=True,
    )
    purity = models.CharField(
        max_length=20,
        null=True,
        blank=True,
    )
    rate_per_gram = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    source = models.CharField(
        max_length=30,
        default="metalpriceapi",
    )
    fetched_at = models.DateTimeField(auto_now_add=True)

    objects = MetalRateManager()

    class Meta:
        ordering = ("-fetched_at", "-id")
        indexes = [
            models.Index(
                fields=("metal", "purity", "-fetched_at"),
                name="metal_rate_latest_idx",
            ),
        ]

    def __str__(self):
        purity = f" {self.purity}" if self.purity else ""
        return f"{self.metal}{purity}: ₹{self.rate_per_gram}/g"

SUPPORTED_METAL_PURITIES = {
    ("Gold", "14K"),
    ("Gold", "18K"),
    ("Gold", "22K"),
    ("Gold", "24K"),
    ("Silver", "925"),
    ("Platinum", "950"),
}

MATERIAL_PRICING_MAP = {
    "14k yellow gold": ("Gold", "14K"),
    "14k rose gold": ("Gold", "14K"),
    "14k white gold": ("Gold", "14K"),

    "18k yellow gold": ("Gold", "18K"),
    "18k rose gold": ("Gold", "18K"),
    "18k white gold": ("Gold", "18K"),

    "22k yellow gold": ("Gold", "22K"),
    "22k rose gold": ("Gold", "22K"),
    "22k white gold": ("Gold", "22K"),

    "24k yellow gold": ("Gold", "24K"),
    "24k rose gold": ("Gold", "24K"),
    "24k white gold": ("Gold", "24K"),
    "24k gold": ("Gold", "24K"),

    "sterling silver (925)": ("Silver", "925"),
    "silver": ("Silver", "925"),

    "platinum": ("Platinum", "950"),
    "platinum 950": ("Platinum", "950"),
}

class Product(models.Model):
    primary_category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="primary_products",
    )
    primary_subcategory = models.ForeignKey(
        Subcategory,
        on_delete=models.PROTECT,
        related_name="primary_products",
    )
    categories = models.ManyToManyField(Category, related_name="products", blank=True)
    subcategories = models.ManyToManyField(Subcategory, related_name="products", blank=True)

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=240, unique=True, null=True, blank=True)
    sku = models.CharField(max_length=80, unique=True, null=True, blank=True)
    price = models.IntegerField()
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    is_new = models.BooleanField(default=False)
    stock = models.PositiveIntegerField(default=0)

    material = models.CharField(max_length=30, blank=True, default="")
    purity = models.CharField(max_length=20, blank=True, default="")
    metal_color = models.CharField(max_length=30, blank=True, default="")
    stone_type = models.CharField(max_length=40, blank=True, default="")
    stone_cut = models.CharField(max_length=40, blank=True, default="")
    carat_weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    weight_grams = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    finish = models.CharField(max_length=40, blank=True, default="")
    setting = models.CharField(max_length=40, blank=True, default="")
    chain_style = models.CharField(max_length=40, blank=True, default="")
    collection = models.CharField(max_length=60, blank=True, default="")
    regional_style = models.CharField(max_length=60, blank=True, default="")
    enamel_color = models.CharField(max_length=30, blank=True, default="")
    size_detail = models.CharField(max_length=40, blank=True, default="")
    is_adjustable = models.BooleanField(default=False)
    is_personalized = models.BooleanField(default=False)
    engraving_text = models.CharField(max_length=80, blank=True, default="")
    occasion = models.CharField(max_length=30, blank=True, default="")
    who_for = models.CharField(max_length=20, blank=True, default="")
    price_range = models.CharField(max_length=30, blank=True, default="")
    description = models.TextField(blank=True, default="")

    tags = models.ManyToManyField(Tag, blank=True)

    variant_group = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
    )

    variant_attributes = models.JSONField(
        default=dict,
        blank=True,
    )

    making_charge_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("12.00"),
    )

    gemstone_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    def get_pricing_attributes(self, purity=None):
        attributes = self.variant_attributes or {}

        material = str(self.material or "").strip()
        material_key = material.lower()

        mapped = MATERIAL_PRICING_MAP.get(material_key)

        if mapped:
            metal, mapped_purity = mapped
            resolved_purity = purity or mapped_purity
            return metal, resolved_purity

        attribute_metal = str(attributes.get("metal") or "").strip()
        attribute_purity = str(attributes.get("purity") or "").strip()

        combined = " ".join(
            filter(
                None,
                (
                    attribute_metal,
                    material,
                    self.metal_color,
                ),
            )
        ).lower()

        if any(
            value in combined
            for value in (
                "stainless steel",
                "titanium",
                "vermeil",
            )
        ):
            return None, None

        resolved_purity = purity or attribute_purity or self.purity or None

        if "silver" in combined:
            return "Silver", resolved_purity or "925"

        if "platinum" in combined:
            return "Platinum", resolved_purity or "950"

        if "gold" in combined:
            return "Gold", resolved_purity

        return None, None

    def get_applicable_metal_rate(self, purity=None):
        metal, resolved_purity = self.get_pricing_attributes(purity=purity)

        if not metal or not resolved_purity:
            return None

        return MetalRate.objects.get_latest(
            metal=metal,
            purity=resolved_purity,
        )

    def get_computed_price(self, purity=None):
        stored_price = Decimal(str(self.price))

        if self.weight_grams is None:
            logger.warning(
                "Price calculation skipped for product %s: "
                "weight_grams is missing.",
                self.pk,
            )
            return stored_price

        metal, resolved_purity = self.get_pricing_attributes(purity=purity)

        if not metal:
            logger.warning(
                "Live pricing skipped for product %s with material '%s'; "
                "stored price preserved.",
                self.pk,
                self.material,
            )
            return stored_price

        if not resolved_purity:
            logger.warning(
                "Price calculation skipped for product %s: purity is missing.",
                self.pk,
            )
            return stored_price

        if (metal, resolved_purity) not in SUPPORTED_METAL_PURITIES:
            logger.warning(
                "Price calculation skipped for product %s: "
                "unsupported combination %s %s.",
                self.pk,
                metal,
                resolved_purity,
            )
            return stored_price

        rate = MetalRate.objects.get_latest(
            metal=metal,
            purity=resolved_purity,
        )

        if rate is None:
            logger.warning(
                "No MetalRate found for product %s: %s %s.",
                self.pk,
                metal,
                resolved_purity,
            )
            return stored_price

        weight = Decimal(str(self.weight_grams))
        making_percent = Decimal(str(self.making_charge_percent))
        stone_cost = Decimal(str(self.gemstone_cost))

        metal_cost = weight * rate.rate_per_gram
        making_charges = metal_cost * making_percent / Decimal("100")

        return (
            metal_cost
            + making_charges
            + stone_cost
        ).quantize(Decimal("0.01"))

    def get_variants(self):
        if not self.variant_group:
            return Product.objects.filter(pk=self.pk)

        return Product.objects.filter(
            variant_group=self.variant_group
        ).order_by("price", "id")

    def __str__(self):
        return self.name


class ProductStockVariant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="stock_variants",
    )
    size = models.CharField(max_length=40, null=True, blank=True)
    purity = models.CharField(max_length=20, null=True, blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    sku = models.CharField(max_length=100, unique=True)
    price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = (("product", "size", "purity"),)
        ordering = ("size", "purity", "id")

    @property
    def final_price(self):
        computed_price = self.product.get_computed_price(
            purity=self.purity
        )
        return computed_price + self.price_delta

    def __str__(self):
        selections = ", ".join(filter(None, (self.size, self.purity)))
        return f"{self.product.name} ({selections or self.sku})"

class ProductInteraction(models.Model):
    VIEW = "view"
    ADD_TO_CART = "add_to_cart"
    REMOVE_FROM_CART = "remove_from_cart"
    CHECKOUT = "checkout"
    PURCHASE = "purchase"

    EVENT_WEIGHTS = {
        VIEW: 1.0,
        ADD_TO_CART: 3.0,
        REMOVE_FROM_CART: -1.0,
        CHECKOUT: 4.0,
        PURCHASE: 5.0,
    }

    EVENT_CHOICES = (
        (VIEW, "View"),
        (ADD_TO_CART, "Add to cart"),
        (REMOVE_FROM_CART, "Remove from cart"),
        (CHECKOUT, "Checkout"),
        (PURCHASE, "Purchase"),
    )

    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="product_interactions",
    )
    session_key = models.CharField(max_length=100, blank=True)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="interactions",
    )
    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES)
    weight = models.FloatField(default=1.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=("user", "created_at")),
            models.Index(fields=("session_key", "created_at")),
            models.Index(fields=("product", "event_type")),
        ]
        ordering = ("-created_at",)

    def save(self, *args, **kwargs):
        if self.weight == 1.0:
            self.weight = self.EVENT_WEIGHTS.get(self.event_type, 1.0)
        super().save(*args, **kwargs)

    def __str__(self):
        actor = self.user_id or self.session_key or "anonymous"
        return f"{actor} {self.event_type} {self.product_id}"


class ProductEmbedding(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="embedding",
    )
    vector = models.JSONField(default=list)
    model_version = models.CharField(max_length=80)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=("model_version",)),
        ]

    def __str__(self):
        return f"{self.product_id} ({self.model_version})"


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    profile_picture = models.ImageField(
        upload_to="profile_pictures/",
        blank=True,
        null=True,
    )
    avatar_choice = models.CharField(
        max_length=40,
        blank=True,
        default="",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile of {self.user.username}"


class EmailSequenceState(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="email_sequence_state",
    )
    emails_sent = models.PositiveSmallIntegerField(default=0)
    next_send_at = models.DateTimeField(default=timezone.now)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email or self.user.username} - {self.emails_sent}/4"

class Review(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="reviews"
    )
    customer_name = models.CharField(max_length=100)
    rating = models.PositiveIntegerField(default=5)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer_name} - {self.product.name}"


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"Cart of {self.user.username}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("Product", on_delete=models.CASCADE)
    stock_variant = models.ForeignKey(
        "ProductStockVariant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("cart", "product", "stock_variant"),
                name="unique_cart_product_stock_variant",
            )
        ]

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

class ShippingAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="shipping_addresses")
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20)
    address_line = models.CharField(max_length=255)
    city = models.CharField(max_length=80)
    state = models.CharField(max_length=80)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=80, default="India")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name}, {self.city}"


class MembershipPlan(models.Model):
    MONTHLY = "monthly"
    YEARLY = "yearly"
    BILLING_CYCLE_CHOICES = (
        (MONTHLY, "Monthly"),
        (YEARLY, "Yearly"),
    )

    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    billing_cycle = models.CharField(max_length=10, choices=BILLING_CYCLE_CHOICES)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    free_shipping = models.BooleanField(default=False)
    wallet_bonus_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    razorpay_plan_id = models.CharField(max_length=100, blank=True, default="")

    def __str__(self):
        return f"{self.name} ({self.get_billing_cycle_display()})"


class UserMembership(models.Model):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    STATUS_CHOICES = (
        (ACTIVE, "Active"),
        (CANCELLED, "Cancelled"),
        (EXPIRED, "Expired"),
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="membership",
    )
    plan = models.ForeignKey(
        MembershipPlan,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)
    start_date = models.DateTimeField(default=timezone.now)
    next_billing_date = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    razorpay_subscription_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
    )

    @property
    def is_active(self):
        return (
            self.status == self.ACTIVE
            and self.next_billing_date is not None
            and self.next_billing_date > timezone.now()
        )

    def __str__(self):
        return f"{self.user.username} - {self.plan.name} ({self.status})"

class Order(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    shipping_address = models.ForeignKey(
        ShippingAddress,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders"
    )

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    membership_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - {self.user.username}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items"
    )
    product_name = models.CharField(max_length=200)
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    product_image = models.ImageField(upload_to="order_items/", blank=True, null=True)
    stock_variant = models.ForeignKey(
        "ProductStockVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    variant_size = models.CharField(max_length=40, blank=True, default="")
    variant_purity = models.CharField(max_length=20, blank=True, default="")
    variant_sku = models.CharField(max_length=100, blank=True, default="")
    quantity = models.PositiveIntegerField(default=1)
    item_total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"


class SocialAccount(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="social_accounts"
    )

    provider = models.CharField(
        max_length=50,
        default="google"
    )

    # Google's permanent unique user id comes from the "sub" field
    unique_id = models.CharField(
        max_length=255,
        unique=True
    )

    # Stores full Google user data like email, name, picture, etc.
    extra_data = models.JSONField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        unique_together = ("provider", "unique_id")

    def __str__(self):
        return f"{self.user.email} - {self.provider}"

class Payment(models.Model):
    STATUS_CHOICES = (
        ("created", "Created"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
        ("partially_refunded", "Partially Refunded"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.OneToOneField(
        "Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment"
    )
    razorpay_order_id = models.CharField(max_length=100, unique=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    razorpay_signature = models.CharField(max_length=255, blank=True)
    amount = models.IntegerField()
    currency = models.CharField(max_length=10, default="INR")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="created")
    refunded_amount = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

class Refund(models.Model):
    STATUS_CHOICES = (
        ("created", "Created"),
        ("pending", "Pending"),
        ("processed", "Processed"),
        ("failed", "Failed"),
    )

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="refunds"
    )
    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refunds"
    )
    razorpay_refund_id = models.CharField(max_length=100, unique=True)
    amount = models.IntegerField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES)
    speed_requested = models.CharField(max_length=30, blank=True, default="")
    speed_processed = models.CharField(max_length=30, blank=True, default="")
    receipt = models.CharField(max_length=100, blank=True, default="")
    reason = models.TextField(blank=True, default="")
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.razorpay_refund_id} - {self.status}"


class RefundRequest(models.Model):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PICKED_UP = "picked_up"
    QC_PASSED = "qc_passed"
    QC_FAILED = "qc_failed"
    REFUND_PROCESSING = "refund_processing"
    REFUND_FAILED = "refund_failed"
    REFUNDED = "refunded"

    STATUS_CHOICES = (
        (PENDING_REVIEW, "Pending Review"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
        (PICKED_UP, "Picked Up"),
        (QC_PASSED, "QC Passed"),
        (QC_FAILED, "QC Failed"),
        (REFUND_PROCESSING, "Refund Processing"),
        (REFUND_FAILED, "Refund Failed"),
        (REFUNDED, "Refunded"),
    )

    DEFECTIVE = "defective"
    WRONG_ITEM = "wrong_item"
    DOES_NOT_FIT = "does_not_fit"
    CHANGED_MIND = "changed_mind"
    QUALITY_ISSUE = "quality_issue"
    OTHER = "other"

    REASON_CHOICES = (
        (DEFECTIVE, "Defective"),
        (WRONG_ITEM, "Wrong Item"),
        (CHANGED_MIND, "Changed Mind"),
        (QUALITY_ISSUE, "Quality Issue"),
    )

    ORIGINAL_PAYMENT = "original_payment"
    STORE_CREDIT = "store_credit"
    WALLET = "wallet"

    REFUND_MODE_CHOICES = (
        (ORIGINAL_PAYMENT, "Original Payment"),
        (WALLET, "Wallet"),
    )

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="refund_requests",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="refund_requests",
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=PENDING_REVIEW,
    )
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    reason_detail = models.TextField(blank=True, default="")
    refund_mode = models.CharField(
        max_length=30,
        choices=REFUND_MODE_CHOICES,
        default=ORIGINAL_PAYMENT,
    )
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_refunded = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_refund_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    staff_notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    razorpay_refund_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    razorpay_refund_status = models.CharField(max_length=40, blank=True, default="")
    refund_initiated_at = models.DateTimeField(null=True, blank=True)
    refund_completed_at = models.DateTimeField(null=True, blank=True)
    wallet_transaction = models.ForeignKey(
        "WalletTransaction", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="refund_requests"
    )

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Refund request #{self.id} for order #{self.order_id}"


class RefundItem(models.Model):
    refund_request = models.ForeignKey(
        RefundRequest,
        on_delete=models.CASCADE,
        related_name="items",
    )
    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name="refund_request_items",
    )
    quantity_returned = models.PositiveIntegerField(default=1)
    item_condition_notes = models.TextField(blank=True, default="")

    def __str__(self):
        return f"{self.order_item.product_name} x {self.quantity_returned}"


class RefundImage(models.Model):
    refund_request = models.ForeignKey(
        RefundRequest,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="refund_requests/")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for refund request #{self.refund_request_id}"

class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class WalletTransaction(models.Model):
    REFUND_CREDIT = "refund_credit"
    TOP_UP = "top_up"
    MANUAL_ADJUSTMENT = "manual_adjustment"
    MEMBERSHIP_BONUS = "membership_bonus"

    SUCCESS = "success"
    PENDING = "pending"
    FAILED = "failed"

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=30, choices=[
        (REFUND_CREDIT, "Refund Credit"),
        (TOP_UP, "Top-Up"),
        (MANUAL_ADJUSTMENT, "Manual Adjustment"),
        (MEMBERSHIP_BONUS, "Aurum Select Cashback"),
    ])
    related_refund_request = models.ForeignKey(
        "RefundRequest", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="wallet_transactions"
    )
    related_order = models.OneToOneField(
        "Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="membership_bonus_transaction",
    )
    razorpay_payment_id = models.CharField(max_length=100, blank=True, default="")
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=[
        (SUCCESS, "Success"),
        (PENDING, "Pending"),
        (FAILED, "Failed"),
    ], default=SUCCESS)
    created_at = models.DateTimeField(auto_now_add=True)

class ChatConversation(models.Model):
    OPEN = "open"
    CLOSED = "closed"

    STATUS_CHOICES = (
        (OPEN, "Open"),
        (CLOSED, "Closed"),
    )

    user = models.ForeignKey(
    User,
    on_delete=models.CASCADE,
    related_name="chat_conversations",
    null=True,
    blank=True,
    )

    guest_name = models.CharField(max_length=120, blank=True)
    guest_email = models.EmailField(blank=True)
    guest_session_key = models.CharField(max_length=80, blank=True, db_index=True)

    last_message_preview = models.CharField(max_length=160, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    unread_by_staff = models.PositiveIntegerField(default=0)
    unread_by_user = models.PositiveIntegerField(default=0)
    closed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=OPEN)
    channel_name = models.CharField(max_length=120, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.user:
            return f"Chat with {self.user.username}"
        return f"Guest chat with {self.guest_name or 'Guest'}"


class ChatMessage(models.Model):
    conversation = models.ForeignKey(
        ChatConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    body = models.TextField()
    is_staff_message = models.BooleanField(default=False)
    is_ai_message = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return self.body[:60]
