from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Cart, CartItem, Product


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

# Create your tests here.
