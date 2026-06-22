import secrets
import time
import uuid
import json
import jwt

from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

import secrets
import requests

from django.conf import settings
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
from django.db.models import Avg, Count
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Cart, CartItem, Category, Product, ShippingAddress


SIGNUP_CACHE_PREFIX = "pending_signup:"
SIGNUP_OTP_TTL_SECONDS = 5 * 60
SIGNUP_RESEND_COOLDOWN_SECONDS = 60
SIGNUP_MAX_ATTEMPTS = 5
PASSWORD_RESET_CACHE_PREFIX = "password_reset:"
PASSWORD_RESET_OTP_TTL_SECONDS = 5 * 60
PASSWORD_RESET_MAX_ATTEMPTS = 5


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

    for product_id, quantity in session_cart.items():
        try:
            product_id = int(product_id)
            quantity = int(quantity)
        except (TypeError, ValueError):
            continue

        if quantity <= 0:
            continue

        product = Product.objects.filter(id=product_id).first()

        if not product:
            continue

        CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=quantity,
        )


def _load_database_cart_to_session(user, session):
    cart = Cart.objects.filter(user=user).first()

    if not cart:
        return

    session_cart = session.get("cart", {}).copy()

    for item in cart.items.select_related("product"):
        product_id = str(item.product_id)
        session_cart[product_id] = session_cart.get(product_id, 0) + item.quantity

    session["cart"] = session_cart
    if hasattr(session, "modified"):
        session.modified = True


@ensure_csrf_cookie
def home(request):
    print("USER:", request.user)
    print("AUTH:", request.user.is_authenticated)

    products = Product.objects.all()
    categories = Category.objects.filter(is_active=True).annotate(
        product_count=Count("products")
    )
    return render(
        request,
        "shop/products/e-commerce.html",
        {"products": products, "categories": categories}
    )

def product_detail(request, id):
    product = get_object_or_404(Product, id=id)

    reviews = product.reviews.all().order_by("-created_at")

    avg_rating = product.reviews.aggregate(Avg("rating"))["rating__avg"] or 0

    review_count = product.reviews.count()

    return render(request, "shop/products/product_detail.html", {
        "product": product,
        "reviews": reviews,
        "avg_rating": avg_rating,
        "review_count": review_count,
    })

def search_view(request):
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
            category_id=selected_category
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

def product_detail_api(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    data = {
        'id': product.id,
        'name': product.name,
        'price': str(product.price),
        'category': product.category.name if product.category else None,
        'image': product.image.url if product.image else None,
    }
    return JsonResponse(data)

def login_view(request):
    if request.method == "POST":
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

    return render(request, "shop/auth/login.html")
    
def dashboard_view(request):    
    if not request.user.is_authenticated:        
        return redirect('login')    
    return render(request, 'shop/auth/profile.html', {'username': request.user.username})

def logout_view(request):
    if request.user.is_authenticated:
        _merge_session_cart_to_database(request.user, request.session)

    response = redirect("home")

    logout(request)

    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    response.delete_cookie("sessionid", path="/")

    return response

def signup_page(request):
    return render(request, "shop/auth/signup.html")


def verify_signup_page(request):
    return render(request, "shop/auth/verify_signup.html")


def forgot_password_page(request):
    return render(request, "shop/auth/forgot_password.html")


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_start_api(request):
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


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_verify_api(request):
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


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_complete_api(request):
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

def cart_page(request):
    if not request.user.is_authenticated:
        return redirect("login")

    session_cart = request.session.get("cart", {})

    cart_items = []
    total = 0

    for product_id, quantity in session_cart.items():
        product = Product.objects.filter(id=product_id).first()

        if not product:
            continue

        subtotal = product.price * quantity
        total += subtotal

        cart_items.append({
            "product": product,
            "quantity": quantity,
            "subtotal": subtotal,
        })

    subtotal = total

    if subtotal == 0:
        shipping = 0
        tax = 0
    elif subtotal >= 250:
        shipping = 0
        tax = subtotal * 0.08
    else:
        shipping = subtotal * 0.05

        if shipping < 8:
            shipping = 8

        if shipping > 35:
            shipping = 35

        tax = subtotal * 0.08

    grand_total = subtotal + shipping + tax

    return render(request, "shop/cart/cart.html", {
        "cart_items": cart_items,
        "subtotal": round(subtotal, 2),
        "shipping": round(shipping, 2),
        "tax": round(tax, 2),
        "grand_total": round(grand_total, 2),
    })

@api_view(["POST"])
@permission_classes([AllowAny])
def signup_start_api(request):
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

@api_view(["POST"])
@permission_classes([AllowAny])
def signup_verify_api(request):
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


@api_view(["POST"])
@permission_classes([AllowAny])
def signup_resend_api(request):
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


# Keep the existing URL import valid until urls.py is switched to the OTP routes.
signup_api = signup_start_api


def session_cart_count(request):
    cart = request.session.get("cart", {})

    return JsonResponse({
        "count": sum(cart.values())
    })


@require_POST
def add_to_session_cart(request, product_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Login required"}, status=401)

    product = get_object_or_404(Product, id=product_id)

    cart = request.session.get("cart", {})

    product_id = str(product.id)

    cart[product_id] = cart.get(product_id, 0) + 1

    request.session["cart"] = cart
    request.session.modified = True

    return redirect("cart")

@require_POST
def decrease_session_cart(request, product_id):
    if not request.user.is_authenticated:
        return redirect("login")

    cart = request.session.get("cart", {})
    product_id = str(product_id)

    if product_id in cart:
        if cart[product_id] <= 1:
            del cart[product_id]
        else:
            cart[product_id] -= 1

    request.session["cart"] = cart
    request.session.modified = True

    return redirect("cart")


@require_POST
def remove_from_session_cart(request, product_id):
    if not request.user.is_authenticated:
        return redirect("login")

    cart = request.session.get("cart", {})
    product_id = str(product_id)

    if product_id in cart:
        del cart[product_id]

    request.session["cart"] = cart
    request.session.modified = True

    return redirect("cart")

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_cart_item_api(request, product_id):
    action = request.data.get("action")
    cart = get_object_or_404(Cart, user=request.user)
    cart_item = get_object_or_404(CartItem, cart=cart, product_id=product_id)

    if action == "increase":
        cart_item.quantity += 1
        cart_item.save(update_fields=("quantity",))
        return Response({"message": "Quantity increased"})

    if action == "decrease":
        if cart_item.quantity <= 1:
            cart_item.delete()
            return Response({"message": "Product removed from cart"})

        cart_item.quantity -= 1
        cart_item.save(update_fields=("quantity",))
        return Response({"message": "Quantity decreased"})

    return Response({"error": "Invalid action"}, status=400)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def remove_from_cart_api(request, product_id):
    cart = get_object_or_404(Cart, user=request.user)

    CartItem.objects.filter(
        cart=cart,
        product_id=product_id
    ).delete()

    return Response({
        "message": "Product removed from cart"
    })

def profile_page(request):
    if not request.user.is_authenticated:
        return redirect("login")

    return render(request, "shop/auth/profile.html", {
        "user": request.user,
        "username": request.user.username,
        "email": request.user.email,
        "first_name": request.user.first_name,
        "last_name": request.user.last_name,
    })

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def merge_cart_api(request):
    items = request.data.get("items", {})

    if not isinstance(items, dict):
        return Response({"error": "Invalid cart data"}, status=400)

    cart, _ = Cart.objects.get_or_create(user=request.user)

    for product_id, quantity in items.items():
        try:
            product_id = int(product_id)
            quantity = int(quantity)
        except (TypeError, ValueError):
            continue

        if quantity <= 0:
            continue

        product = Product.objects.filter(id=product_id).first()

        if not product:
            continue

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
        )

        if created:
            cart_item.quantity = quantity
        else:
            cart_item.quantity += quantity

        cart_item.save(update_fields=("quantity",))

    return Response({"message": "Guest cart merged"})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def profile_api(request):
    return Response({
        "username": request.user.username,
        "email": request.user.email,
    })

@ensure_csrf_cookie
def checkout_page(request):
    if not request.user.is_authenticated:
        return redirect("login")

    return render(request, "shop/checkout.html")


@require_GET
def checkout_summary_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Login required"}, status=401)

    session_cart = request.session.get("cart", {})

    items = []
    subtotal = 0

    for product_id, quantity in session_cart.items():
        product = Product.objects.filter(id=product_id).first()

        if not product:
            continue

        item_subtotal = product.price * quantity
        subtotal += item_subtotal

        items.append({
            "id": product.id,
            "name": product.name,
            "price": float(product.price),
            "quantity": quantity,
            "subtotal": float(item_subtotal),
            "image": product.image.url if product.image else "",
        })

    if subtotal == 0:
        shipping = 0
        tax = 0
    elif subtotal >= 250:
        shipping = 0
        tax = subtotal * 0.08
    else:
        shipping = subtotal * 0.05

        if shipping < 8:
            shipping = 8

        if shipping > 35:
            shipping = 35

        tax = subtotal * 0.08

    grand_total = subtotal + shipping + tax

    return JsonResponse({
        "items": items,
        "subtotal": round(subtotal, 2),
        "shipping": round(shipping, 2),
        "tax": round(tax, 2),
        "grand_total": round(grand_total, 2),
    })


@require_POST
def save_shipping_address_json(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Login required"}, status=401)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    required_fields = [
        "first_name",
        "last_name",
        "email",
        "address",
        "city",
        "postal_code",
    ]

    for field in required_fields:
        if not str(data.get(field, "")).strip():
            return JsonResponse({
                "error": f"{field.replace('_', ' ').title()} is required"
            }, status=400)

    ShippingAddress.objects.create(
        user=request.user,
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        email=data.get("email"),
        address=data.get("address"),
        city=data.get("city"),
        postal_code=data.get("postal_code"),
    )

    return JsonResponse({
        "message": "Shipping address saved successfully"
    })

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def save_shipping_address_api(request):
    ShippingAddress.objects.create(
        user=request.user,
        first_name=request.data.get("first_name"),
        last_name=request.data.get("last_name"),
        email=request.data.get("email"),
        address=request.data.get("address"),
        city=request.data.get("city"),
        postal_code=request.data.get("postal_code"),
    )

    return Response({"message": "Shipping address saved"})

def social_complete_page(request):
    return render(request, "shop/auth/social_complete.html")

def google_login(request):
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


def google_callback(request):
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