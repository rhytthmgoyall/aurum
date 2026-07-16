from multiprocessing import context
import hashlib
import hmac
import secrets
import time
import uuid
import json
import jwt
import logging
import razorpay

from datetime import datetime, timedelta, timezone as datetime_timezone
from urllib.parse import quote, urlencode

import secrets
import requests

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.http import HttpResponseBadRequest
from django.urls import reverse

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from .models import SocialAccount

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from .auth_helpers import generate_tokens
from django.conf import settings
from django.contrib.auth import authenticate
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Avg, Case, Count, F, IntegerField, Sum, Value, When
from django.db.models.functions import Abs
from django.http import JsonResponse
from django.templatetags.static import static
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from .tasks import send_order_confirmation_email
from .rag import generate_support_reply

from .models import Cart, CartItem, Category, MembershipPlan, Product, ProductInteraction, ProductStockVariant, ShippingAddress, Subcategory, UserMembership, UserProfile
from .forms import RefundRequestForm, RETURN_WINDOW_DAYS
from .recommender import get_product_recommendations, record_product_interaction
from decimal import Decimal
from .models import Order, OrderItem, Payment, Refund, RefundImage, RefundItem, RefundRequest
from .models import Wallet, WalletTransaction
from .wallet_services import credit_wallet
from .membership_services import calculate_order_totals

from agora_token_builder import RtmTokenBuilder
from django.views.decorators.http import require_GET
from .models import ChatConversation, ChatMessage

logger = logging.getLogger(__name__)

SIGNUP_CACHE_PREFIX = "pending_signup:"
SIGNUP_OTP_TTL_SECONDS = 5 * 60
SIGNUP_RESEND_COOLDOWN_SECONDS = 60
SIGNUP_MAX_ATTEMPTS = 5
PASSWORD_RESET_CACHE_PREFIX = "password_reset:"
PASSWORD_RESET_OTP_TTL_SECONDS = 5 * 60
PASSWORD_RESET_MAX_ATTEMPTS = 5
WALLET_TOPUP_MIN_AMOUNT = Decimal("100")
WALLET_TOPUP_MAX_AMOUNT = Decimal("50000")

AVATAR_CHOICES = [
    {"id": "parrot", "name": "Parrot", "image": "shop/img/avatars/parrot.jpg"},
    {"id": "snake", "name": "Snake", "image": "shop/img/avatars/snake.jpg"},
    {"id": "dog", "name": "Dog", "image": "shop/img/avatars/dog.jpg"},
    {"id": "swan", "name": "Swan", "image": "shop/img/avatars/swan.jpg"},
    {"id": "deer", "name": "Deer", "image": "shop/img/avatars/deer.jpg"},
    {"id": "cat", "name": "Cat", "image": "shop/img/avatars/cat.jpg"},
    {"id": "sheep", "name": "Sheep", "image": "shop/img/avatars/sheep.jpg"},
    {"id": "bird", "name": "Bird", "image": "shop/img/avatars/bird.jpg"},
]


def _pending_signup_cache_key(pending_id):
    return f"{SIGNUP_CACHE_PREFIX}{pending_id}"


def _generate_otp():
    return f"{secrets.randbelow(1_000_000):06d}"


def _send_signup_otp(email, otp):
    send_mail(
        subject="Your AURUM verification code",
        message=(
            f"Your verification code is {otp}.\n\n"
            "This code expires in 5 minutes. Do not share it with anyone."
        ),
        from_email=None,
        recipient_list=[email],
        fail_silently=False,
    )


def _password_reset_cache_key(reset_id):
    return f"{PASSWORD_RESET_CACHE_PREFIX}{reset_id}"


def _session_cart_key(product_id, stock_variant_id=None):
    if stock_variant_id:
        return f"{product_id}:{stock_variant_id}"
    return str(product_id)


def _parse_session_cart_key(key):
    product_id, separator, stock_variant_id = str(key).partition(":")
    try:
        product_id = int(product_id)
        stock_variant_id = int(stock_variant_id) if separator and stock_variant_id else None
    except (TypeError, ValueError):
        return None, None
    return product_id, stock_variant_id


def _get_cart_product_and_variant(cart_key, lock=False):
    product_id, stock_variant_id = _parse_session_cart_key(cart_key)
    if not product_id:
        return None, None

    product_query = Product.objects.select_for_update() if lock else Product.objects
    product = product_query.filter(id=product_id).first()
    if not product:
        return None, None

    stock_variant = None
    if stock_variant_id:
        variant_query = ProductStockVariant.objects.select_for_update() if lock else ProductStockVariant.objects
        stock_variant = variant_query.filter(
            id=stock_variant_id,
            product_id=product_id,
        ).first()
        if not stock_variant:
            return None, None

    return product, stock_variant


def _cart_unit_price(product, stock_variant=None):
    if stock_variant:
        return stock_variant.final_price
    return Decimal(product.price)


def _send_password_reset_otp(email, otp):
    send_mail(
        subject="Your AURUM password reset code",
        message=(
            f"Your password reset code is {otp}.\n\n"
            "This code expires in 5 minutes. If you did not request it, "
            "you can ignore this email."
        ),
        from_email=None,
        recipient_list=[email],
        fail_silently=False,
    )


def _merge_session_cart_to_database(user, session):
    session_cart = session.get("cart", {})

    cart, _ = Cart.objects.get_or_create(user=user)
    cart.items.all().delete()

    if not session_cart:
        return

    for cart_key, quantity in session_cart.items():
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            continue

        if quantity <= 0:
            continue

        product, stock_variant = _get_cart_product_and_variant(cart_key)

        if not product:
            continue

        CartItem.objects.create(
            cart=cart,
            product=product,
            stock_variant=stock_variant,
            quantity=quantity,
        )


def _load_database_cart_to_session(user, session):
    cart = Cart.objects.filter(user=user).first()

    if not cart:
        return

    session_cart = session.get("cart", {}).copy()

    for item in cart.items.select_related("product", "stock_variant"):
        cart_key = _session_cart_key(item.product_id, item.stock_variant_id)
        session_cart[cart_key] = session_cart.get(cart_key, 0) + item.quantity

    session["cart"] = session_cart
    if hasattr(session, "modified"):
        session.modified = True


class AnyMethodAsGetMixin:
    def dispatch(self, request, *args, **kwargs):
        handler = getattr(self, request.method.lower(), None)
        if handler is None:
            handler = self.get
        return handler(request, *args, **kwargs)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class HomeView(AnyMethodAsGetMixin, View):
    def get(self, request):
        print("USER:", request.user)
        print("AUTH:", request.user.is_authenticated)

        categories = list(
            Category.objects.filter(is_active=True).prefetch_related("subcategories")
        )

        # Products still use the original detailed categories. Map those records
        # into the eight customer-facing umbrella categories used by this page.
        category_groups = {
            "Everyday Fine Jewellery": [
                "Everyday Fine Jewellery", "Gold Jewellery", "Diamond Jewellery",
                "Platinum Jewellery", "Gemstone Jewellery", "Pearl Jewellery",
                "Silver Jewellery", "Temple Jewellery",
            ],
            "Bridal Collection": ["Bridal Collection"],
            "Men's": ["Men's Jewellery", "Men's Western"],
            "Kids": ["Kids Jewellery"],
            "Western": [
                "Western Necklaces", "Western Bracelets", "Western Earrings",
                "Western Rings",
            ],
            "Timepieces": ["Watches & Timepieces"],
            "Accessories": ["Accessories"],
            "Gifting & Combo Sets": ["Gifting & Combo Sets"],
        }
        visible_category_ids = {category.name: category.id for category in categories}
        mapping_rules = []
        for display_name, source_names in category_groups.items():
            display_id = visible_category_ids.get(display_name)
            if display_id:
                mapping_rules.append(
                    When(primary_category__name__in=source_names, then=Value(display_id))
                )

        products = Product.objects.select_related("primary_category").annotate(
            display_category_id=Case(
                *mapping_rules,
                default=F("primary_category_id"),
                output_field=IntegerField(),
            )
        )
        mapped_counts = dict(
            products.values("display_category_id")
            .annotate(total=Count("id"))
            .values_list("display_category_id", "total")
        )
        for category in categories:
            category.product_count = mapped_counts.get(category.id, 0)
        new_products = Product.objects.filter(is_new=True)

        profile_picture_url = ""

        if request.user.is_authenticated:
            profile = UserProfile.objects.filter(user=request.user).first()
            if profile:
                if profile.profile_picture:
                    profile_picture_url = profile.profile_picture.url
                elif profile.avatar_choice:
                    avatar = next(
                        (
                            item
                            for item in AVATAR_CHOICES
                            if item["id"] == profile.avatar_choice
                        ),
                        None,
                    )
                    if avatar:
                        profile_picture_url = static(avatar["image"])
        
        return render(
            request,
            "shop/products/e-commerce.html",
            {"products": products, "categories": categories, "profile_picture_url": profile_picture_url, "new_products": new_products}
        )


class ProductDetailView(AnyMethodAsGetMixin, View):
    def get(self, request, id):
        product = get_object_or_404(Product, id=id)
        record_product_interaction(request, product, ProductInteraction.VIEW)

        variants = list(product.get_variants())
        attribute_keys = []
        for variant in variants:
            for key in variant.variant_attributes:
                if key not in attribute_keys:
                    attribute_keys.append(key)

        variant_selectors = []
        current_attributes = product.variant_attributes or {}
        for attribute_key in attribute_keys:
            options = []
            seen_values = set()

            for variant in variants:
                value = (variant.variant_attributes or {}).get(attribute_key)
                value_marker = str(value)
                if value in (None, "") or value_marker in seen_values:
                    continue
                seen_values.add(value_marker)

                candidates = [
                    sibling for sibling in variants
                    if (sibling.variant_attributes or {}).get(attribute_key) == value
                ]
                is_active = current_attributes.get(attribute_key) == value

                if is_active:
                    target = product
                else:
                    other_keys = [key for key in attribute_keys if key != attribute_key]
                    target = max(
                        candidates,
                        key=lambda sibling: sum(
                            (sibling.variant_attributes or {}).get(key)
                            == current_attributes.get(key)
                            for key in other_keys
                        ),
                    )

                options.append({
                    "value": value,
                    "product": target,
                    "is_active": is_active,
                    "is_available": target.stock > 0,
                })

            if options:
                variant_selectors.append({
                    "key": attribute_key,
                    "label": attribute_key.replace("_", " ").title(),
                    "options": options,
                })

        stock_variants = list(product.stock_variants.all())
        size_options = list(dict.fromkeys(
            variant.size for variant in stock_variants if variant.size
        ))
        purity_options = list(dict.fromkeys(
            variant.purity for variant in stock_variants if variant.purity
        ))
        default_stock_variant = next(
            (variant for variant in stock_variants if variant.stock_quantity > 0),
            stock_variants[0] if stock_variants else None,
        )

        reviews = product.reviews.all().order_by("-created_at")

        avg_rating = product.reviews.aggregate(Avg("rating"))["rating__avg"] or 0

        review_count = product.reviews.count()

        more_pieces, recommendation_source, recommendation_explanation = (
            get_product_recommendations(anchor_product=product, limit=4)
        )

        return render(request, "shop/products/product_detail.html", {
            "product": product,
            "variants": variants,
            "variant_selectors": variant_selectors,
            "stock_variants": stock_variants,
            "size_options": size_options,
            "purity_options": purity_options,
            "default_stock_variant": default_stock_variant,
            "reviews": reviews,
            "avg_rating": avg_rating,
            "review_count": review_count,
            "more_pieces": more_pieces,
            "recommendation_source": recommendation_source,
            "recommendation_explanation": recommendation_explanation,
        })


class ProductVariantStockApiView(View):
    def get(self, request, id):
        product = get_object_or_404(Product, id=id)
        size = request.GET.get("size") or None
        purity = request.GET.get("purity") or None

        variants = product.stock_variants.all()
        if size is None:
            variants = variants.filter(size__isnull=True)
        else:
            variants = variants.filter(size=size)
        if purity is None:
            variants = variants.filter(purity__isnull=True)
        else:
            variants = variants.filter(purity=purity)

        stock_variant = variants.first()
        if not stock_variant:
            return JsonResponse({
                "available": False,
                "error": "This size and purity combination is not available.",
            }, status=404)

        return JsonResponse({
            "available": stock_variant.stock_quantity > 0,
            "stock_variant_id": stock_variant.id,
            "sku": stock_variant.sku,
            "size": stock_variant.size,
            "purity": stock_variant.purity,
            "price": str(stock_variant.final_price),
            "stock_quantity": stock_variant.stock_quantity,
        })


class SearchView(AnyMethodAsGetMixin, View):
    def get(self, request):
        query = request.GET.get("q", "")
        selected_sort = request.GET.get("sort", "")
        categories = Category.objects.filter(is_active=True)

        products = Product.objects.annotate(
            avg_rating=Avg("reviews__rating"),
            review_count=Count("reviews")
        )

        if query:
            products = products.filter(name__icontains=query)

        selected_category = request.GET.get("category", "")

        if selected_category:
            products = products.filter(
                categories__id=selected_category
            )

        if selected_sort == "price_low":
            products = products.order_by("price")
        elif selected_sort == "price_high":
            products = products.order_by("-price")
        elif selected_sort == "name_az":
            products = products.order_by("name")
        elif selected_sort == "name_za":
            products = products.order_by("-name")
        elif selected_sort == "rating_high":
            products = products.order_by("-avg_rating")
        elif selected_sort == "most_reviewed":
            products = products.order_by("-review_count")
        else:
            products = products.order_by("id")

        paginator = Paginator(products, 8)
        page_obj = paginator.get_page(request.GET.get("page"))

        return render(request, "shop/products/search_results.html", {
            "products": page_obj,
            "page_obj": page_obj,
            "query": query,
            "categories": categories,
            "selected_category": selected_category,
            "selected_sort": selected_sort,
        })


class CategoryBrowseView(AnyMethodAsGetMixin, View):
    def get(self, request, category_slug, subcategory_slug=None):
        category = get_object_or_404(
            Category.objects.prefetch_related("subcategories"),
            slug=category_slug,
            is_active=True,
        )
        subcategory = None

        products = Product.objects.filter(categories=category).annotate(
            avg_rating=Avg("reviews__rating"),
            review_count=Count("reviews"),
        )

        if subcategory_slug:
            subcategory = get_object_or_404(
                Subcategory,
                category=category,
                slug=subcategory_slug,
            )
            products = products.filter(subcategories=subcategory)

        selected_sort = request.GET.get("sort", "")

        if selected_sort == "price_low":
            products = products.order_by("price")
        elif selected_sort == "price_high":
            products = products.order_by("-price")
        elif selected_sort == "name_az":
            products = products.order_by("name")
        elif selected_sort == "name_za":
            products = products.order_by("-name")
        elif selected_sort == "rating_high":
            products = products.order_by("-avg_rating")
        elif selected_sort == "most_reviewed":
            products = products.order_by("-review_count")
        else:
            products = products.order_by("id")

        paginator = Paginator(products.distinct(), 12)
        page_obj = paginator.get_page(request.GET.get("page"))
        title = category.name if subcategory is None else f"{subcategory.name} in {category.name}"

        return render(request, "shop/products/search_results.html", {
            "products": page_obj,
            "page_obj": page_obj,
            "query": title,
            "categories": Category.objects.filter(is_active=True),
            "selected_category": str(category.id),
            "selected_sort": selected_sort,
            "browse_category": category,
            "browse_subcategory": subcategory,
        })


class ProductDetailApiView(AnyMethodAsGetMixin, View):
    def get(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        data = {
            'id': product.id,
            'name': product.name,
            'price': str(product.price),
            'category': product.primary_category.name if product.primary_category else None,
            'image': product.image.url if product.image else None,
        }
        return JsonResponse(data)


class LoginView(AnyMethodAsGetMixin, View):
    def get(self, request):
        return render(request, "shop/auth/login.html")

    def post(self, request):
        u = request.POST.get("username")
        p = request.POST.get("password")

        user = authenticate(request, username=u, password=p)

        if user is not None:
            login(request, user)
            _load_database_cart_to_session(user, request.session)

            response = redirect("home")

            access, refresh = generate_tokens(user)

            response.set_cookie(
                "access_token",
                access,
                httponly=True,
                samesite="Lax",
                path="/"
            )

            response.set_cookie(
                "refresh_token",
                refresh,
                httponly=True,
                samesite="Lax",
                path="/"
            )

            return response

        return render(request, "shop/auth/login.html", {
            "error": "Invalid Credentials"
        })


class DashboardView(AnyMethodAsGetMixin, View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('login')
        return render(request, 'shop/auth/profile.html', {'username': request.user.username})


class LogoutView(AnyMethodAsGetMixin, View):
    def get(self, request):
        if request.user.is_authenticated:
            _merge_session_cart_to_database(request.user, request.session)

        response = redirect("home")

        logout(request)

        response.delete_cookie("access_token", path="/")
        response.delete_cookie("refresh_token", path="/")
        response.delete_cookie("sessionid", path="/")

        return response


class SignupPageView(AnyMethodAsGetMixin, TemplateView):
    template_name = "shop/auth/signup.html"


class VerifySignupPageView(AnyMethodAsGetMixin, TemplateView):
    template_name = "shop/auth/verify_signup.html"


class ForgotPasswordPageView(AnyMethodAsGetMixin, TemplateView):
    template_name = "shop/auth/forgot_password.html"


class PasswordResetStartApiView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        identifier = str(request.data.get("identifier", "")).strip()

        if not identifier:
            return Response({"error": "Enter your username or email"}, status=400)

        user = User.objects.filter(email__iexact=identifier).first()

        if user is None:
            user = User.objects.filter(username__iexact=identifier).first()

        if user is None or not user.email:
            return Response(
                {"error": "No active account was found for those details"},
                status=404,
            )

        reset_id = uuid.uuid4().hex
        otp = _generate_otp()

        reset_request = {
            "user_id": user.id,
            "email": user.email,
            "otp_hash": make_password(otp),
            "attempts": 0,
            "verified": False,
            "expires_at": time.time() + PASSWORD_RESET_OTP_TTL_SECONDS,
        }

        cache.set(
            _password_reset_cache_key(reset_id),
            reset_request,
            timeout=PASSWORD_RESET_OTP_TTL_SECONDS,
        )

        try:
            _send_password_reset_otp(user.email, otp)
        except Exception:
            cache.delete(_password_reset_cache_key(reset_id))
            return Response(
                {"error": "Unable to send password reset email"},
                status=503,
            )

        return Response({
            "password_reset_id": reset_id,
            "email": user.email,
            "message": "Password reset code sent",
        })


class PasswordResetVerifyApiView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        reset_id = str(request.data.get("password_reset_id", "")).strip()
        otp = str(request.data.get("otp", "")).strip()
        cache_key = _password_reset_cache_key(reset_id)
        reset_request = cache.get(cache_key)

        if not reset_request:
            return Response(
                {"error": "Password reset request was not found or has expired"},
                status=400,
            )

        remaining_seconds = int(reset_request["expires_at"] - time.time())
        if remaining_seconds <= 0:
            cache.delete(cache_key)
            return Response({"error": "Password reset code has expired"}, status=400)

        if reset_request["attempts"] >= PASSWORD_RESET_MAX_ATTEMPTS:
            cache.delete(cache_key)
            return Response(
                {"error": "Too many incorrect attempts. Start again."},
                status=429,
            )

        if not otp.isdigit() or len(otp) != 6:
            return Response({"error": "Enter a valid six-digit code"}, status=400)

        if not check_password(otp, reset_request["otp_hash"]):
            reset_request["attempts"] += 1
            cache.set(cache_key, reset_request, timeout=remaining_seconds)
            return Response({"error": "Incorrect verification code"}, status=400)

        reset_request["verified"] = True
        cache.set(cache_key, reset_request, timeout=remaining_seconds)

        return Response({"message": "Code verified"})


class PasswordResetCompleteApiView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        reset_id = str(request.data.get("password_reset_id", "")).strip()
        password = str(request.data.get("password", ""))
        confirm_password = str(request.data.get("confirm_password", ""))
        cache_key = _password_reset_cache_key(reset_id)
        reset_request = cache.get(cache_key)

        if not reset_request:
            return Response(
                {"error": "Password reset request was not found or has expired"},
                status=400,
            )

        if not reset_request.get("verified"):
            return Response({"error": "Verify the code first"}, status=400)

        if not password or not confirm_password:
            return Response({"error": "Both password fields are required"}, status=400)

        if password != confirm_password:
            return Response({"error": "Passwords do not match"}, status=400)

        user = User.objects.filter(id=reset_request["user_id"]).first()

        if user is None:
            cache.delete(cache_key)
            return Response({"error": "User account was not found"}, status=400)

        try:
            validate_password(password, user=user)
        except ValidationError as error:
            return Response({"error": " ".join(error.messages)}, status=400)

        user.set_password(password)
        user.save(update_fields=("password",))
        cache.delete(cache_key)

        return Response({"message": "Password reset successfully"})


class CartPageView(AnyMethodAsGetMixin, View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("login")

        session_cart = request.session.get("cart", {})

        cart_items = []
        total = Decimal("0")

        for cart_key, quantity in session_cart.items():
            product, stock_variant = _get_cart_product_and_variant(cart_key)

            if not product:
                continue

            unit_price = _cart_unit_price(product, stock_variant)
            subtotal = unit_price * quantity
            total += subtotal

            cart_items.append({
                "product": product,
                "stock_variant": stock_variant,
                "cart_key": cart_key,
                "unit_price": unit_price,
                "quantity": quantity,
                "subtotal": subtotal,
            })

        totals = calculate_order_totals(total, request.user)

        return render(request, "shop/cart/cart.html", {
            "cart_items": cart_items,
            **totals,
        })


class SignupStartApiView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = str(request.data.get("username", "")).strip()
        email = str(request.data.get("email", "")).strip().lower()
        password = str(request.data.get("password", ""))
        confirm_password = str(request.data.get("confirm_password", ""))

        if not username or not email or not password or not confirm_password:
            return Response({"error": "All fields are required"}, status=400)

        if password != confirm_password:
            return Response({"error": "Passwords do not match"}, status=400)

        try:
            validate_email(email)
        except ValidationError:
            return Response({"error": "Enter a valid email address"}, status=400)

        if User.objects.filter(username__iexact=username).exists():
            return Response({"error": "Username already exists"}, status=400)

        if User.objects.filter(email__iexact=email).exists():
            return Response({"error": "Email address already exists"}, status=400)

        pending_user = User(username=username, email=email)
        try:
            validate_password(password, user=pending_user)
            pending_user.full_clean(exclude=("password",))
        except ValidationError as error:
            return Response({"error": " ".join(error.messages)}, status=400)

        pending_id = uuid.uuid4().hex
        otp = _generate_otp()
        pending_signup = {
            "username": username,
            "email": email,
            "password_hash": make_password(password),
            "otp_hash": make_password(otp),
            "attempts": 0,
            "last_sent_at": time.time(),
            "expires_at": time.time() + SIGNUP_OTP_TTL_SECONDS,
        }

        cache.set(
            _pending_signup_cache_key(pending_id),
            pending_signup,
            timeout=SIGNUP_OTP_TTL_SECONDS,
        )

        try:
            _send_signup_otp(email, otp)
        except Exception:
            cache.delete(_pending_signup_cache_key(pending_id))
            return Response(
                {"error": "Unable to send verification email"},
                status=503,
            )

        return Response({
            "pending_signup_id": pending_id,
            "message": "Verification code sent",
        })

class SignupVerifyApiView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        pending_id = str(request.data.get("pending_signup_id", "")).strip()
        otp = str(request.data.get("otp", "")).strip()
        cache_key = _pending_signup_cache_key(pending_id)
        pending_signup = cache.get(cache_key)
        if not pending_signup:
            return Response(
                {"error": "Signup request was not found or has expired"},
                status=400,
            )

        remaining_seconds = int(pending_signup["expires_at"] - time.time())
        if remaining_seconds <= 0:
            cache.delete(cache_key)
            return Response(
                {"error": "Verification code has expired"},
                status=400,
            )

        if pending_signup["attempts"] >= SIGNUP_MAX_ATTEMPTS:
            cache.delete(cache_key)
            return Response(
                {"error": "Too many incorrect attempts. Start signup again."},
                status=429,
            )

        if not otp.isdigit() or len(otp) != 6:
            return Response(
                {"error": "Enter a valid six-digit code"},
                status=400,
            )

        if not check_password(otp, pending_signup["otp_hash"]):
            pending_signup["attempts"] += 1
            cache.set(cache_key, pending_signup, timeout=remaining_seconds)
            return Response({"error": "Incorrect verification code"}, status=400)

        try:
            with transaction.atomic():
                if User.objects.filter(
                    username__iexact=pending_signup["username"]
                ).exists():
                    return Response(
                        {"error": "Username already exists"},
                        status=400,
                    )

                if User.objects.filter(
                    email__iexact=pending_signup["email"]
                ).exists():
                    return Response(
                        {"error": "Email address already exists"},
                        status=400,
                    )

                user = User(
                    username=pending_signup["username"],
                    email=pending_signup["email"],
                    password=pending_signup["password_hash"],
                )
                user.save()
                Cart.objects.create(user=user)
        except IntegrityError:
            return Response(
                {"error": "Unable to create account with those details"},
                status=400,
            )

        cache.delete(cache_key)
        refresh = RefreshToken.for_user(user)

        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        })


class SignupResendApiView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        pending_id = str(request.data.get("pending_signup_id", "")).strip()
        cache_key = _pending_signup_cache_key(pending_id)
        pending_signup = cache.get(cache_key)

        if not pending_signup:
            return Response(
                {"error": "Signup request was not found or has expired"},
                status=400,
            )

        elapsed = time.time() - pending_signup["last_sent_at"]
        if elapsed < SIGNUP_RESEND_COOLDOWN_SECONDS:
            wait_seconds = int(SIGNUP_RESEND_COOLDOWN_SECONDS - elapsed) + 1
            return Response(
                {"error": f"Wait {wait_seconds} seconds before resending"},
                status=429,
            )

        otp = _generate_otp()
        pending_signup["otp_hash"] = make_password(otp)
        pending_signup["attempts"] = 0
        pending_signup["last_sent_at"] = time.time()
        pending_signup["expires_at"] = time.time() + SIGNUP_OTP_TTL_SECONDS

        try:
            _send_signup_otp(pending_signup["email"], otp)
        except Exception:
            return Response(
                {"error": "Unable to resend verification email"},
                status=503,
            )

        cache.set(
            cache_key,
            pending_signup,
            timeout=SIGNUP_OTP_TTL_SECONDS,
        )
        return Response({"message": "Verification code resent"})


class SessionCartCountView(AnyMethodAsGetMixin, View):
    def get(self, request):
        cart = request.session.get("cart", {})

        return JsonResponse({
            "count": sum(cart.values())
        })


class AddToSessionCartView(View):
    def post(self, request, product_id):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Login required"}, status=401)

        product = get_object_or_404(Product, id=product_id)
        stock_variant_id = request.POST.get("stock_variant_id")
        stock_variant = None
        if stock_variant_id:
            stock_variant = get_object_or_404(
                ProductStockVariant,
                id=stock_variant_id,
                product=product,
            )
        elif product.stock_variants.exists():
            return JsonResponse({"error": "Please select size and purity options."}, status=400)

        record_product_interaction(request, product, ProductInteraction.ADD_TO_CART)

        cart = request.session.get("cart", {})
        cart_key = _session_cart_key(product.id, stock_variant.id if stock_variant else None)
        available_stock = stock_variant.stock_quantity if stock_variant else product.stock
        if cart.get(cart_key, 0) >= available_stock:
            return JsonResponse({"error": "No more stock is available for this selection."}, status=400)

        cart[cart_key] = cart.get(cart_key, 0) + 1

        request.session["cart"] = cart
        request.session.modified = True

        return redirect("cart")


class DecreaseSessionCartView(View):
    def post(self, request, product_id):
        if not request.user.is_authenticated:
            return redirect("login")

        cart = request.session.get("cart", {})
        stock_variant_id = request.POST.get("stock_variant_id")
        cart_key = _session_cart_key(product_id, stock_variant_id)

        if cart_key in cart:
            if cart[cart_key] <= 1:
                del cart[cart_key]
            else:
                cart[cart_key] -= 1

        request.session["cart"] = cart
        request.session.modified = True

        return redirect("cart")


class RemoveFromSessionCartView(View):
    def post(self, request, product_id):
        if not request.user.is_authenticated:
            return redirect("login")

        product = Product.objects.filter(id=product_id).first()
        if product:
            record_product_interaction(request, product, ProductInteraction.REMOVE_FROM_CART)

        cart = request.session.get("cart", {})
        stock_variant_id = request.POST.get("stock_variant_id")
        cart_key = _session_cart_key(product_id, stock_variant_id)

        if cart_key in cart:
            del cart[cart_key]

        request.session["cart"] = cart
        request.session.modified = True

        return redirect("cart")

class UpdateCartItemApiView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, product_id):
        action = request.data.get("action")
        stock_variant_id = request.data.get("stock_variant_id")
        cart = get_object_or_404(Cart, user=request.user)
        cart_item = get_object_or_404(
            CartItem,
            cart=cart,
            product_id=product_id,
            stock_variant_id=stock_variant_id or None,
        )

        if action == "increase":
            record_product_interaction(request, cart_item.product, ProductInteraction.ADD_TO_CART)
            cart_item.quantity += 1
            cart_item.save(update_fields=("quantity",))
            return Response({"message": "Quantity increased"})

        if action == "decrease":
            record_product_interaction(request, cart_item.product, ProductInteraction.REMOVE_FROM_CART)
            if cart_item.quantity <= 1:
                cart_item.delete()
                return Response({"message": "Product removed from cart"})

            cart_item.quantity -= 1
            cart_item.save(update_fields=("quantity",))
            return Response({"message": "Quantity decreased"})

        return Response({"error": "Invalid action"}, status=400)


class RemoveFromCartApiView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, product_id):
        cart = get_object_or_404(Cart, user=request.user)
        product = Product.objects.filter(id=product_id).first()
        if product:
            record_product_interaction(request, product, ProductInteraction.REMOVE_FROM_CART)

        stock_variant_id = request.data.get("stock_variant_id") or request.query_params.get("stock_variant_id")
        CartItem.objects.filter(
            cart=cart,
            product_id=product_id,
            stock_variant_id=stock_variant_id or None,
        ).delete()

        return Response({
            "message": "Product removed from cart"
        })


class ProfilePageView(AnyMethodAsGetMixin, View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("login")

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        
        return render(request, "shop/auth/profile.html", {
            "user": request.user,
            "profile": profile,
            "wallet": wallet,
            "avatar_choices": AVATAR_CHOICES,
            "username": request.user.username,
            "email": request.user.email,
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
        })
    
    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("login")

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        selected_avatar = request.POST.get("avatar_choice", "")
        valid_avatar_ids = {avatar["id"] for avatar in AVATAR_CHOICES}

        if request.FILES.get("profile_picture"):
            profile.profile_picture = request.FILES["profile_picture"]
            profile.avatar_choice = ""
            profile.save(update_fields=("profile_picture", "avatar_choice", "updated_at"))
        elif selected_avatar in valid_avatar_ids:
            profile.profile_picture = None
            profile.avatar_choice = selected_avatar
            profile.save(update_fields=("profile_picture", "avatar_choice", "updated_at"))

        return redirect("profile")


class WalletBalanceView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("login")

        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        transactions = (
            wallet.transactions
            .select_related("related_refund_request", "related_refund_request__order")
            .order_by("-created_at")
        )

        return render(request, "shop/wallet.html", {
            "wallet": wallet,
            "transactions": transactions,
            "min_topup_amount": WALLET_TOPUP_MIN_AMOUNT,
            "max_topup_amount": WALLET_TOPUP_MAX_AMOUNT,
        })


class WalletTopUpView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("login")

        return redirect("wallet_balance")

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("login")

        try:
            amount = Decimal(str(request.POST.get("amount", ""))).quantize(Decimal("0.01"))
        except Exception:
            messages.error(request, "Enter a valid top-up amount.")
            return redirect("wallet_balance")

        if amount < WALLET_TOPUP_MIN_AMOUNT or amount > WALLET_TOPUP_MAX_AMOUNT:
            messages.error(
                request,
                f"Top-up amount must be between Rs. {WALLET_TOPUP_MIN_AMOUNT} and Rs. {WALLET_TOPUP_MAX_AMOUNT}.",
            )
            return redirect("wallet_balance")

        amount_paise = int(amount * Decimal("100"))
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        razorpay_order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "payment_capture": 1,
            "receipt": f"wallet_topup_{request.user.id}_{get_random_string(8)}",
            "notes": {
                "user_id": str(request.user.id),
                "purpose": "wallet_topup",
            },
        })

        request.session["wallet_topup"] = {
            "razorpay_order_id": razorpay_order["id"],
            "amount": str(amount),
        }
        request.session.modified = True

        return render(request, "shop/wallet_topup.html", {
            "key": settings.RAZORPAY_KEY_ID,
            "amount_paise": amount_paise,
            "amount": amount,
            "razorpay_order_id": razorpay_order["id"],
            "callback_url": reverse("wallet_topup_verify"),
            "customer_name": request.user.get_full_name() or request.user.username,
            "customer_email": request.user.email,
        })


class WalletTopUpVerifyView(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Login required"}, status=401)

        try:
            data = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        razorpay_order_id = data.get("razorpay_order_id", "")
        razorpay_payment_id = data.get("razorpay_payment_id", "")
        razorpay_signature = data.get("razorpay_signature", "")
        topup_session = request.session.get("wallet_topup") or {}

        if razorpay_order_id != topup_session.get("razorpay_order_id"):
            return JsonResponse({"error": "Invalid wallet top-up session"}, status=400)

        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

        try:
            client.utility.verify_payment_signature({
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            })
        except razorpay.errors.SignatureVerificationError:
            return JsonResponse({"error": "Payment verification failed"}, status=400)

        amount = Decimal(topup_session["amount"])
        transaction_row = credit_wallet(
            request.user,
            amount,
            transaction_type=WalletTransaction.TOP_UP,
            razorpay_payment_id=razorpay_payment_id,
            notes="Wallet top-up",
        )
        request.session.pop("wallet_topup", None)
        request.session.modified = True

        return JsonResponse({
            "message": "Wallet credited",
            "transaction_id": transaction_row.id,
            "balance": str(transaction_row.balance_after),
        })


@method_decorator(ensure_csrf_cookie, name="dispatch")
class MembershipPageView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={reverse('membership')}")

        membership = UserMembership.objects.filter(
            user=request.user
        ).select_related("plan").first()
        plans = MembershipPlan.objects.all().order_by("price", "billing_cycle")
        return render(request, "shop/membership.html", {
            "plans": plans,
            "membership": membership,
            "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        })


class MembershipSubscribeView(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Login required"}, status=401)

        try:
            data = json.loads(request.body)
            plan = MembershipPlan.objects.get(pk=data.get("plan_id"))
        except (json.JSONDecodeError, MembershipPlan.DoesNotExist, TypeError, ValueError):
            return JsonResponse({"error": "Invalid membership plan"}, status=400)

        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        try:
            if not plan.razorpay_plan_id:
                remote_plan = client.plan.create({
                    "period": plan.billing_cycle,
                    "interval": 1,
                    "item": {
                        "name": f"Aurum Select - {plan.name}",
                        "amount": int(plan.price * 100),
                        "currency": "INR",
                        "description": (
                            f"{plan.discount_percent}% discount and "
                            f"{plan.wallet_bonus_percent}% cashback"
                        ),
                    },
                    "notes": {"membership_plan_id": str(plan.id)},
                })
                plan.razorpay_plan_id = remote_plan["id"]
                plan.save(update_fields=("razorpay_plan_id",))

            remote_subscription = client.subscription.create({
                "plan_id": plan.razorpay_plan_id,
                "total_count": 1200 if plan.billing_cycle == MembershipPlan.MONTHLY else 100,
                "quantity": 1,
                "customer_notify": True,
                "notes": {
                    "user_id": str(request.user.id),
                    "membership_plan_id": str(plan.id),
                },
            })
        except razorpay.errors.BadRequestError as exc:
            logger.exception("Unable to create Razorpay membership subscription")
            return JsonResponse({"error": str(exc)}, status=400)

        request.session["pending_membership_subscription"] = {
            "plan_id": plan.id,
            "subscription_id": remote_subscription["id"],
        }
        return JsonResponse({
            "key": settings.RAZORPAY_KEY_ID,
            "subscription_id": remote_subscription["id"],
            "name": "AURUM SELECT",
            "description": f"{plan.name} membership",
            "prefill": {
                "name": request.user.get_full_name() or request.user.username,
                "email": request.user.email,
            },
        })


class MembershipVerifyView(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Login required"}, status=401)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid payment response"}, status=400)

        pending = request.session.get("pending_membership_subscription") or {}
        subscription_id = pending.get("subscription_id")
        payment_id = data.get("razorpay_payment_id", "")
        signature = data.get("razorpay_signature", "")
        if not subscription_id or data.get("razorpay_subscription_id") != subscription_id:
            return JsonResponse({"error": "Invalid subscription session"}, status=400)

        expected_signature = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
            f"{payment_id}|{subscription_id}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_signature, signature):
            return JsonResponse({"error": "Subscription verification failed"}, status=400)

        plan = get_object_or_404(MembershipPlan, pk=pending.get("plan_id"))
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        try:
            remote_subscription = client.subscription.fetch(subscription_id)
        except razorpay.errors.BadRequestError:
            logger.exception("Unable to fetch verified Razorpay subscription")
            return JsonResponse({"error": "Unable to activate membership"}, status=400)

        current_end = remote_subscription.get("current_end")
        if current_end:
            next_billing_date = datetime.fromtimestamp(
                current_end,
                tz=datetime_timezone.utc,
            )
        else:
            days = 30 if plan.billing_cycle == MembershipPlan.MONTHLY else 365
            next_billing_date = timezone.now() + timedelta(days=days)

        existing = UserMembership.objects.filter(user=request.user).first()
        if (
            existing
            and existing.razorpay_subscription_id
            and existing.razorpay_subscription_id != subscription_id
        ):
            try:
                client.subscription.cancel(
                    existing.razorpay_subscription_id,
                    {"cancel_at_cycle_end": 0},
                )
            except Exception:
                logger.warning(
                    "Could not cancel previous subscription during upgrade",
                    exc_info=True,
                )

        UserMembership.objects.update_or_create(
            user=request.user,
            defaults={
                "plan": plan,
                "status": UserMembership.ACTIVE,
                "start_date": timezone.now(),
                "next_billing_date": next_billing_date,
                "cancelled_at": None,
                "razorpay_subscription_id": subscription_id,
            },
        )
        request.session.pop("pending_membership_subscription", None)
        return JsonResponse({"message": "Aurum Select membership activated"})


class MembershipCancelView(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("login")

        membership = get_object_or_404(UserMembership, user=request.user)
        if membership.razorpay_subscription_id:
            client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )
            try:
                client.subscription.cancel(
                    membership.razorpay_subscription_id,
                    {"cancel_at_cycle_end": 0},
                )
            except razorpay.errors.BadRequestError as exc:
                messages.error(request, f"Unable to cancel membership: {exc}")
                return redirect("membership")

        membership.status = UserMembership.CANCELLED
        membership.cancelled_at = timezone.now()
        membership.save(update_fields=("status", "cancelled_at"))
        messages.success(request, "Your Aurum Select membership has been cancelled.")
        return redirect("membership")


class MergeCartApiView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        items = request.data.get("items", {})

        if not isinstance(items, dict):
            return Response({"error": "Invalid cart data"}, status=400)

        cart, _ = Cart.objects.get_or_create(user=request.user)

        for cart_key, quantity in items.items():
            try:
                quantity = int(quantity)
            except (TypeError, ValueError):
                continue

            if quantity <= 0:
                continue

            product, stock_variant = _get_cart_product_and_variant(cart_key)

            if not product:
                continue

            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                stock_variant=stock_variant,
            )

            if created:
                cart_item.quantity = quantity
            else:
                cart_item.quantity += quantity

            cart_item.save(update_fields=("quantity",))

        return Response({"message": "Guest cart merged"})


class ProfileApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "username": request.user.username,
            "email": request.user.email,
        })


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CheckoutPageView(AnyMethodAsGetMixin, View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("login")

        for cart_key in request.session.get("cart", {}):
            product, _ = _get_cart_product_and_variant(cart_key)
            if product:
                record_product_interaction(request, product, ProductInteraction.CHECKOUT)

        saved_addresses = ShippingAddress.objects.filter(
            user=request.user
        ).order_by("-created_at")

        return render(request, "shop/checkout.html", {
            "saved_addresses": saved_addresses,
        })


class CheckoutSummaryApiView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Login required"}, status=401)

        session_cart = request.session.get("cart", {})

        items = []
        subtotal = Decimal("0")

        for cart_key, quantity in session_cart.items():
            product, stock_variant = _get_cart_product_and_variant(cart_key)

            if not product:
                continue

            unit_price = _cart_unit_price(product, stock_variant)
            item_subtotal = unit_price * quantity
            subtotal += item_subtotal

            items.append({
                "id": product.id,
                "name": product.name,
                "price": float(unit_price),
                "quantity": quantity,
                "subtotal": float(item_subtotal),
                "image": product.image.url if product.image else "",
                "size": stock_variant.size if stock_variant else "",
                "purity": stock_variant.purity if stock_variant else "",
                "sku": stock_variant.sku if stock_variant else product.sku or "",
            })

        totals = calculate_order_totals(subtotal, request.user)

        return JsonResponse({
            "items": items,
            "subtotal": totals["subtotal"],
            "membership_discount": totals["membership_discount"],
            "discount_percent": totals["discount_percent"],
            "shipping": totals["shipping"],
            "tax": totals["tax"],
            "grand_total": totals["total"],
            "membership_name": (
                totals["membership"].plan.name if totals["membership"] else ""
            ),
        })


class SaveShippingAddressJsonView(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Login required"}, status=401)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        required_fields = [
            "full_name",
            "phone",
            "address_line",
            "city",
            "state",
            "postal_code",
        ]

        for field in required_fields:
            if not str(data.get(field, "")).strip():
                return JsonResponse({
                    "error": f"{field.replace('_', ' ').title()} is required"
                }, status=400)

        _, created = ShippingAddress.objects.get_or_create(
            user=request.user,
            full_name=data.get("full_name"),
            phone=data.get("phone"),
            address_line=data.get("address_line"),
            city=data.get("city"),
            state=data.get("state"),
            postal_code=data.get("postal_code"),
            country=data.get("country") or "India",
        )

        return JsonResponse({
            "message": (
                "Shipping address saved successfully"
                if created
                else "This address is already saved"
            )
        })


class SaveShippingAddressApiView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        _, created = ShippingAddress.objects.get_or_create(
            user=request.user,
            full_name=request.data.get("full_name"),
            phone=request.data.get("phone"),
            address_line=request.data.get("address_line"),
            city=request.data.get("city"),
            state=request.data.get("state"),
            postal_code=request.data.get("postal_code"),
            country=request.data.get("country") or "India",
        )

        return Response({
            "message": (
                "Shipping address saved"
                if created
                else "This address is already saved"
            )
        })


class RecommendationsApiView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        product_id = request.query_params.get("product_id")
        anchor_product = None

        if product_id:
            anchor_product = get_object_or_404(Product, id=product_id)

        products, source, explanation = get_product_recommendations(
            anchor_product=anchor_product,
            limit=int(request.query_params.get("limit", 4)),
        )

        return Response({
            "source": source,
            "explanation": explanation,
            "products": [
                {
                    "id": product.id,
                    "name": product.name,
                    "price": product.price,
                    "category": product.primary_category.name if product.primary_category else None,
                    "image": product.image.url if product.image else None,
                    "url": reverse("product_detail", kwargs={"id": product.id}),
                }
                for product in products
            ],
        })


class SocialCompletePageView(AnyMethodAsGetMixin, TemplateView):
    template_name = "shop/auth/social_complete.html"


class GoogleLoginView(AnyMethodAsGetMixin, View):
    def get(self, request):
        state = secrets.token_urlsafe(32)
        request.session["google_oauth_state"] = state
        redirect_uri = request.build_absolute_uri(reverse("google_callback"))
        request.session["google_oauth_redirect_uri"] = redirect_uri

        query = urlencode(
            {
                "response_type": "code",
                "client_id": settings.GOOGLE_CLIENT_ID,
                "redirect_uri": redirect_uri,
                "scope": "openid email profile",
                "state": state,
                "prompt": "select_account",
            },
            quote_via=quote,
        )

        google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{query}"

        return redirect(google_auth_url)


class GoogleCallbackView(AnyMethodAsGetMixin, View):
    def get(self, request):
        error = request.GET.get("error")
        if error:
            return HttpResponseBadRequest(f"Google login failed: {error}")

        code = request.GET.get("code")
        state = request.GET.get("state")

        saved_state = request.session.get("google_oauth_state")

        if not code:
            return HttpResponseBadRequest("Missing authorization code.")

        if not state or state != saved_state:
            return HttpResponseBadRequest("Invalid OAuth state.")

        redirect_uri = request.session.get(
            "google_oauth_redirect_uri",
            settings.GOOGLE_REDIRECT_URI,
        )

        token_url = "https://oauth2.googleapis.com/token"

        token_data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        token_response = requests.post(token_url, data=token_data)

        if token_response.status_code != 200:
            return HttpResponseBadRequest("Failed to get token from Google.")

        tokens = token_response.json()
        google_id_token = tokens.get("id_token")

        if not google_id_token:
            return HttpResponseBadRequest("No ID token received from Google.")

        try:
            user_info = id_token.verify_oauth2_token(
                google_id_token,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except ValueError:
            return HttpResponseBadRequest("Invalid Google ID token.")

        google_unique_id = user_info.get("sub")
        email = user_info.get("email")
        first_name = user_info.get("given_name", "")
        last_name = user_info.get("family_name", "")

        if not google_unique_id:
            return HttpResponseBadRequest("Google unique ID not found.")

        if not email:
            return HttpResponseBadRequest("Google account has no email.")

        if not user_info.get("email_verified"):
            return HttpResponseBadRequest("Google email is not verified.")

        social_account = SocialAccount.objects.filter(
            provider="google",
            unique_id=google_unique_id
        ).first()

        if social_account:
            user = social_account.user
        else:
            user = User.objects.filter(email=email).first()

            if user is None:
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                )
                user.set_unusable_password()
                user.save()

            SocialAccount.objects.create(
                user=user,
                provider="google",
                unique_id=google_unique_id,
                extra_data=user_info
            )

        login(request, user)
        _load_database_cart_to_session(user, request.session)

        request.session.pop("google_oauth_state", None)
        request.session.pop("google_oauth_redirect_uri", None)

        return redirect("/")

class CreateOrderView(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Login required"}, status=401)

        cart = request.session.get("cart", {})

        if not cart:
            return JsonResponse({"error": "Your cart is empty"}, status=400)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid payment confirmation"}, status=400)

        razorpay_order_id = data.get("razorpay_order_id")
        razorpay_payment_id = data.get("razorpay_payment_id")
        razorpay_signature = data.get("razorpay_signature")

        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
            return JsonResponse({"error": "Payment details are missing"}, status=400)

        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

        try:
            client.utility.verify_payment_signature({
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            })
        except razorpay.errors.SignatureVerificationError:
            return JsonResponse({"error": "Payment verification failed"}, status=400)

        with transaction.atomic():
            payment = Payment.objects.select_for_update().filter(
                razorpay_order_id=razorpay_order_id,
                user=request.user,
            ).first()

            if not payment:
                return JsonResponse({"error": "Payment record not found"}, status=400)

            subtotal = Decimal("0")
            order_items_data = []

            for cart_key, quantity in cart.items():
                product, stock_variant = _get_cart_product_and_variant(cart_key, lock=True)

                if not product:
                    continue

                quantity = int(quantity)

                available_stock = stock_variant.stock_quantity if stock_variant else product.stock
                if available_stock < quantity:
                    return JsonResponse({
                        "error": f"{product.name} is out of stock or only {available_stock} left."
                    }, status=400)

                unit_price = _cart_unit_price(product, stock_variant)
                item_total = unit_price * quantity
                subtotal += item_total

                order_items_data.append({
                    "product_id": product.id,
                    "stock_variant_id": stock_variant.id if stock_variant else None,
                    "product_name": product.name,
                    "product_price": unit_price,
                    "product_image": product.image,
                    "variant_size": (stock_variant.size or "") if stock_variant else "",
                    "variant_purity": (stock_variant.purity or "") if stock_variant else "",
                    "variant_sku": stock_variant.sku if stock_variant else (product.sku or ""),
                    "quantity": quantity,
                    "item_total": item_total,
                })

            totals = calculate_order_totals(subtotal, request.user)

            order = Order.objects.create(
                user=request.user,
                subtotal=totals["subtotal"],
                membership_discount=totals["membership_discount"],
                shipping=totals["shipping"],
                tax=totals["tax"],
                total=totals["total"],
                status="paid",
            )

            payment.order = order
            payment.razorpay_payment_id = razorpay_payment_id
            payment.razorpay_signature = razorpay_signature
            payment.status = "paid"
            payment.save(update_fields=[
                "order",
                "razorpay_payment_id",
                "razorpay_signature",
                "status",
            ])

            for item in order_items_data:
                product_id = item.pop("product_id")
                stock_variant_id = item.pop("stock_variant_id")

                OrderItem.objects.create(
                    order=order,
                    stock_variant_id=stock_variant_id,
                    **item
                )

                if stock_variant_id:
                    ProductStockVariant.objects.filter(id=stock_variant_id).update(
                        stock_quantity=F("stock_quantity") - item["quantity"]
                    )
                else:
                    Product.objects.filter(id=product_id).update(
                        stock=F("stock") - item["quantity"]
                    )

            membership = totals["membership"]
            if membership and membership.plan.wallet_bonus_percent > 0:
                bonus = (
                    totals["total"]
                    * membership.plan.wallet_bonus_percent
                    / Decimal("100")
                ).quantize(Decimal("0.01"))
                if bonus > 0:
                    credit_wallet(
                        request.user,
                        bonus,
                        related_order=order,
                        transaction_type=WalletTransaction.MEMBERSHIP_BONUS,
                        notes=f"Aurum Select cashback for order #{order.id}",
                    )

        request.session["cart"] = {}
        request.session.modified = True

        send_order_confirmation_email.delay(order.id)

        return JsonResponse({
            "message": "Order confirmed",
            "redirect_url": reverse("order_confirmation", args=[order.id])
        })

class OrderConfirmationView(View):
    def get(self, request, order_id):
        if not request.user.is_authenticated:
            return redirect("login")

        order = get_object_or_404(
            Order.objects.prefetch_related("items"),
            id=order_id,
            user=request.user
        )

        return render(request, "shop/order_confirmation.html", {
            "order": order
        })

class OrderHistoryView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("login")

        orders = (
            Order.objects.filter(user=request.user)
            .select_related("payment")
            .prefetch_related("items", "payment__refunds")
            .order_by("-created_at")
        )

        for order in orders:
            payment = getattr(order, "payment", None)
            order.payment_record = payment
            if payment:
                payment.amount_rupees = Decimal(payment.amount) / Decimal("100")
                payment.refunded_amount_rupees = Decimal(payment.refunded_amount) / Decimal("100")
                payment.remaining_refund_amount = payment.amount - payment.refunded_amount
                payment.remaining_refund_rupees = (
                    Decimal(payment.remaining_refund_amount) / Decimal("100")
                )
                payment.refund_rows = [
                    {
                        "id": refund.razorpay_refund_id,
                        "amount_rupees": Decimal(refund.amount) / Decimal("100"),
                        "status": refund.status,
                    }
                    for refund in payment.refunds.all()
                ]
                payment.can_refund = (
                    payment.status in ["paid", "partially_refunded"]
                    and payment.remaining_refund_amount > 0
                    and bool(payment.razorpay_payment_id)
                )
                payment.item_refund_totals = {}
                for item_refund in payment.refunds.filter(order_item_id__isnull=False):
                    payment.item_refund_totals[item_refund.order_item_id] = (
                        payment.item_refund_totals.get(item_refund.order_item_id, 0)
                        + item_refund.amount
                    )

                for item in order.items.all():
                    item.refundable_amount = int(item.item_total * Decimal("100"))
                    item.refunded_amount = payment.item_refund_totals.get(item.id, 0)
                    item.requested_refund_quantity = _refund_request_quantities(order).get(item.id, 0)
                    item.remaining_refund_amount = max(
                        item.refundable_amount - item.refunded_amount,
                        0,
                    )
                    item.remaining_refund_quantity = max(
                        item.quantity - item.requested_refund_quantity,
                        0,
                    )
                    item.remaining_refund_rupees = (
                        Decimal(item.remaining_refund_amount) / Decimal("100")
                    )
                    item.can_refund = (
                        payment.can_refund
                        and item.remaining_refund_amount > 0
                        and item.remaining_refund_quantity > 0
                        and _is_return_window_open(order)
                    )

        return render(request, "shop/order_history.html", {
            "orders": orders,
        })


def _return_window_anchor(order):
    return getattr(order, "delivered_at", None) or order.created_at


def _return_window_deadline(order):
    return _return_window_anchor(order) + timedelta(days=RETURN_WINDOW_DAYS)


def _is_return_window_open(order):
    return _return_window_deadline(order) >= timezone.now()


def _refund_request_quantities(order):
    rows = (
        RefundItem.objects
        .filter(refund_request__order=order)
        .exclude(refund_request__status=RefundRequest.REJECTED)
        .values("order_item_id")
        .annotate(total=Sum("quantity_returned"))
    )
    return {row["order_item_id"]: row["total"] for row in rows}


def _legacy_refund_amounts(order):
    rows = (
        Refund.objects
        .filter(payment__order=order, order_item_id__isnull=False)
        .values("order_item_id")
        .annotate(total=Sum("amount"))
    )
    return {row["order_item_id"]: row["total"] for row in rows}


def _annotate_refund_eligibility(order):
    requested_quantities = _refund_request_quantities(order)
    legacy_refund_amounts = _legacy_refund_amounts(order)
    return_window_open = _is_return_window_open(order)

    for item in order.items.all():
        legacy_refunded_amount = legacy_refund_amounts.get(item.id, 0)
        legacy_refunded_quantity = item.quantity if legacy_refunded_amount >= int(item.item_total * Decimal("100")) else 0
        blocked_quantity = requested_quantities.get(item.id, 0) + legacy_refunded_quantity
        item.remaining_refund_quantity = max(item.quantity - blocked_quantity, 0)
        item.return_window_open = return_window_open
        item.can_request_refund = item.remaining_refund_quantity > 0 and return_window_open
        item.estimated_tax = Decimal("0")
        if order.subtotal:
            item.estimated_tax = (order.tax * item.item_total / order.subtotal).quantize(Decimal("0.01"))

    return order


def _selected_refund_items(order, post_data):
    selected_items = []

    for item in order.items.all():
        quantity_key = f"quantity_{item.id}"
        if str(item.id) not in post_data.getlist("items"):
            continue

        try:
            quantity = int(post_data.get(quantity_key, "0"))
        except (TypeError, ValueError):
            quantity = 0

        if quantity <= 0:
            raise ValueError(f"Enter a valid quantity for {item.product_name}.")

        if quantity > item.remaining_refund_quantity:
            raise ValueError(f"{item.product_name} has only {item.remaining_refund_quantity} refundable item(s).")

        selected_items.append({
            "item": item,
            "quantity": quantity,
            "condition_notes": post_data.get(f"condition_{item.id}", "").strip(),
        })

    if not selected_items:
        raise ValueError("Select at least one item to refund.")

    return selected_items


def _calculate_refund_amount(order, selected_items, reason):
    subtotal = sum(
        selected["item"].product_price * selected["quantity"]
        for selected in selected_items
    )
    tax = Decimal("0")
    if order.subtotal:
        tax = (order.tax * subtotal / order.subtotal).quantize(Decimal("0.01"))

    shipping_refunded = reason in [
        RefundRequest.DEFECTIVE,
        RefundRequest.WRONG_ITEM,
        RefundRequest.QUALITY_ISSUE,
    ]
    shipping = order.shipping if shipping_refunded else Decimal("0")

    return {
        "subtotal": subtotal,
        "tax": tax,
        "shipping": shipping,
        "shipping_refunded": shipping_refunded,
        "total": subtotal + tax + shipping,
    }


class RefundRequestView(View):
    template_name = "shop/refund_request.html"

    def get_order(self, request, order_id):
        return get_object_or_404(
            Order.objects.prefetch_related("items", "refund_requests__items"),
            id=order_id,
            user=request.user,
        )

    def get(self, request, order_id):
        if not request.user.is_authenticated:
            return redirect("login")

        order = _annotate_refund_eligibility(self.get_order(request, order_id))
        form = RefundRequestForm(order=order)
        selected_item_id = request.GET.get("item", "")

        if not _is_return_window_open(order):
            messages.error(request, f"This order is outside the {RETURN_WINDOW_DAYS}-day return window.")

        return render(request, self.template_name, {
            "order": order,
            "form": form,
            "selected_item_id": selected_item_id,
            "return_deadline": _return_window_deadline(order),
            "return_window_days": RETURN_WINDOW_DAYS,
        })

    def post(self, request, order_id):
        if not request.user.is_authenticated:
            return redirect("login")

        order = _annotate_refund_eligibility(self.get_order(request, order_id))
        form = RefundRequestForm(request.POST, request.FILES, order=order)

        if not _is_return_window_open(order):
            messages.error(request, f"This order is outside the {RETURN_WINDOW_DAYS}-day return window.")
            return redirect("refund_request", order_id=order.id)

        try:
            selected_items = _selected_refund_items(order, request.POST)
        except ValueError as error:
            messages.error(request, str(error))
            return render(request, self.template_name, {
                "order": order,
                "form": form,
                "selected_item_id": "",
                "return_deadline": _return_window_deadline(order),
                "return_window_days": RETURN_WINDOW_DAYS,
            })

        if not form.is_valid():
            messages.error(request, "Please correct the refund request details.")
            return render(request, self.template_name, {
                "order": order,
                "form": form,
                "selected_item_id": "",
                "return_deadline": _return_window_deadline(order),
                "return_window_days": RETURN_WINDOW_DAYS,
            })

        totals = _calculate_refund_amount(order, selected_items, form.cleaned_data["reason"])

        with transaction.atomic():
            refund_request = form.save(commit=False)
            refund_request.order = order
            refund_request.user = request.user
            refund_request.status = RefundRequest.PENDING_REVIEW
            refund_request.refund_amount = totals["total"]
            refund_request.shipping_refunded = totals["shipping_refunded"]
            refund_request.save()

            for selected in selected_items:
                RefundItem.objects.create(
                    refund_request=refund_request,
                    order_item=selected["item"],
                    quantity_returned=selected["quantity"],
                    item_condition_notes=selected["condition_notes"],
                )

            for image in request.FILES.getlist("images"):
                RefundImage.objects.create(
                    refund_request=refund_request,
                    image=image,
                )

        messages.success(request, "Refund request submitted. You can track the status here.")
        return redirect("refund_status", refund_request_id=refund_request.id)


class RefundStatusView(View):
    template_name = "shop/refund_status.html"

    def get(self, request, refund_request_id):
        if not request.user.is_authenticated:
            return redirect("login")

        refund_request = get_object_or_404(
            RefundRequest.objects
            .select_related("order", "user")
            .prefetch_related("items__order_item", "images"),
            id=refund_request_id,
            user=request.user,
        )
        steps = [
            (RefundRequest.APPROVED, "Approved"),
            (RefundRequest.PICKED_UP, "Picked Up"),
            (RefundRequest.QC_PASSED, "QC"),
            (RefundRequest.REFUNDED, "Refunded"),
        ]
        step_index = {status: index for index, (status, label) in enumerate(steps)}
        current_index = step_index.get(refund_request.status, 0)
        display_steps = [
            {
                "label": label,
                "is_complete": refund_request.status not in [
                    RefundRequest.PENDING_REVIEW,
                    RefundRequest.REJECTED,
                    RefundRequest.QC_FAILED,
                ] and index <= current_index,
                "is_current": index == current_index,
            }
            for index, (status, label) in enumerate(steps)
        ]

        return render(request, self.template_name, {
            "refund_request": refund_request,
            "steps": display_steps,
            "is_pending": refund_request.status == RefundRequest.PENDING_REVIEW,
            "is_rejected": refund_request.status == RefundRequest.REJECTED,
            "is_qc_failed": refund_request.status == RefundRequest.QC_FAILED,
            "is_approved_or_later": refund_request.status in [
                RefundRequest.APPROVED,
                RefundRequest.PICKED_UP,
                RefundRequest.QC_PASSED,
                RefundRequest.REFUNDED,
            ],
        })

class CreateRazorpayOrderView(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Login required"}, status=401)

        cart = request.session.get("cart", {})

        if not cart:
            return JsonResponse({"error": "Your cart is empty"}, status=400)

        subtotal = Decimal("0")

        for cart_key, quantity in cart.items():
            product, stock_variant = _get_cart_product_and_variant(cart_key)

            if product:
                quantity = int(quantity)

                available_stock = stock_variant.stock_quantity if stock_variant else product.stock
                if available_stock < quantity:
                    return JsonResponse({
                        "error": f"{product.name} is out of stock or only {available_stock} left."
                    }, status=400)

                subtotal += _cart_unit_price(product, stock_variant) * quantity

        totals = calculate_order_totals(subtotal, request.user)

        amount_in_paise = int(totals["total"] * 100)

        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

        razorpay_order = client.order.create({
            "amount": amount_in_paise,
            "currency": "INR",
            "payment_capture": 1,
        })

        from .models import Payment

        Payment.objects.create(
            user=request.user,
            razorpay_order_id=razorpay_order["id"],
            amount=amount_in_paise,
            currency="INR",
            status="created",
        )

        return JsonResponse({
            "key": settings.RAZORPAY_KEY_ID,
            "amount": amount_in_paise,
            "currency": "INR",
            "razorpay_order_id": razorpay_order["id"],
            "name": "AURUM",
            "description": "Luxury jewellery order",
        })

def _create_razorpay_refund(payment, refund_amount, reason, speed, order_item=None):
    receipt = f"refund_{payment.id}_{get_random_string(8)}"
    notes = {
        "payment_id": str(payment.id),
        "reason": reason[:250],
    }

    if order_item:
        notes["order_item_id"] = str(order_item.id)

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )

    refund_response = client.payment.refund(
        payment.razorpay_payment_id,
        {
            "amount": refund_amount,
            "speed": speed,
            "receipt": receipt,
            "notes": notes,
        }
    )

    Refund.objects.create(
        payment=payment,
        order_item=order_item,
        razorpay_refund_id=refund_response["id"],
        amount=refund_response["amount"],
        status=refund_response["status"],
        speed_requested=refund_response.get("speed_requested", ""),
        speed_processed=refund_response.get("speed_processed", ""),
        receipt=refund_response.get("receipt", receipt),
        reason=reason,
        raw_response=refund_response,
    )

    payment.refunded_amount += refund_response["amount"]

    if payment.refunded_amount >= payment.amount:
        payment.status = "refunded"
        if payment.order:
            payment.order.status = "cancelled"
            payment.order.save(update_fields=["status"])
    else:
        payment.status = "partially_refunded"

    payment.save(update_fields=["refunded_amount", "status"])
    return refund_response


@require_POST
def request_order_refund(request, order_id):
    return JsonResponse(
        {"error": "Full-order refunds are not available. Request a refund for each item instead."},
        status=400,
    )


@require_POST
def request_order_item_refund(request, order_id, item_id):
    return JsonResponse(
        {"error": "Direct refunds are not available. Submit a refund request for this item instead."},
        status=400,
    )

    if not request.user.is_authenticated:
        return JsonResponse({"error": "Login required"}, status=401)

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    amount = data.get("amount")
    reason = str(data.get("reason", "")).strip()
    speed = data.get("speed", "normal")

    if speed not in ["normal", "optimum"]:
        return JsonResponse({"error": "Invalid refund speed"}, status=400)

    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update(),
            id=order_id,
            user=request.user,
        )
        order_item = get_object_or_404(
            OrderItem.objects.select_for_update(),
            id=item_id,
            order=order,
        )

        payment = Payment.objects.select_for_update().filter(order=order).first()

        if not payment:
            return JsonResponse({"error": "Payment record not found"}, status=400)

        if payment.status not in ["paid", "partially_refunded"]:
            return JsonResponse({"error": "This order is not eligible for refund"}, status=400)

        if not payment.razorpay_payment_id:
            return JsonResponse({"error": "Missing Razorpay payment id"}, status=400)

        remaining_amount = payment.amount - payment.refunded_amount
        item_refund_total = (
            Refund.objects.filter(payment=payment, order_item=order_item)
            .aggregate(total=Sum("amount"))["total"]
            or 0
        )
        item_remaining_amount = int(order_item.item_total * Decimal("100")) - item_refund_total

        if amount in [None, ""]:
            refund_amount = item_remaining_amount
        else:
            try:
                refund_amount = int(amount)
            except (TypeError, ValueError):
                return JsonResponse({"error": "Invalid refund amount"}, status=400)

        if refund_amount <= 0:
            return JsonResponse({"error": "Refund amount must be greater than 0"}, status=400)

        if refund_amount > remaining_amount:
            return JsonResponse({"error": "Refund amount exceeds remaining refundable amount"}, status=400)

        if refund_amount > item_remaining_amount:
            return JsonResponse({"error": "Refund amount exceeds this item's refundable amount"}, status=400)

        try:
            refund_response = _create_razorpay_refund(
                payment=payment,
                refund_amount=refund_amount,
                reason=reason or f"Customer refund request for {order_item.product_name}",
                speed=speed,
                order_item=order_item,
            )
        except razorpay.errors.BadRequestError as error:
            return JsonResponse({"error": str(error)}, status=400)

    return JsonResponse({
        "message": "Refund request created",
        "refund_id": refund_response["id"],
        "status": refund_response["status"],
        "amount": refund_response["amount"],
    })

@staff_member_required
@require_POST
def refund_payment(request, payment_id):
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    amount = data.get("amount")
    reason = data.get("reason", "")
    speed = data.get("speed", "normal")

    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(id=payment_id)

        if payment.status not in ["paid", "partially_refunded"]:
            return JsonResponse({"error": "Only paid payments can be refunded"}, status=400)

        if not payment.razorpay_payment_id:
            return JsonResponse({"error": "Missing Razorpay payment id"}, status=400)

        remaining_amount = payment.amount - payment.refunded_amount

        if amount is None:
            refund_amount = remaining_amount
        else:
            refund_amount = int(amount)

        if refund_amount <= 0:
            return JsonResponse({"error": "Refund amount must be greater than 0"}, status=400)

        if refund_amount > remaining_amount:
            return JsonResponse({"error": "Refund amount exceeds remaining refundable amount"}, status=400)

        refund_response = _create_razorpay_refund(
            payment=payment,
            refund_amount=refund_amount,
            reason=reason,
            speed=speed,
        )

    return JsonResponse({
        "message": "Refund created",
        "refund_id": refund_response["id"],
        "status": refund_response["status"],
        "amount": refund_response["amount"],
    })


@csrf_exempt
@require_POST
def razorpay_webhook_view(request):
    signature = request.headers.get("X-Razorpay-Signature", "")

    if not getattr(settings, "RAZORPAY_WEBHOOK_SECRET", ""):
        logger.error("RAZORPAY_WEBHOOK_SECRET is not configured")
        return JsonResponse({"error": "Webhook secret is not configured"}, status=500)

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )

    try:
        client.utility.verify_webhook_signature(
            request.body,
            signature,
            settings.RAZORPAY_WEBHOOK_SECRET,
        )
    except Exception:
        logger.exception("Invalid Razorpay webhook signature")
        return JsonResponse({"error": "Invalid signature"}, status=400)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    event = payload.get("event")
    subscription_entity = (
        payload.get("payload", {}).get("subscription", {}).get("entity", {})
    )
    subscription_id = subscription_entity.get("id")

    if event and event.startswith("subscription.") and subscription_id:
        membership = UserMembership.objects.filter(
            razorpay_subscription_id=subscription_id
        ).first()
        if not membership:
            logger.info(
                "Razorpay subscription id %s did not match a UserMembership",
                subscription_id,
            )
            return JsonResponse({"ok": True})

        update_fields = []
        active_events = {
            "subscription.authenticated",
            "subscription.activated",
            "subscription.charged",
            "subscription.resumed",
        }
        expired_events = {
            "subscription.pending",
            "subscription.halted",
            "subscription.completed",
            "subscription.expired",
        }

        if event in active_events:
            membership.status = UserMembership.ACTIVE
            membership.cancelled_at = None
            update_fields.extend(("status", "cancelled_at"))
            current_end = subscription_entity.get("current_end")
            if current_end:
                membership.next_billing_date = datetime.fromtimestamp(
                    current_end,
                    tz=datetime_timezone.utc,
                )
                update_fields.append("next_billing_date")
        elif event == "subscription.cancelled":
            membership.status = UserMembership.CANCELLED
            membership.cancelled_at = timezone.now()
            update_fields.extend(("status", "cancelled_at"))
        elif event in expired_events:
            membership.status = UserMembership.EXPIRED
            update_fields.append("status")

        if update_fields:
            membership.save(update_fields=tuple(dict.fromkeys(update_fields)))
        return JsonResponse({"ok": True})

    refund_entity = payload.get("payload", {}).get("refund", {}).get("entity", {})
    refund_id = refund_entity.get("id")

    if not refund_id:
        return JsonResponse({"ok": True})

    refund_request = RefundRequest.objects.filter(
        razorpay_refund_id=refund_id,
    ).first()

    if not refund_request:
        logger.info("Razorpay webhook refund id %s did not match a RefundRequest", refund_id)
        return JsonResponse({"ok": True})

    if event == "refund.processed":
        refund_request.status = RefundRequest.REFUNDED
        refund_request.razorpay_refund_status = refund_entity.get("status", "processed")
        refund_request.refund_completed_at = timezone.now()
        refund_request.save(update_fields=[
            "status",
            "razorpay_refund_status",
            "refund_completed_at",
            "updated_at",
        ])
    elif event == "refund.failed":
        failure_reason = (
            refund_entity.get("error_description")
            or refund_entity.get("error_reason")
            or "Razorpay refund failed"
        )
        refund_request.status = RefundRequest.REFUND_FAILED
        refund_request.razorpay_refund_status = refund_entity.get("status", "failed")
        refund_request.staff_notes = failure_reason
        refund_request.save(update_fields=[
            "status",
            "razorpay_refund_status",
            "staff_notes",
            "updated_at",
        ])

    return JsonResponse({"ok": True})


@require_POST
def start_guest_support_chat(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    guest_name = str(data.get("name", "")).strip() or "Guest visitor"
    guest_email = str(data.get("email", "")).strip()

    if not request.session.session_key:
        request.session.create()

    session_key = request.session.session_key
    uid = f"guest_{session_key}"
    channel_name = f"support_guest_{session_key}"

    conversation, _ = ChatConversation.objects.get_or_create(
        guest_session_key=session_key,
        defaults={
            "guest_name": guest_name,
            "guest_email": guest_email,
            "channel_name": channel_name,
        },
    )

    if guest_name != conversation.guest_name or guest_email != conversation.guest_email:
        conversation.guest_name = guest_name
        conversation.guest_email = guest_email
        conversation.save(update_fields=["guest_name", "guest_email", "updated_at"])

    expire_seconds = 60 * 60
    privilege_expire_ts = int(time.time()) + expire_seconds

    token = RtmTokenBuilder.buildToken(
        settings.AGORA_APP_ID,
        settings.AGORA_APP_CERTIFICATE,
        uid,
        1,
        privilege_expire_ts,
    )

    return JsonResponse({
        "app_id": settings.AGORA_APP_ID,
        "token": token,
        "uid": uid,
        "channel_name": conversation.channel_name,
        "username": guest_name,
        "is_staff": False,
        "is_guest": True,
    })

@require_GET
def agora_support_token(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Login required"}, status=401)

    uid = f"user_{request.user.id}"
    channel_name = f"support_user_{request.user.id}"

    conversation, _ = ChatConversation.objects.get_or_create(
        user=request.user,
        defaults={"channel_name": channel_name},
    )

    expire_seconds = 60 * 60
    privilege_expire_ts = int(time.time()) + expire_seconds

    token = RtmTokenBuilder.buildToken(
        settings.AGORA_APP_ID,
        settings.AGORA_APP_CERTIFICATE,
        uid,
        1,
        privilege_expire_ts,
    )

    return JsonResponse({
        "app_id": settings.AGORA_APP_ID,
        "token": token,
        "uid": uid,
        "channel_name": conversation.channel_name,
        "username": request.user.username,
        "is_staff": request.user.is_staff,
    })


def support_chat_history(request):
    channel_name = request.GET.get("channel")

    if request.user.is_authenticated and request.user.is_staff and channel_name:
        conversation = get_object_or_404(ChatConversation, channel_name=channel_name)
    elif request.user.is_authenticated:
        conversation = get_object_or_404(ChatConversation, user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            return JsonResponse({"messages": []})
        conversation = ChatConversation.objects.filter(
            guest_session_key=session_key
        ).first()
        if not conversation:
            return JsonResponse({"messages": []})

    messages = conversation.messages.select_related("sender").order_by("created_at")

    return JsonResponse({
        "messages": [
            {
                "body": message.body,
                "sender": (
                    "AURUM Assistant"
                    if message.is_ai_message
                    else
                    message.sender.username
                    if message.sender
                    else "AURUM Support"
                    if message.is_staff_message
                    else conversation.guest_name or "Guest"
                ),
                "is_staff": message.is_staff_message,
                "is_ai": message.is_ai_message,
                "created_at": timezone.localtime(message.created_at).strftime("%I:%M %p")
            }
            for message in messages
        ]
    })

@require_POST
def save_support_chat_message(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    body = str(data.get("body", "")).strip()
    channel_name = str(data.get("channel", "")).strip()

    if not body:
        return JsonResponse({"error": "Message is required"}, status=400)

    if len(body) > 1000:
        return JsonResponse({"error": "Message is too long"}, status=400)

    if request.user.is_authenticated and request.user.is_staff and channel_name:
        conversation = get_object_or_404(ChatConversation, channel_name=channel_name)
        sender = request.user
        is_staff_message = True
        conversation.unread_by_user += 1
    elif request.user.is_authenticated:
        conversation, _ = ChatConversation.objects.get_or_create(
            user=request.user,
            defaults={"channel_name": f"support_user_{request.user.id}"},
        )
        sender = request.user
        is_staff_message = False
        conversation.unread_by_staff += 1
    else:
        session_key = request.session.session_key
        if not session_key:
            return JsonResponse({"error": "Start guest chat first"}, status=400)

        conversation = ChatConversation.objects.filter(
            guest_session_key=session_key,
        ).first()

        if not conversation:
            return JsonResponse({"error": "Start guest chat first"}, status=400)

        sender = None
        is_staff_message = False
        conversation.unread_by_staff += 1

    message = ChatMessage.objects.create(
        conversation=conversation,
        sender=sender,
        body=body,
        is_staff_message=is_staff_message,
        is_ai_message=False,
    )

    conversation.last_message_preview = body[:160]
    conversation.last_message_at = message.created_at
    conversation.status = ChatConversation.OPEN
    conversation.closed_at = None
    conversation.save()

    return JsonResponse({
        "id": message.id,
        "body": message.body,
        "sender": (
            request.user.username
            if request.user.is_authenticated
            else conversation.guest_name or "Guest"
        ),
        "is_staff": message.is_staff_message,
        "is_ai": message.is_ai_message,
        "created_at": timezone.localtime(message.created_at).strftime("%I:%M %p")
    })


@require_POST
def support_ai_reply(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    body = str(data.get("body", "")).strip()
    if not body:
        return JsonResponse({"error": "Message is required"}, status=400)

    if request.user.is_authenticated and request.user.is_staff:
        return JsonResponse({"error": "AI replies are for customer chats only"}, status=400)

    if request.user.is_authenticated:
        conversation = get_object_or_404(ChatConversation, user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            return JsonResponse({"error": "No guest session"}, status=400)

        conversation = ChatConversation.objects.filter(
            guest_session_key=session_key,
        ).first()

        if not conversation:
            return JsonResponse({"error": "No guest conversation"}, status=400)

    try:
        reply = generate_support_reply(
            body,
            user=request.user if request.user.is_authenticated else None,
            conversation=conversation,
        )
    except Exception as exc:
        return JsonResponse({
            "error": "AI support is unavailable",
            "detail": str(exc),
        }, status=502)

    message = ChatMessage.objects.create(
        conversation=conversation,
        sender=None,
        body=reply,
        is_staff_message=True,
        is_ai_message=True,
    )

    conversation.last_message_preview = reply[:160]
    conversation.last_message_at = message.created_at
    conversation.unread_by_user += 1
    conversation.save()

    return JsonResponse({
        "id": message.id,
        "body": message.body,
        "sender": "AURUM Assistant",
        "sender_id": "aurum_ai",
        "is_staff": True,
        "is_ai": True,
        "created_at": timezone.localtime(message.created_at).strftime("%I:%M %p"),
    })


def support_chat_dashboard(request):
    if not request.user.is_authenticated:
        return redirect("login")

    if not request.user.is_staff:
        return redirect("home")

    conversations = (
        ChatConversation.objects
        .select_related("user")
        .prefetch_related("messages")
        .order_by("-updated_at")
    )

    return render(request, "shop/support_chat.html", {
        "conversations": conversations,
    })

home = HomeView.as_view()
product_detail = ProductDetailView.as_view()
product_variant_stock_api = ProductVariantStockApiView.as_view()
search_view = SearchView.as_view()
category_browse = CategoryBrowseView.as_view()
product_detail_api = ProductDetailApiView.as_view()
login_view = LoginView.as_view()
dashboard_view = DashboardView.as_view()
logout_view = LogoutView.as_view()
signup_page = SignupPageView.as_view()
verify_signup_page = VerifySignupPageView.as_view()
forgot_password_page = ForgotPasswordPageView.as_view()
password_reset_start_api = PasswordResetStartApiView.as_view()
password_reset_verify_api = PasswordResetVerifyApiView.as_view()
password_reset_complete_api = PasswordResetCompleteApiView.as_view()
cart_page = CartPageView.as_view()
signup_start_api = SignupStartApiView.as_view()
signup_verify_api = SignupVerifyApiView.as_view()
signup_resend_api = SignupResendApiView.as_view()
# Keep the existing URL import valid until urls.py is switched to the OTP routes.
signup_api = signup_start_api
session_cart_count = SessionCartCountView.as_view()
add_to_session_cart = AddToSessionCartView.as_view()
decrease_session_cart = DecreaseSessionCartView.as_view()
remove_from_session_cart = RemoveFromSessionCartView.as_view()
update_cart_item_api = UpdateCartItemApiView.as_view()
remove_from_cart_api = RemoveFromCartApiView.as_view()
profile_page = ProfilePageView.as_view()
merge_cart_api = MergeCartApiView.as_view()
profile_api = ProfileApiView.as_view()
wallet_balance = WalletBalanceView.as_view()
wallet_topup = WalletTopUpView.as_view()
wallet_topup_verify = WalletTopUpVerifyView.as_view()
membership = MembershipPageView.as_view()
membership_subscribe = MembershipSubscribeView.as_view()
membership_verify = MembershipVerifyView.as_view()
membership_cancel = MembershipCancelView.as_view()
checkout_page = CheckoutPageView.as_view()
checkout_summary_api = CheckoutSummaryApiView.as_view()
save_shipping_address_json = SaveShippingAddressJsonView.as_view()
save_shipping_address_api = SaveShippingAddressApiView.as_view()
recommendations_api = RecommendationsApiView.as_view()
social_complete_page = SocialCompletePageView.as_view()
google_login = GoogleLoginView.as_view()
google_callback = GoogleCallbackView.as_view()                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            
create_order = CreateOrderView.as_view()
order_confirmation = OrderConfirmationView.as_view()
order_history = OrderHistoryView.as_view()
refund_request = RefundRequestView.as_view()
refund_status = RefundStatusView.as_view()
create_razorpay_order = CreateRazorpayOrderView.as_view()
