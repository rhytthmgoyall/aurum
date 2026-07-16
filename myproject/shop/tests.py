from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .membership_services import calculate_order_totals
from .models import (
    Cart,
    CartItem,
    MembershipPlan,
    Order,
    Product,
    UserMembership,
    WalletTransaction,
)
from .wallet_services import credit_wallet


class SignupApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_signup_requires_all_fields(self):
        response = self.client.post("/api/signup/", {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "All fields are required")

    def test_signup_creates_user_cart_and_tokens(self):
        response = self.client.post(
            "/api/signup/",
            {
                "username": "newcustomer",
                "email": "newcustomer@example.com",
                "password": "StrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        user = User.objects.get(username="newcustomer")
        self.assertTrue(Cart.objects.filter(user=user).exists())


class CartApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="cartuser",
            email="cartuser@example.com",
            password="StrongPass123!",
        )
        self.product = Product.objects.create(name="Test Ring", price=250)
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    def test_add_to_cart_merges_existing_product_row(self):
        self.client.post(f"/api/cart/add/{self.product.id}/", format="json")
        self.client.post(f"/api/cart/add/{self.product.id}/", format="json")

        cart = Cart.objects.get(user=self.user)
        item = CartItem.objects.get(cart=cart, product=self.product)
        self.assertEqual(item.quantity, 2)

    def test_update_cart_item_increases_quantity(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)

        response = self.client.post(
            f"/api/cart/update/{self.product.id}/",
            {"action": "increase"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        item = CartItem.objects.get(cart=cart, product=self.product)
        self.assertEqual(item.quantity, 2)

    def test_update_cart_item_decrease_removes_at_one(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)

        response = self.client.post(
            f"/api/cart/update/{self.product.id}/",
            {"action": "decrease"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CartItem.objects.filter(cart=cart, product=self.product).exists())


class MembershipPricingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="selectmember",
            email="select@example.com",
            password="StrongPass123!",
        )
        self.plan = MembershipPlan.objects.create(
            name="Select Signature",
            price=Decimal("999.00"),
            billing_cycle=MembershipPlan.YEARLY,
            discount_percent=Decimal("10.00"),
            free_shipping=True,
            wallet_bonus_percent=Decimal("5.00"),
        )

    def test_active_membership_applies_discount_and_free_shipping(self):
        UserMembership.objects.create(
            user=self.user,
            plan=self.plan,
            status=UserMembership.ACTIVE,
            next_billing_date=timezone.now() + timedelta(days=30),
        )

        totals = calculate_order_totals(Decimal("100.00"), self.user)

        self.assertEqual(totals["membership_discount"], Decimal("10.00"))
        self.assertEqual(totals["shipping"], Decimal("0.00"))
        self.assertEqual(totals["tax"], Decimal("7.20"))
        self.assertEqual(totals["total"], Decimal("97.20"))

    def test_expired_membership_does_not_apply_benefits(self):
        UserMembership.objects.create(
            user=self.user,
            plan=self.plan,
            status=UserMembership.ACTIVE,
            next_billing_date=timezone.now() - timedelta(seconds=1),
        )

        totals = calculate_order_totals(Decimal("100.00"), self.user)

        self.assertEqual(totals["membership_discount"], Decimal("0.00"))
        self.assertEqual(totals["shipping"], Decimal("8.00"))
        self.assertEqual(totals["total"], Decimal("116.00"))

    def test_membership_cashback_is_idempotent_per_order(self):
        order = Order.objects.create(
            user=self.user,
            subtotal=Decimal("100.00"),
            total=Decimal("100.00"),
            status="paid",
        )

        first = credit_wallet(
            self.user,
            Decimal("5.00"),
            related_order=order,
            transaction_type=WalletTransaction.MEMBERSHIP_BONUS,
        )
        second = credit_wallet(
            self.user,
            Decimal("5.00"),
            related_order=order,
            transaction_type=WalletTransaction.MEMBERSHIP_BONUS,
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(self.user.wallet.balance, Decimal("5.00"))

    def test_membership_page_lists_available_plan(self):
        self.client.force_login(self.user)

        response = self.client.get("/profile/membership/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aurum Select")
        self.assertContains(response, self.plan.name)

# Create your tests here.
